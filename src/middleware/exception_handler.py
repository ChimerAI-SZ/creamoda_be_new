from fastapi import Request
from fastapi.responses import JSONResponse

from ..config.log_config import logger
from ..dto.common import CommonResponse
from ..exceptions.base import CustomException


async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, CustomException):
        logger.error(f"Custom exception: {exc.message}")
        return JSONResponse(
            status_code=200,  # 按照接口文档，错误也返回200
            content=CommonResponse(
                code=exc.code,
                msg=exc.message,
                data=exc.data
            ).model_dump()
        )
    
    # 处理其他未知异常
    logger.error(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=200,
        content=CommonResponse(
            code=500,
            msg="Internal server error"
        ).model_dump()
    ) 