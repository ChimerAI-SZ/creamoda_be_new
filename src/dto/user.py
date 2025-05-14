from pydantic import BaseModel, EmailStr
from typing import Optional

from .common import CommonResponse


class UserLoginRequest(BaseModel):
    email: str
    pwd: str

class UserLoginData(BaseModel):
    authorization: str

class UserLoginResponse(CommonResponse[UserLoginData]):
    pass

class UserRegisterRequest(BaseModel):
    email: str
    pwd: str
    username: str

class UserRegisterResponse(CommonResponse):
    pass

class LogoutResponse(CommonResponse):
    pass

class EmailVerifyRequest(BaseModel):
    verifyCode: str
    email: str

class EmailVerifyResponse(CommonResponse):
    pass 

class ResendEmailRequest(BaseModel):
    email: str

class ResendEmailResponse(CommonResponse):
    pass 

class ChangeUsernameRequest(BaseModel):
    username: str

class ChangeUsernameResponse(CommonResponse):
    pass 

class ChangePwdRequest(BaseModel):
    pwd: str

class ChangePwdResponse(CommonResponse):
    pass 

class ChangeUserInfoRequest(BaseModel):
    username: Optional[str] = None
    pwd: Optional[str] = None
    head_pic: Optional[str] = None

class ChangeUserInfoResponse(CommonResponse):
    pass 