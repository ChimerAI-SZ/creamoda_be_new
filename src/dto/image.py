from pydantic import BaseModel, Field, validator
from typing import Optional, List
from .common import CommonResponse
from ..constants.image_constants import SUPPORTED_IMAGE_FORMATS


class TextToImageRequest(BaseModel):
    prompt: str = Field(..., title="提示词")
    withHumanModel: int = Field(..., title="使用人类模特", description="1-使用 0-不使用")  
    gender: int = Field(..., title="模特性别", description="1-男 2-女")
    age: int = Field(..., title="年龄")
    country: str = Field(..., title="国家code")
    modelSize: int = Field(..., title="模特身材code")
    format: str = Field(..., title="图片比例", description="1:1 2:3 3:2 3:4 4:3 9:16 16:9")

    @validator("format")
    def validate_format(cls, v):
        """验证图像格式是否支持"""
        if v not in SUPPORTED_IMAGE_FORMATS:
            supported_formats = ", ".join(SUPPORTED_IMAGE_FORMATS)
            raise ValueError(f"不支持的图像格式: {v}。支持的格式: {supported_formats}")
        return v
    

class ImageGenerationData(BaseModel):
    taskId: str
    status: int = Field(..., description="任务状态：1-待生成 2-生成中 3-已生成")
    estimatedTime: int = Field(..., description="预计完成时间(秒)")

class TextToImageResponse(CommonResponse[ImageGenerationData]):
    pass

class CopyStyleRequest(BaseModel):
    originalPicUrl: str = Field(..., title="原始图片链接", description="图转图 或细节修改传递")
    referLevel: float = Field(..., description="仅洗图填写", title="保真度")
    prompt: str = Field(..., title="提示词")

class CopyStyleResponse(CommonResponse[ImageGenerationData]):
    pass

class ChangeClothesRequest(BaseModel):
    originalPicUrl: str = Field(..., title="原始图片链接", description="需要更改服装的原始图片")
    prompt: str = Field(..., title="替换描述", description="描述要替换成的新服装")
    
class FabricToDesignRequest(BaseModel):
    fabricPicUrl: str = Field(..., title="面料图片链接", description="面料图片链接")
    prompt: str = Field(..., title="替换描述", description="描述要替换成的新服装")
        
class SketchToDesignRequest(BaseModel):
    originalPicUrl: str = Field(..., title="原始图片链接", description="需要更改服装的原始图片")
    prompt: str = Field(..., title="替换描述", description="描述要替换成的新服装")
    referLevel: int = Field(..., title="保真度", description="保真度")

class VirtualTryOnRequest(BaseModel):
    originalPicUrl: str = Field(..., title="原始图片链接", description="需要更改服装的原始图片")
    clothingPhoto: str = Field(..., title="服装图片链接", description="服装图片链接")
    clothType: str = Field(..., title="服装类型", description="服装类型,Value can be 'tops', 'bottoms' or 'one-pieces'")
    
class ChangeClothesResponse(CommonResponse[ImageGenerationData]):
    pass

class FabricToDesignResponse(CommonResponse[ImageGenerationData]):
    pass

class VirtualTryOnResponse(CommonResponse[ImageGenerationData]):
    pass

class GetImageHistoryRequest(BaseModel):
    pageNum: int = Field(1, description="页码，从1开始")
    pageSize: int = Field(10, description="每页数量")
    type: Optional[int] = Field(None, description="生成类型：1-文生图 2-图生图")

class ImageHistoryItem(BaseModel):
    genImgId: int = Field(..., description="图片ID")
    genId: int = Field(..., description="记录ID")
    type: int = Field(..., description="生成类型：1-文生图 2-图生图")
    variationType: Optional[int] = Field(None, description="变化类型：1-洗图 2-更换服装")
    status: int = Field(..., description="状态：1-待生成 2-生成中 3-已生成 4-生成失败")
    resultPic: str = Field(..., description="生成结果图片")
    createTime: str = Field(..., description="创建时间")

class ImageHistoryData(BaseModel):
    total: int = Field(..., description="总记录数")
    list: List[ImageHistoryItem] = Field(..., description="记录列表")

class GetImageHistoryResponse(CommonResponse[ImageHistoryData]):
    pass

class GetImageDetailRequest(BaseModel):
    genImgId: int = Field(..., description="图片ID")

class ImageDetailData(BaseModel):
    genImgId: int = Field(..., description="图片ID")
    genId: int = Field(..., description="记录ID")
    type: int = Field(..., description="生成类型：1-文生图 2-图生图")
    variationType: Optional[int] = Field(None, description="变化类型：1-洗图 2-更换服装")
    prompt: Optional[str] = Field(None, description="原始提示词")
    originalPicUrl: Optional[str] = Field(None, description="原始图片URL")
    resultPic: str = Field(..., description="生成结果图片")
    status: int = Field(..., description="状态：1-待生成 2-生成中 3-已生成 4-生成失败")
    createTime: str = Field(..., description="创建时间")
    withHumanModel: Optional[int] = Field(None, description="是否使用人物模特")
    gender: Optional[int] = Field(None, description="性别")
    age: Optional[int] = Field(None, description="年龄")
    country: Optional[str] = Field(None, description="国家")
    modelSize: Optional[int] = Field(None, description="模特身材")
    fidelity: Optional[float] = Field(None, description="保真度，洗图时使用")

class GetImageDetailResponse(CommonResponse[ImageDetailData]):
    pass

class RefreshImageStatusRequest(BaseModel):
    genImgIdListId: List[int] = Field(default=[], description="图片ID列表")

class RefreshImageStatusDataItem(BaseModel):
    genImgId: int = Field(..., description="图片ID")
    genId: int = Field(..., description="记录ID")
    type: int = Field(..., description="生成类型：1-文生图 2-图生图")
    variationType: Optional[int] = Field(None, description="变化类型：1-洗图 2-更换服装")
    resultPic: str = Field(..., description="生成结果图片")
    status: int = Field(..., description="状态：1-待生成 2-生成中 3-已生成 4-生成失败")
    createTime: str = Field(..., description="创建时间")

class RefreshImageStatusData(BaseModel):
    list: List[RefreshImageStatusDataItem] = Field(..., description="记录列表")

class RefreshImageStatusResponse(CommonResponse[RefreshImageStatusData]):
    pass 