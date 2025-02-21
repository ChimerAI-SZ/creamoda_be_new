from src.config.log_config import logger
from fastapi import FastAPI
from src.config.config import settings
from src.api.v1 import auth
from src.middleware.log_middleware import log_middleware

app = FastAPI(
    title=settings.api.project_name,
    openapi_url=None
)
logger.info("FastAPI 应用已启动")

# 添加中间件
app.middleware("http")(log_middleware)

# 注册路由
app.include_router(
    auth.router,
    prefix=f"{settings.api.v1_str}/auth",
    tags=["authentication"]
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True) 