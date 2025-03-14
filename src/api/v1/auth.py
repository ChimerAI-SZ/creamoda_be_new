from io import BytesIO
import httpx
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Response
from src.services.upload_service import UploadService
from src.config.config import settings
from sqlalchemy.orm import Session
from src.utils.uid import generate_uid
from src.dto.user import (UserLoginResponse, UserLoginData)
from src.config.log_config import logger
from src.utils.image import download_and_upload_image

from ...dto.token import Token
from ...models.models import UserInfo
from ...utils.security import create_access_token
from src.db.session import get_db

router = APIRouter()

@router.get("/google")
async def google_auth():
    """获取Google登录URL"""
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.google_oauth2.client_id}&"
        f"redirect_uri={settings.google_oauth2.redirect_uri}&"
        "response_type=code&"
        "scope=openid email profile"
    )
    return {"auth_url": auth_url}

@router.get("/callback")
async def auth_callback(code: str, db: Session = Depends(get_db), response: Response = Response()):
    """处理Google回调"""
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": settings.google_oauth2.client_id,
        "client_secret": settings.google_oauth2.client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.google_oauth2.redirect_uri,
    }
    
    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=token_data)
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Failed to get access token"
            )
        
        access_token = token_response.json().get("access_token")
        
        userinfo_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if userinfo_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Failed to get user info"
            )
        
        user_data = userinfo_response.json()
        
        user_info = UserInfo(
            email=user_data["email"],
            username=user_data.get("name", ""),
            google_sub_id=user_data.get("id"),
            google_access_token=access_token
        )

        # 检查用户是否存在，如果存在则更新用户信息，否则创建新用户
        user = db.query(UserInfo).filter(UserInfo.email == user_info.email).first()
        if user:
            user.email_verified = 1
            user.google_sub_id = user_info.google_sub_id
            user.google_access_token = user_info.google_access_token
            user.last_login_time = datetime.utcnow()
            user.update_time = datetime.utcnow()
            db.commit()
            db.refresh(user)
        else:
            profile_pic_url = None
            if user_data.get("picture"):
                # 使用新的工具函数下载并上传头像
                profile_pic_url = await download_and_upload_image(
                    user_data.get("picture"),
                    f"google_avatar_{user_data.get('id')}"
                )
            user_info.head_pic = profile_pic_url
            user_info.status = 1
            user_info.uid = generate_uid()
            user_info.email_verified = 1
            user_info.last_login_time = datetime.utcnow()
            user_info.create_time = datetime.utcnow()
            user_info.update_time = datetime.utcnow()
            db.add(user_info)
            db.commit()
        
        access_token = create_access_token({"sub": user_info.email})

        bearer_token = f"Bearer {access_token}"
        response.headers["Authorization"] = bearer_token
        return UserLoginResponse(
            code=0,
            msg="Login successful",
            data=UserLoginData(
                authorization=bearer_token.replace("+", "%2B")  # 转义 + 字符
            )
        )
