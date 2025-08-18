import sys
import os
import threading
import asyncio
from pathlib import Path

from loguru import logger

# 移除默认 logger
logger.remove()

# 定义拦截器函数，添加线程ID和协程ID
def add_thread_and_task_info(record):
    # 添加线程ID
    record["extra"]["thread_id"] = threading.get_ident()
    
    # 尝试获取当前协程ID，如果在协程中运行
    try:
        # 获取当前运行的协程/任务
        task = asyncio.current_task()
        if task:
            # 使用任务名称或任务ID
            record["extra"]["task_id"] = task.get_name() if hasattr(task, 'get_name') else id(task)
        else:
            record["extra"]["task_id"] = "None"
    except (RuntimeError, ImportError):
        # 如果不在协程环境中，或者asyncio不可用
        record["extra"]["task_id"] = "None"
    
    return record

# 配置日志格式
log_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
    "[<level>{level}</level>] "
    "[Thread:{extra[thread_id]}] "
    "[Task:{extra[task_id]}] "
    "[<cyan>{name}</cyan>:<cyan>{line}</cyan>] - "
    "<level>{message}</level>"
)

# 添加控制台处理器
logger.configure(patcher=add_thread_and_task_info)  # 配置拦截器
logger.add(
    sys.stdout,
    format=log_format,
    level="INFO",  # 恢复INFO级别，生产环境不需要DEBUG
)

# 普通日志文件（INFO 级别及以上）
logger.add(
    "logs/app.log",
    format=log_format,
    level="INFO",
    rotation="1 day",     # 每天轮转
    retention="30 days",  # 保留30天
    encoding="utf-8",
)

# 错误日志文件（ERROR 及以上级别）
logger.add(
    "logs/error.log",
    format=log_format,
    level="ERROR",
    rotation="1 week",    # 每周轮转
    retention="30 days",  # 保留30天
    encoding="utf-8",
)

# 抑制第三方库的日志
# 注意：这需要结合拦截标准库日志的方式
# 如果其他库使用标准库logging，可以通过以下方式拦截到loguru
# import logging
# class InterceptHandler(logging.Handler):
#     def emit(self, record):
#         logger_opt = logger.opt(depth=6, exception=record.exc_info)
#         logger_opt.log(record.levelname, record.getMessage())
#
# logging.getLogger().addHandler(InterceptHandler())
# for name in ["uvicorn", "fastapi", "sqlalchemy"]:
#     logging.getLogger(name).setLevel(logging.WARNING)
