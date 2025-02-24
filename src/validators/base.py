from typing import Any, Type, TypeVar

from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)

class BaseValidator:
    @classmethod
    def validate_model(cls, model_type: Type[ModelType], data: Any) -> ModelType:
        """基础模型验证"""
        return model_type.model_validate(data) 