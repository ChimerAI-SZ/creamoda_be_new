from typing import Optional

from pydantic import BaseModel, EmailStr


class UserInfo(BaseModel):
    email: EmailStr
    name: str
    picture: Optional[str] = None 