from pydantic import BaseModel, Field
from typing import Optional, List
from .common import CommonResponse

class TextToImageRequest(BaseModel):
    prompt: str = Field(..., title="提示词")
    withHumanModel: int = Field(..., title="使用人类模特", description="1-使用 0-不使用")  
    gender: int = Field(..., title="模特性别", description="1-男 2-女")
    age: int = Field(..., title="年龄")
    country: str = Field(..., title="国家code")
    modelSize: int = Field(..., title="模特身材code")

class ImageGenerationData(BaseModel):
    taskId: str
    status: int = Field(..., description="任务状态：1-待生成 2-生成中 3-已生成")
    estimatedTime: int = Field(..., description="预计完成时间(秒)")

class TextToImageResponse(CommonResponse[ImageGenerationData]):
    pass

class CopyStyleRequest(BaseModel):
    originalPicUrl: str = Field(..., title="原始图片链接", description="图转图 或细节修改传递")
    fidelity: float = Field(..., description="仅洗图填写", title="保真度")
    prompt: str = Field(..., title="提示词")

class CopyStyleResponse(CommonResponse[ImageGenerationData]):
    pass

class ChangeClothesRequest(BaseModel):
    originalPicUrl: str = Field(..., title="原始图片链接", description="需要更改服装的原始图片")
    prompt: str = Field(..., title="替换描述", description="描述要替换成的新服装")
    
class ChangeClothesResponse(CommonResponse[ImageGenerationData]):
    pass 