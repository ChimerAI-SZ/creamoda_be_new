from typing import Any, Dict, Optional

from .base import CustomException

class ServerError(CustomException):
    def __init__(self, message: str = "Server error", data: Optional[Dict[str, Any]] = None):
        super().__init__(code=500, message=message, data=data)

class ValidationError(CustomException):
    def __init__(self, message: str = "Validation error", data: Optional[Dict[str, Any]] = None):
        super().__init__(code=400, message=message, data=data)

class AuthenticationError(CustomException):
    def __init__(self, message: str = "Authentication failed", data: Optional[Dict[str, Any]] = None):
        super().__init__(code=401, message=message, data=data) 

class EmailVerifiedError(CustomException):
    def __init__(self, message: str = "Email not verified", data: Optional[Dict[str, Any]] = None):
        super().__init__(code=402, message=message, data=data) 

class UserInfoError(CustomException):
    def __init__(self, message: str = "User info error", data: Optional[Dict[str, Any]] = None):
        super().__init__(code=403, message=message, data=data) 