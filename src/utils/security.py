from datetime import datetime, timedelta
from typing import Optional

from jose import jwt

from ..config.config import settings


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.security.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.security.jwt_secret_key, 
        algorithm=settings.security.jwt_algorithm
    )
    return encoded_jwt 