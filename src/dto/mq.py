
from typing import Any, Dict
from pydantic import BaseModel, Field

class MQBaseDto(BaseModel):
    id: str
    type: str
    timestamp: str
    priority: int
    data: dict

class ImageGenerationDto(BaseModel):
    genImgId: int
