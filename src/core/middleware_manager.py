"""
中间件管理模块，负责所有中间件的注册和配置
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from src.config.config import settings
from src.config.log_config import logger
from src.middleware.exception_handler import exception_handler, validation_exception_handler
from src.middleware.log_middleware import log_middleware
from src.middleware.auth_middleware import AuthMiddleware
from src.middleware.rate_limit_middleware import RateLimitMiddleware

class MiddlewareManager:
    """中间件管理器，处理所有中间件的注册"""
    
    @staticmethod
    def setup_middlewares(app: FastAPI) -> None:
        """设置所有中间件
        
        Args:
            app: FastAPI应用实例
        """
        try:
            logger.info("Registering middlewares...")
            
            # 添加全局异常处理器
            app.add_exception_handler(RequestValidationError, validation_exception_handler)
            app.add_exception_handler(Exception, exception_handler)
            logger.info("Registered global exception handler")
            
            # 添加日志中间件
            app.middleware("http")(log_middleware)
            logger.info("Registered log middleware")
            
            # 添加认证中间件
            protected_paths = [
                "/api/v1/user/info",
                "/api/v1/user/logout",
                "/api/v1/user/change/user_info",
                "/api/v1/img/*",  # 所有图片相关接口
                "/api/v1/collect/*",  # 所有收藏相关接口
                "/api/v1/pay/*",  # 所有支付相关接口
                "/api/v1/paypal/capture",  # paypal捕获接口
                "/api/v1/common/contact",
                "/api/v1/common/img/upload",
                "/api/v1/common/enum/*"  # 枚举接口公开访问
            ]
            
            # 从配置中获取额外的受保护路径
            try:
                extra_protected_paths = settings.security.extra_protected_paths
                if extra_protected_paths:
                    protected_paths.extend(extra_protected_paths)
            except (AttributeError, KeyError):
                pass
            
            app.middleware("http")(AuthMiddleware(protected_paths).__call__)
            logger.info(f"Registered auth middleware with {len(protected_paths)} protected paths")
            
            # 限流中间件放在认证中间件之后注册，确保先认证再限流
            app.middleware("http")(RateLimitMiddleware())
            logger.info("Registered rate limit middleware")
            
            
            
            logger.info("All middlewares registered successfully")
        except Exception as e:
            logger.error(f"Failed to setup middlewares: {str(e)}")
            raise