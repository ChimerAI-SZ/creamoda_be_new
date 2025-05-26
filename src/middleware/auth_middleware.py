from typing import List, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from jose import ExpiredSignatureError, jwt
from sqlalchemy.orm import Session

from src.config.log_config import logger
from src.config.config import settings
from src.core.context import UserContext, set_user_context, clear_user_context
from src.db.redis import redis_client
from src.db.session import SessionLocal
from src.dto.common import CommonResponse
from src.exceptions.user import AuthenticationError
from src.models.models import UserInfo

class AuthMiddleware:
    def __init__(self, protected_paths: Optional[List[str]] = None):
        """
        :param protected_paths: 需要登录验证的路径列表，支持通配符 *
        例如: ["/api/v1/user/*", "/api/v1/img/*"]
        """
        self.protected_paths = protected_paths or []

    async def __call__(self, request: Request, call_next):
        path = request.url.path
        
        # 检查是否需要验证
        if not self._should_protect_path(path):
            return await call_next(request)

        # 获取并验证token
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=200,
                content=CommonResponse(
                    code=401,
                    msg="Authorization header missing"
                ).model_dump()
            )

        try:
            # 解析token
            scheme, token = auth_header.split()
            if scheme.lower() != 'bearer':
                raise AuthenticationError(message="Invalid authentication scheme")
            
            # 验证token
            payload = jwt.decode(
                token,
                settings.security.jwt_secret_key,
                algorithms=[settings.security.jwt_algorithm]
            )
            email = payload.get("sub")
            
            if not email:
                raise AuthenticationError(message="Invalid token payload")
                
            # 检查Redis中的会话
            # stored_token = redis_client.get(f"user_session:{email}")
            # if not stored_token or stored_token != token:
            #     raise AuthenticationError(message="Invalid or expired session")
            
            # 获取用户信息
            db = SessionLocal()
            try:
                user = db.query(UserInfo).filter(UserInfo.email == email).first()
                if not user:
                    raise AuthenticationError(message="User not found")
                
                if user.status != 1:
                    raise AuthenticationError(message="User account disabled")
                
                # 设置用户上下文
                set_user_context(UserContext(
                    id=user.id,
                    uid=user.uid,
                    email=user.email,
                    username=user.username,
                    status=user.status,
                    email_verified=user.email_verified,
                    head_pic=user.head_pic,
                    has_pwd=bool(user.pwd)  # pwd为空则showPwd为False，否则为True
                ))
                
                # 继续处理请求
                response = await call_next(request)
                return response
                
            finally:
                db.close()
                clear_user_context()
                
        except (AuthenticationError, ExpiredSignatureError) as e:
            logger.warning(f"Authentication error: {str(e)}")
            return JSONResponse(
                status_code=200,
                content=CommonResponse(
                    code=401,
                    msg="Invalid or expired token"
                ).model_dump()
            )

    def _should_protect_path(self, path: str) -> bool:
        """检查路径是否需要保护"""
        for protected_path in self.protected_paths:
            if protected_path.endswith('*'):
                if path.startswith(protected_path[:-1]):
                    return True
            elif path == protected_path:
                return True
        return False 