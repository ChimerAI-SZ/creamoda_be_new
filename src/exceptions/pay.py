from typing import Any, Dict, Optional

from .base import CustomException

class PayError(CustomException):
    def __init__(self, message: str = "Pay error", data: Optional[Dict[str, Any]] = None):
        super().__init__(code=700, message=message, data=data)
