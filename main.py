from fastapi import FastAPI
from src.api.v1 import auth, user
from src.config.config import settings
from src.config.log_config import logger
from src.middleware.exception_handler import exception_handler
from src.middleware.log_middleware import log_middleware
from src.middleware.auth_middleware import AuthMiddleware

app = FastAPI(
    title=settings.api.project_name,
    openapi_url=None
)
logger.info("FastAPI 应用已启动")

# 添加中间件
app.middleware("http")(log_middleware)

# 添加异常处理器
app.add_exception_handler(Exception, exception_handler)

# 添加认证中间件
app.middleware("http")(AuthMiddleware([
    "/api/v1/user/info",
    "/api/v1/user/logout",
    "/api/v1/img/*",  # 所有图片相关接口
]).
__call__)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True) 