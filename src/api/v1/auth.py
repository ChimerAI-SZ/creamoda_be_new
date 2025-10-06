
from io import BytesIO
import httpx
import jwt
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Response
from src.services.upload_service import UploadService
from src.config.config import settings
from sqlalchemy.orm import Session
from src.utils.uid import generate_uid
from src.dto.user import (UserLoginResponse, UserLoginData)
from src.dto.google_one_tap import GoogleOneTapRequest, GoogleOneTapResponse
from src.config.log_config import logger
from src.utils.image import download_and_upload_image

from ...dto.token import Token
from ...models.models import UserInfo
from ...utils.security import create_access_token
from src.db.session import get_db
from src.db.redis import redis_client

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
        
        # 将 token 存储到 Redis 中，用于后续会话验证
        redis_client.setex(
            f"user_session:{user_info.email}",
            settings.security.access_token_expire_minutes * 60,  # 转换为秒
            access_token
        )

        bearer_token = f"Bearer {access_token}"
        response.headers["Authorization"] = bearer_token
        return UserLoginResponse(
            code=0,
            msg="Login successful",
            data=UserLoginData(
                authorization=bearer_token.replace("+", "%2B")  # 转义 + 字符
            )
        )


@router.post("/google-callback", response_model=GoogleOneTapResponse)
async def google_one_tap_callback(
    request: GoogleOneTapRequest,
    db: Session = Depends(get_db),
    response: Response = Response()
):
    """处理 Google One Tap JWT credential"""
    try:
        # 解析 JWT token（暂时跳过签名验证用于开发）
        # 在生产环境中应该验证签名
        decoded_token = jwt.decode(
            request.credential, 
            options={"verify_signature": False}  # 开发环境跳过签名验证
        )
        
        logger.info(f"Google One Tap JWT payload: {decoded_token}")
        
        # 验证基本字段
        if not decoded_token.get("email") or not decoded_token.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Google credential: missing required fields"
            )
        
        # 检查用户是否存在
        email = decoded_token.get("email")
        user = db.query(UserInfo).filter(UserInfo.email == email).first()
        
        if user:
            # 更新现有用户
            user.email_verified = 1
            user.google_sub_id = decoded_token.get("sub")
            user.last_login_time = datetime.utcnow()
            user.update_time = datetime.utcnow()
            
            # 更新用户名如果有变化
            if decoded_token.get("name") and user.username != decoded_token.get("name"):
                user.username = decoded_token.get("name")
            
            db.commit()
            db.refresh(user)
            
            logger.info(f"Updated existing user: {email}")
        else:
            # 创建新用户
            profile_pic_url = None
            if decoded_token.get("picture"):
                try:
                    # 下载并上传Google头像
                    profile_pic_url = await download_and_upload_image(
                        decoded_token.get("picture"),
                        f"google_avatar_{decoded_token.get('sub')}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to download Google avatar: {e}")
            
            user = UserInfo(
                email=email,
                username=decoded_token.get("name", email.split("@")[0]),
                google_sub_id=decoded_token.get("sub"),
                head_pic=profile_pic_url,
                status=1,  # 活跃状态
                uid=generate_uid(),
                email_verified=1,  # Google用户默认验证邮箱
                last_login_time=datetime.utcnow(),
                create_time=datetime.utcnow(),
                update_time=datetime.utcnow()
            )
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            logger.info(f"Created new user from Google One Tap: {email}")
        
        # 生成访问令牌
        access_token = create_access_token({"sub": email})
        
        # 将 token 存储到 Redis 中，用于后续会话验证
        redis_client.setex(
            f"user_session:{email}",
            settings.security.access_token_expire_minutes * 60,  # 转换为秒
            access_token
        )
        
        bearer_token = f"Bearer {access_token}"
        
        # 设置响应头
        response.headers["Authorization"] = bearer_token
        
        return GoogleOneTapResponse(
            code=0,
            msg="Google One Tap login successful",
            data=UserLoginData(
                authorization=bearer_token.replace("+", "%2B")
            )
        )
        
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Google credential: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Google One Tap callback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during Google authentication"
        )
