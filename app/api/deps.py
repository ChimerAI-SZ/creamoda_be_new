from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from typing import Dict
from ..core.config import settings
from ..schemas.user import UserInfo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 模拟用户数据库
users_db: Dict[str, UserInfo] = {}

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInfo:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None or email not in users_db:
            raise credentials_exception
        return users_db[email]
    except JWTError:
        raise credentials_exception 