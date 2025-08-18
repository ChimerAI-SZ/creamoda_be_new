import time
from datetime import datetime, timedelta
from typing import Callable, List, Optional, Tuple
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from src.db.redis import redis_client

from src.core.context import get_current_user_context
from src.config.log_config import logger
from src.db.session import SessionLocal, get_db
from src.exceptions.base import CustomException
from src.exceptions.user import AuthenticationError
from src.dto.common import CommonResponse
from src.models.models import GenImgResult, Subscribe

class GenImgRateLimitMiddleware:
    """基于Redis的生图API请求限流中间件"""
    def __init__(self, protected_paths: Optional[List[str]] = None):
        """
        :param protected_paths: 需要限流的路径列表，支持通配符 *
        例如: ["/api/v1/img/*"]
        """
        self.protected_paths = protected_paths or ["/api/v1/img/*"]
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        # 获取请求路径
        path = request.url.path
        
        # 检查是否需要验证
        if not self._should_protect_path(path):
            return await call_next(request)
        
        # 获取用户信息
        user = get_current_user_context()
        user_id = user.id if user else None
        
        # 记录日志
        if user_id:
            logger.debug(f"Rate limiting for user ID: {user_id}, path: {path}")
        else:
            raise AuthenticationError(message="User not login")
        
        db = SessionLocal()
        try:
            # 检查是否超过限流
            is_limited, remaining, reset_time = await self._check_rate_limit(
                db=db,
                user_id=user_id
            )
            
            # 如果超过限流，返回错误响应
            if is_limited:
                logger.warning(
                    f"Rate limit exceeded: User ID={user_id}, Path={path}, "
                    f"Reset in {reset_time} seconds"
                )
                return JSONResponse(
                    status_code=429,
                    content=CommonResponse(
                        code=429,
                        msg="Too many requests, please try again later"
                    ).model_dump()
                )
            
            # 检查并发限制
            is_concurrency_limited = await self._check_concurrency_limit(
                db=db,
                user_id=user_id
            )
            if is_concurrency_limited:
                return JSONResponse(
                    status_code=430,
                    content=CommonResponse(
                        code=430,
                        msg="Concurrency limit reached, please try again later"
                    ).model_dump()
                )
            
            # 将限流信息添加到响应头
            response = await call_next(request)
            return response
        finally:
            db.close()
    
    def _should_protect_path(self, path: str) -> bool:
        """检查路径是否需要保护"""
        for protected_path in self.protected_paths:
            if protected_path.endswith('*'):
                if path.startswith(protected_path[:-1]):
                    return True
            elif path == protected_path:
                return True
        return False 
    
    async def _check_rate_limit(
        self, 
        db: Session,
        user_id: Optional[int]
    ) -> Tuple[bool, int, int]:
        window_seconds = 14400
        max_requests = 50
        sub = db.query(Subscribe).filter(Subscribe.uid == user_id).first()
        if not sub or sub.level == 0:
            # 未订阅用户，使用默认限流规则
            pass
        elif sub.level == 1:
            max_requests = 100
        elif sub.level == 2:
            max_requests = 200
        elif sub.level == 3:
            return False, 0, 0

        # 当前时间戳
        now = int(time.time())
        window_start = now - window_seconds
        
        # 构建Redis键
        key = f"gen_img_rate_limit:user:{user_id}"
        
        # 使用Redis事务保证原子性
        pipe = redis_client.pipeline()
        
        try:
            # 删除窗口外的记录
            pipe.zremrangebyscore(key, 0, window_start)
            
            # 获取当前窗口内的请求数（不包含本次请求）
            pipe.zcount(key, window_start, now)
            
            # 执行前两个操作
            _, current_count = pipe.execute()
            
            # 检查是否会超过限流
            is_limited = current_count >= max_requests
            
            if not is_limited:
                # 如果不会被限流，则添加当前请求
                pipe = redis_client.pipeline()
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, window_seconds + 1)
                pipe.execute()
                
                # 更新计数
                request_count = current_count + 1
            else:
                # 如果会被限流，不添加当前请求
                request_count = current_count
            
            # 计算剩余请求数和重置时间
            remaining = max(0, max_requests - request_count)
            reset_time = window_seconds - (now % window_seconds)
            
            return is_limited, remaining, reset_time
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            # 出错时不限流
            return False, max_requests, window_seconds 
        
    async def _check_concurrency_limit(
        self, 
        db: Session,
        user_id: Optional[int]
    ) -> bool:
        """检查并发限制"""
        max_concurrency = 3  # 临时提高默认并发限制
        sub = db.query(Subscribe).filter(Subscribe.uid == user_id).first()
        if not sub or sub.level == 0:
            # 未订阅用户，使用默认限流规则
            pass
        elif sub.level == 1:
            max_concurrency = 4  # 提高订阅用户限制
        elif sub.level == 2:
            max_concurrency = 6
        elif sub.level == 3:
            max_concurrency = 10

        # 同时检查超时任务，自动清理卡住的任务
        timeout_threshold = datetime.utcnow() - timedelta(minutes=30)  # 30分钟超时
        
        # 清理超时的任务
        timeout_tasks = db.query(GenImgResult).filter(
            GenImgResult.uid == user_id,
            GenImgResult.status.in_([1, 2]),
            GenImgResult.update_time < timeout_threshold
        ).all()
        
        if timeout_tasks:
            logger.warning(f"Found {len(timeout_tasks)} timeout tasks for user {user_id}, cleaning up...")
            for task in timeout_tasks:
                task.status = 4  # 标记为失败
                task.update_time = datetime.utcnow()
            db.commit()

        gening_img_count = db.query(GenImgResult).filter(GenImgResult.uid == user_id, GenImgResult.status.in_([1, 2])).count()
        if gening_img_count >= max_concurrency:
            logger.warning(f"Concurrency limit reached: user {user_id} has {gening_img_count} active tasks (limit: {max_concurrency})")
            return True
        else:
            return False