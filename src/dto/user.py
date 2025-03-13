from pydantic import BaseModel, EmailStr

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