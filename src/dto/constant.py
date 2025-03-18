from pydantic import BaseModel, Field
from typing import List, Optional
from .common import CommonResponse

class EnumItem(BaseModel):
    """枚举项"""
    code: str = Field(..., description="枚举键")
    name: str = Field(..., description="枚举值")

class EnumData(BaseModel):
    """枚举数据"""
    list: List[EnumItem] = Field(..., description="枚举值列表")
    type: Optional[str] = Field(None, description="枚举类型")

class GetEnumResponse(CommonResponse[EnumData]):
    """获取枚举响应"""
    pass 