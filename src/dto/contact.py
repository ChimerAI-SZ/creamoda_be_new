from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from .common import CommonResponse

class ContactBusinessRequest(BaseModel):
    contactEmail: EmailStr = Field(..., description="联系邮箱")
    source: int = Field(None, description="来源场景")
    genImgId: Optional[int] = Field(None, description="生成图片id")

class ContactBusinessResponse(CommonResponse):
    pass 