from typing import Optional

from pydantic import BaseModel, EmailStr


class UserInfo(BaseModel):
    email: str
    name: str
    picture: Optional[str] = None 