from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")

class CommonResponse(BaseModel, Generic[DataT]):
    code: int = 0
    msg: str = "success"
    data: Optional[DataT] = None 