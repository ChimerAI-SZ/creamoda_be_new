from typing import Any, Dict, Optional

from .base import CustomException

class AlgError(CustomException):
    def __init__(self, message: str = "Alg error", data: Optional[Dict[str, Any]] = None):
        super().__init__(code=600, message=message, data=data)