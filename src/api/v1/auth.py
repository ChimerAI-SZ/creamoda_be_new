import httpx
from fastapi import APIRouter, HTTPException, status
from src.config.config import settings

from ...dto.token import Token
from ...dto.user_info import UserInfo
from ...utils.security import create_access_token

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
async def auth_callback(code: str):
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
            name=user_data.get("name", ""),
            picture=user_data.get("picture")
        )
        # users_db[user_info.email] = user_info
        
        access_token = create_access_token({"sub": user_info.email})
        return Token(access_token=access_token, token_type="bearer") 