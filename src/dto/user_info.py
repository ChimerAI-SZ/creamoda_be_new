from pydantic import BaseModel, EmailStr
from typing import Optional


class UserInfo(BaseModel):
    email: EmailStr
    name: str
    picture: Optional[str] = None 