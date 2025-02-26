from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Callable, Any

from ..dto.common import CommonResponse
from ..exceptions.base import CustomException
from ..config.log_config import logger

async def api_exception_middleware(request: Request, call_next: Callable) -> Any:
    """API异常拦截中间件
    
    捕获API请求处理过程中的异常，并按照规范格式返回响应
    """
    try:
        # 继续处理请求
        return await call_next(request)
    
    except CustomException as e:
        # 捕获业务自定义异常
        logger.warning(
            f"业务异常: {e.__class__.__name__}, 代码: {e.code}, 消息: {e.message}, "
            f"路径: {request.url.path}, 方法: {request.method}"
        )
        
        # 构建标准响应
        return JSONResponse(
            status_code=200,  # 业务异常使用200状态码，通过code字段区分
            content=CommonResponse(
                code=e.code,
                msg=e.message,
                data=e.data
            ).model_dump()
        )
        
    except Exception as e:
        # 捕获其他未预期的异常
        error_message = str(e)
        logger.exception(
            f"未预期异常: {error_message}, "
            f"路径: {request.url.path}, 方法: {request.method}"
        )
        
        # 构建标准错误响应
        return JSONResponse(
            status_code=500,
            content=CommonResponse(
                code=500,
                msg=f"服务器内部错误: {error_message}" if logger.level <= 20 else "服务器内部错误"
            ).model_dump()
        ) 