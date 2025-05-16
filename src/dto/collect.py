from typing import List
from pydantic import BaseModel, Field

from src.dto.common import CommonResponse


class CollectRequest(BaseModel):
    genImgId: int = Field(..., title="生成图片id", description="生成图片id")
    action: int = Field(..., title="动作", description="1-收藏 2-取消收藏")
    
class CollectResponse(CommonResponse):
    pass

class CollectListItem(BaseModel):
    genImgId: int = Field(..., description="生成图片id")
    resultPic: str = Field(..., description="生成结果图片")
    createTime: str = Field(..., description="创建时间")

class CollectListData(BaseModel):
    list: List[CollectListItem] = Field(..., description="枚举值列表")
    total: int = Field(..., description="总记录数")

class CollectListResponse(CommonResponse[CollectListData]):
    pass