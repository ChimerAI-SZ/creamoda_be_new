from fastapi import FastAPI
from src.api.v1 import auth, user, img, common
from src.config.config import settings
from src.config.log_config import logger
from src.middleware.exception_handler import exception_handler
from src.middleware.log_middleware import log_middleware
from src.middleware.auth_middleware import AuthMiddleware
from src.middleware.api_exception_middleware import api_exception_middleware
from src.core.scheduler import scheduler
from src.tasks.img_generation_task import img_generation_compensate_task
from src.middleware.rate_limit_middleware import RateLimitMiddleware

app = FastAPI(
    title=settings.api.project_name,
    openapi_url=None
)

logger.info("FastAPI 应用已启动")

# 添加其他中间件
app.middleware("http")(api_exception_middleware)
app.middleware("http")(log_middleware)

# 添加认证中间件
app.middleware("http")(AuthMiddleware([
    "/api/v1/user/info",
    "/api/v1/user/logout",
    "/api/v1/img/*",  # 所有图片相关接口
    "/api/v1/common/contact",
    "/api/v1/common/img/upload",
    "/api/v1/common/enum/*"  # 枚举接口公开访问
]).__call__)

# 限流中间件放在认证中间件之后注册，确保先认证再限流
app.middleware("http")(RateLimitMiddleware())  # 添加限流中间件

# 添加异常处理器
app.add_exception_handler(Exception, exception_handler)

# 注册路由
app.include_router(
    auth.router,
    prefix=f"{settings.api.v1_str}/auth",
    tags=["authentication"]
)

# 添加用户路由
app.include_router(
    user.router,
    prefix=f"{settings.api.v1_str}/user",
    tags=["user"]
)

# 添加图像路由
app.include_router(
    img.router,
    prefix=f"{settings.api.v1_str}/img",
    tags=["image"]
)

# 添加通用路由
app.include_router(
    common.router,
    prefix=f"{settings.api.v1_str}/common",
    tags=["common"]
)

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化操作"""
    
    # 添加图像生成补偿定时任务
    scheduler.add_job(
        img_generation_compensate_task,
        'interval',
        seconds=30,  # 每30秒执行一次
        id='img_generation_compensate_task',  # 任务唯一标识
        replace_existing=True  # 如果任务已存在则替换
    )
    
    # 启动调度器
    # todo revert
    # scheduler.start()
    logger.info("APScheduler started")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理操作"""
    scheduler.shutdown()
    logger.info("APScheduler shutdown")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 