from functools import lru_cache, wraps
import time
from typing import Any, Callable, Optional, TypeVar, cast

from redis import Redis, ConnectionError, TimeoutError as RedisTimeoutError
from redis.exceptions import RedisError, AuthenticationError

from ..config.config import settings
from ..config.log_config import logger

# 定义返回类型变量
T = TypeVar('T')

# Redis连接超时设置（秒）
REDIS_CONNECT_TIMEOUT = 3
REDIS_SOCKET_TIMEOUT = 5
REDIS_RETRY_COUNT = 3
REDIS_RETRY_DELAY = 0.5

@lru_cache()
def get_redis() -> Redis:
    """获取Redis连接，连接失败时直接抛出异常"""
    try:
        logger.info(f"Connecting to Redis at {settings.redis.host}:{settings.redis.port}")
        
        # 构建Redis连接参数
        redis_params = {
            "host": settings.redis.host,
            "port": settings.redis.port,
            "db": settings.redis.db,
            "decode_responses": True,  # 自动解码响应
            "socket_connect_timeout": REDIS_CONNECT_TIMEOUT,  # 连接超时
            "socket_timeout": REDIS_SOCKET_TIMEOUT,  # 操作超时
            "health_check_interval": 30  # 定期检查连接健康状态
        }
        
        # 添加用户名（如果配置中有）
        if hasattr(settings.redis, 'username') and settings.redis.username:
            redis_params["username"] = settings.redis.username
            logger.info(f"Using Redis username: {settings.redis.username}")
        
        # 添加密码（如果配置中有）
        if settings.redis.password:
            redis_params["password"] = settings.redis.password
            logger.info("Redis password configured")
        
        # 创建Redis客户端
        client = Redis(**redis_params)
        
        # 测试连接
        client.ping()
        logger.info("Successfully connected to Redis")
        return client
    except AuthenticationError as e:
        logger.error(f"Redis authentication failed: {str(e)}")
        raise  # 直接抛出异常
    except (ConnectionError, RedisTimeoutError) as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise  # 直接抛出异常
    except Exception as e:
        logger.error(f"Unexpected error connecting to Redis: {str(e)}")
        raise  # 直接抛出异常

def with_redis_retry(max_retries: int = REDIS_RETRY_COUNT, delay: float = REDIS_RETRY_DELAY) -> Callable:
    """Redis操作重试装饰器"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, RedisTimeoutError) as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Redis operation failed (attempt {attempt+1}/{max_retries}): {str(e)}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"Redis operation failed after {max_retries} attempts: {str(e)}")
                except RedisError as e:
                    logger.error(f"Redis error: {str(e)}")
                    last_error = e
                    break
                except Exception as e:
                    logger.error(f"Unexpected error in Redis operation: {str(e)}")
                    last_error = e
                    break
            
            # 如果所有重试都失败，抛出最后一个错误
            if last_error:
                logger.error(f"All Redis retries failed: {str(last_error)}")
                raise last_error  # 抛出最后一个错误
            return cast(T, None)  # 这行代码实际上不会执行到
        return wrapper
    return decorator

# 创建全局Redis客户端实例
try:
    redis_client = get_redis()
except Exception as e:
    logger.critical(f"Failed to initialize Redis client: {str(e)}")
    # 在应用启动时就抛出异常，确保Redis连接问题立即被发现
    raise

# 示例：如何使用重试装饰器
# @with_redis_retry()
# def get_user_data(user_id: str) -> dict:
#     return redis_client.hgetall(f"user:{user_id}") 