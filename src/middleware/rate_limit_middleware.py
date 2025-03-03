import time
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from typing import Callable, Dict, Optional, Tuple

from ..config.rate_limit import rate_limit_settings, RateLimitRule
from ..config.log_config import logger
from ..db.redis import redis_client
from ..core.context import get_current_user_context
from ..dto.common import CommonResponse

class RateLimitMiddleware:
    """基于Redis的API请求限流中间件"""
    
    def __init__(self):
        self.enabled = rate_limit_settings.enabled
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        # 如果限流功能被禁用，直接处理请求
        if not self.enabled:
            return await call_next(request)
        
        # 获取请求路径
        path = request.url.path
        
        # 检查是否在白名单中
        if self._is_path_in_whitelist(path):
            return await call_next(request)
        
        # 获取客户端IP
        client_ip = self._get_client_ip(request)
        
        # 检查IP是否在黑名单中
        if client_ip in rate_limit_settings.ip_blacklist:
            return JSONResponse(
                status_code=403,
                content=CommonResponse(
                    code=403,
                    msg="IP address blocked"
                ).model_dump()
            )
        
        # 获取用户信息
        user = get_current_user_context()
        user_id = user.id if user else None
        
        # 记录日志
        if user_id:
            logger.debug(f"Rate limiting for user ID: {user_id}, path: {path}")
        else:
            logger.debug(f"Rate limiting for anonymous user (IP: {client_ip}), path: {path}")
        
        # 获取适用的限流规则
        rule = self._get_rate_limit_rule(path)
        
        # 如果用户未认证且规则不适用于匿名用户，直接处理请求
        if not user_id and not rule.apply_to_anonymous:
            return await call_next(request)
        
        # 检查是否超过限流
        is_limited, remaining, reset_time = await self._check_rate_limit(
            client_ip=client_ip,
            user_id=user_id,
            path=path,
            rule=rule
        )
        
        # 如果超过限流，返回错误响应
        if is_limited:
            logger.warning(
                f"Rate limit exceeded: IP={client_ip}, User ID={user_id}, Path={path}, "
                f"Reset in {reset_time} seconds"
            )
            return JSONResponse(
                status_code=429,
                content=CommonResponse(
                    code=429,
                    msg="Too many requests, please try again later"
                ).model_dump(),
                headers={
                    "X-RateLimit-Limit": str(rule.max_requests),
                    "X-RateLimit-Remaining": str(0),
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time)
                }
            )
        
        # 将限流信息添加到响应头
        response = await call_next(request)
        
        # 尝试添加限流信息到响应头
        try:
            response.headers["X-RateLimit-Limit"] = str(rule.max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_time)
        except (AttributeError, TypeError):
            # 某些响应类型可能不支持修改头信息
            pass
        
        return response
    
    def _is_path_in_whitelist(self, path: str) -> bool:
        """检查路径是否在白名单中"""
        return any(path.startswith(whitelist_path) for whitelist_path in rate_limit_settings.whitelist_paths)
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP地址"""
        # 尝试从常见的代理头中获取真实IP
        for header in ["X-Forwarded-For", "X-Real-IP"]:
            if header in request.headers:
                # X-Forwarded-For可能包含多个IP，取第一个
                return request.headers[header].split(",")[0].strip()
        # 如果没有代理头，使用直接客户端地址
        return request.client.host if request.client else "unknown"
    
    def _get_rate_limit_rule(self, path: str) -> RateLimitRule:
        """获取适用于指定路径的限流规则"""
        # 按最长匹配原则查找规则
        matching_path = ""
        for rule_path in rate_limit_settings.path_rules:
            if path.startswith(rule_path) and len(rule_path) > len(matching_path):
                matching_path = rule_path
        
        # 如果找到匹配规则，返回它
        if matching_path:
            return rate_limit_settings.path_rules[matching_path]
        
        # 否则返回默认规则
        return rate_limit_settings.default
    
    async def _check_rate_limit(
        self, 
        client_ip: str, 
        user_id: Optional[int], 
        path: str, 
        rule: RateLimitRule
    ) -> Tuple[bool, int, int]:
        """
        检查请求是否超过限流
        
        Args:
            client_ip: 客户端IP
            user_id: 用户ID（如果已认证）
            path: 请求路径
            rule: 限流规则
            
        Returns:
            Tuple[is_limited, remaining_requests, reset_time_seconds]
        """
        # 当前时间戳
        now = int(time.time())
        window_start = now - rule.window_seconds
        
        # 构建Redis键
        # 用户ID优先于IP地址（因为同一个用户可能使用不同的IP）
        identifier = f"user:{user_id}" if user_id else f"ip:{client_ip}"
        key = f"rate_limit:{path}:{identifier}"
        
        # 使用Redis事务保证原子性
        pipe = redis_client.pipeline()
        
        try:
            # 删除窗口外的记录
            pipe.zremrangebyscore(key, 0, window_start)
            
            # 添加当前请求的时间戳
            pipe.zadd(key, {str(now): now})
            
            # 获取当前窗口内的请求数
            pipe.zcount(key, window_start, now)
            
            # 设置键过期时间（窗口大小 + 1秒）
            pipe.expire(key, rule.window_seconds + 1)
            
            # 执行事务
            _, _, request_count, _ = pipe.execute()
            
            # 计算剩余请求数和重置时间
            remaining = max(0, rule.max_requests - request_count)
            reset_time = rule.window_seconds - (now % rule.window_seconds)
            
            # 是否超过限流
            is_limited = request_count > rule.max_requests
            
            return is_limited, remaining, reset_time
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            # 出错时不限流
            return False, rule.max_requests, rule.window_seconds 