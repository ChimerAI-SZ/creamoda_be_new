"""
路由管理模块，负责所有API路由的注册和配置
"""

from fastapi import FastAPI
from src.config.config import settings
from src.config.log_config import logger
from src.api.v1 import auth, user, img, common, collect

class RouterManager:
    """路由管理器，处理所有API路由的注册"""
    
    @staticmethod
    def register_routers(app: FastAPI) -> None:
        """注册所有API路由
        
        Args:
            app: FastAPI应用实例
        """
        try:
            logger.info("Registering API routers...")
            
            # 注册认证路由
            app.include_router(
                auth.router,
                prefix=f"{settings.api.v1_str}/auth",
                tags=["authentication"]
            )
            logger.info("Registered authentication router")
            
            # 注册用户路由
            app.include_router(
                user.router,
                prefix=f"{settings.api.v1_str}/user",
                tags=["user"]
            )
            logger.info("Registered user router")
            
            # 注册图像路由
            app.include_router(
                img.router,
                prefix=f"{settings.api.v1_str}/img",
                tags=["image"]
            )
            logger.info("Registered image router")
            
            # 注册图像路由
            app.include_router(
                collect.router,
                prefix=f"{settings.api.v1_str}/collect",
                tags=["collect"]
            )
            logger.info("Registered collect router")

            # 注册通用路由
            app.include_router(
                common.router,
                prefix=f"{settings.api.v1_str}/common",
                tags=["common"]
            )
            logger.info("Registered common router")
            
            # 这里可以注册更多路由...
            
            logger.info("All API routers registered successfully")
        except Exception as e:
            logger.error(f"Failed to register API routers: {str(e)}")
            raise 