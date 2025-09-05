from typing import List, Optional
from pydantic import BaseModel, Field
from .common import CommonResponse


class FashionDataItem(BaseModel):
    """时尚数据项DTO"""
    record_id: str = Field(..., description="记录ID")
    slug: str = Field(..., description="URL友好标识")
    gender: str = Field(..., description="性别")
    feature: str = Field(..., description="特征")
    clothing_description: str = Field(..., description="服装描述")
    type: str = Field(..., description="类型")
    complete_prompt: Optional[str] = Field(None, description="完整prompt")
    choose_img: Optional[str] = Field(None, description="选中图片地址")
    image_url: Optional[str] = Field(None, description="OSS图片地址")


class ProcessCsvResponseData(BaseModel):
    """处理CSV响应数据"""
    total_records: int = Field(..., description="总记录数")
    processed_records: int = Field(..., description="处理成功的记录数")
    failed_records: int = Field(..., description="处理失败的记录数")
    processed_images: int = Field(..., description="处理的图片数量")
    failed_images: int = Field(..., description="处理失败的图片数量")
    error_details: List[str] = Field(default=[], description="错误详情列表")


class ProcessCsvResponse(CommonResponse[ProcessCsvResponseData]):
    """处理CSV响应DTO"""
    pass


class GetFashionDataRequest(BaseModel):
    """获取时尚数据请求"""
    page: int = Field(1, description="页码，从1开始")
    page_size: int = Field(10, description="每页数量")
    gender: Optional[str] = Field(None, description="性别筛选")
    type: Optional[str] = Field(None, description="类型筛选")


class GetFashionDataResponseData(BaseModel):
    """获取时尚数据响应数据"""
    total: int = Field(..., description="总记录数")
    list: List[FashionDataItem] = Field(..., description="数据列表")


class GetFashionDataResponse(CommonResponse[GetFashionDataResponseData]):
    """获取时尚数据响应"""
    pass


class FrontendImageItem(BaseModel):
    """前端图片展示项DTO"""
    id: int = Field(..., description="数据ID")
    record_id: str = Field(..., description="记录ID")
    slug: str = Field(..., description="URL友好标识")
    image_url: Optional[str] = Field(None, description="OSS图片地址")
    clothing_description: str = Field(..., description="服装描述")
    complete_prompt: Optional[str] = Field(None, description="完整prompt")
    type: str = Field(..., description="服装类型")
    gender: str = Field(..., description="性别")
    feature: str = Field(..., description="特征")
    create_time: str = Field(..., description="创建时间")


class GetFrontendImagesRequest(BaseModel):
    """获取前端图片列表请求"""
    page: int = Field(1, description="页码，从1开始", ge=1)
    page_size: int = Field(20, description="每页数量，默认20", ge=1, le=50)
    type_filter: Optional[List[str]] = Field(None, description="服装类型筛选，支持多个值：Evening Wear, Casual, Professional, Sportswear, Kidswear")
    gender_filter: Optional[List[str]] = Field(None, description="性别筛选，支持多个值：Female, Male")


class GetFrontendImagesResponseData(BaseModel):
    """获取前端图片列表响应数据"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    has_more: bool = Field(..., description="是否还有更多数据")
    list: List[FrontendImageItem] = Field(..., description="图片列表")


class GetFrontendImagesResponse(CommonResponse[GetFrontendImagesResponseData]):
    """获取前端图片列表响应"""
    pass


class SimilarImageItem(BaseModel):
    """相似图片项DTO"""
    id: int = Field(..., description="数据ID")
    record_id: str = Field(..., description="记录ID")
    slug: str = Field(..., description="URL友好标识")
    image_url: Optional[str] = Field(None, description="OSS图片地址")
    clothing_description: str = Field(..., description="服装描述")
    type: str = Field(..., description="服装类型")
    gender: str = Field(..., description="性别")
    feature: str = Field(..., description="特征")
    similarity_score: float = Field(..., description="相似度分数")


class ImageDetailItem(BaseModel):
    """图片详情项DTO"""
    id: int = Field(..., description="数据ID")
    record_id: str = Field(..., description="记录ID")
    slug: str = Field(..., description="URL友好标识")
    image_url: Optional[str] = Field(None, description="OSS图片地址")
    choose_img: Optional[str] = Field(None, description="选中图片地址")
    clothing_description: str = Field(..., description="服装描述")
    complete_prompt: Optional[str] = Field(None, description="完整prompt")
    type: str = Field(..., description="服装类型")
    gender: str = Field(..., description="性别")
    feature: str = Field(..., description="特征")
    create_time: str = Field(..., description="创建时间")
    update_time: str = Field(..., description="更新时间")
    similar_images: List[SimilarImageItem] = Field(default=[], description="相似图片列表")


class GetImageDetailResponse(CommonResponse[ImageDetailItem]):
    """获取图片详情响应"""
    pass
