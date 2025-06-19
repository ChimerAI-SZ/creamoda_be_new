from fastapi import Request
from jose import ExpiredSignatureError, jwt

from src.config.log_config import logger
from src.db.session import SessionLocal, get_db
from src.exceptions.user import AuthenticationError
from src.core.context import UserContext
from src.config.config import settings
from src.models.models import UserInfo

def get_user_info_from_request(request: Request) -> UserContext:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise AuthenticationError(message="no auth header")
    
    scheme, token = auth_header.split()
    if scheme.lower() != 'bearer':
        raise AuthenticationError(message="invalid auth scheme")
    
    payload = jwt.decode(
        token,
        settings.security.jwt_secret_key,
        algorithms=[settings.security.jwt_algorithm]
    )
    email = payload.get("sub")

    if not email:
        raise AuthenticationError(message="Invalid token payload")
    
    db = get_db()
    try:
        user = db.query(UserInfo).filter(UserInfo.email == email).first()
        if not user:
            raise AuthenticationError(message="User not found")
        
        if user.status != 1:
            raise AuthenticationError(message="User account disabled")
        
        # 用户上下文
        return UserContext(
            id=user.id,
            uid=user.uid,
            email=user.email,
            username=user.username,
            status=user.status,
            email_verified=user.email_verified,
            head_pic=user.head_pic,
            has_pwd=bool(user.pwd)
        )
    except (AuthenticationError, ExpiredSignatureError) as e:
        logger.warning(f"Authentication error: {str(e)}")
        raise e
    finally:
        db.close()