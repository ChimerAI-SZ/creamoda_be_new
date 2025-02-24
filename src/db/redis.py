from functools import lru_cache

from redis import Redis

from ..config.config import settings


@lru_cache()
def get_redis() -> Redis:
    """获取Redis连接"""
    return Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password,
        db=settings.redis.db,
        decode_responses=True  # 自动解码响应
    )

# 创建全局Redis客户端实例
redis_client = get_redis() 