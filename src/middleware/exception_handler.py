from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..config.log_config import logger
from ..dto.common import CommonResponse
from ..exceptions.base import CustomException


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_messages = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        message = f"{field}: {error['msg']}"
        error_messages.append(message)
    
    # 组合所有错误信息
    error_msg = "; ".join(error_messages)
    
    # 返回自定义格式的响应
    return JSONResponse(
        status_code=422,  # 保持相同的状态码
        content=CommonResponse(
            code=40001,  # 您可以为验证错误定义一个特定的错误代码
            msg=error_msg or "parameter validation error"
        ).model_dump()
    )

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