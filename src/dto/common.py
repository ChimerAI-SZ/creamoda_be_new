from typing import Generic, Optional, TypeVar
from fastapi import UploadFile, File, Form
from pydantic import BaseModel, Field

from pydantic import BaseModel

DataT = TypeVar("DataT")

class CommonResponse(BaseModel, Generic[DataT]):
    code: int = 0
    msg: str = "success"
    data: Optional[DataT] = None 

class UploadResponse(BaseModel):
    url: str = Field(..., description="上传后的文件URL")
    filename: str = Field(..., description="文件名")

class UploadImageResponse(CommonResponse[UploadResponse]):
    pass 