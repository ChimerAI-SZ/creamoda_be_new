from loguru import logger
import sys

# 移除默认 logger
logger.remove()

# 终端日志（INFO 级别及以上）
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    level="INFO",
)

# 普通日志文件（INFO 级别及以上）
logger.add(
    "logs/app.log",
    rotation="1 day",  # 每天轮转
    retention="30 days",  # 仅保留最近30天
    level="INFO",
    encoding="utf-8",
)

# 错误日志文件（ERROR 及以上级别）
logger.add(
    "logs/error.log",
    rotation="1 week",  # 每周轮转
    retention="30 days",  # 仅保留最近30天
    level="ERROR",  # 只记录 ERROR 及以上级别日志
    encoding="utf-8",
)
