from contextvars import ContextVar
from typing import Optional
from pydantic import BaseModel

class UserContext(BaseModel):
    id: int
    uid: int
    email: str
    username: str
    status: int
    email_verified: int
    head_pic: Optional[str] = None
    has_pwd: Optional[bool] = None

# 创建上下文变量
user_context: ContextVar[Optional[UserContext]] = ContextVar('user_context', default=None)

def get_current_user_context() -> Optional[UserContext]:
    """获取当前用户上下文"""
    return user_context.get()

def set_user_context(user: UserContext) -> None:
    """设置用户上下文"""
    user_context.set(user)

def clear_user_context() -> None:
    """清除用户上下文"""
    user_context.set(None) 