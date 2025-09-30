from pydantic import BaseModel
from typing import Optional
from .common import CommonResponse
from .user import UserLoginData


class GoogleOneTapRequest(BaseModel):
    """Google One Tap JWT credential 请求"""
    credential: str
    source: str = "one-tap"


class GoogleOneTapResponse(CommonResponse[UserLoginData]):
    """Google One Tap 登录响应"""
    pass
