from typing import List, Optional
from pydantic import BaseModel, Field
from src.dto.common import CommonResponse

class Creator(BaseModel):
    """创建者DTO"""
    uid: int = Field(..., description="创建者id")
    name: str = Field(..., description="创建者名称")
    email: str = Field(..., description="邮箱")

class CommunityListItem(BaseModel):
    """账单历史项DTO"""
    genImgId: int = Field(..., description="图片id")
    picUrl: str = Field(..., description="图片链接")
    isCollected: str = Field(..., description="是否收藏 1-是 0-否")
    seoImgUid: str = Field(..., description="seo图片uid")
    creator: Optional[Creator] = Field(..., description="创建者")
    islike: int = Field(..., description="是否点赞 1-是 0-否")
    likeCount: int = Field(..., description="点赞数量")
    
class CommunityListData(BaseModel):
    total: int = Field(..., description="总记录数")
    list: List[CommunityListItem] = Field(..., description="记录列表")

class CommunityListResponse(CommonResponse[CommunityListData]):
    pass

class CommunityDetailResponseData(BaseModel):
    genImgId: int = Field(..., description="图片id")
    genType: List[str] = Field(..., description="生成类型")
    prompt: str = Field(..., description="提示词")
    originalImgUrl: str = Field(..., description="原始图片链接")
    materials: List[str] = Field(..., description="材质")
    trendStyles: List[str] = Field(..., description="流行风格")
    description: str = Field(..., description="描述")
    isLike: int = Field(..., description="是否点赞 1-是 0-否")
    likeCount: int = Field(..., description="点赞数量")
    isCollected: str = Field(..., description="是否收藏 1-是 0-否")
    creator: Optional[Creator] = Field(..., description="创建者")

class CommunityDetailResponse(CommonResponse[CommunityDetailResponseData]):
    pass

