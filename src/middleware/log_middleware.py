import time

from fastapi import Request
from src.config.log_config import logger


async def log_middleware(request: Request, call_next):
    """记录每个 HTTP 请求的日志"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        f"{request.client.host} - {request.method} {request.url.path} - {response.status_code} "
        f" cost time: ({process_time:.2f}s)"
    )
    return response