from fastapi import FastAPI
from src.api.v1 import auth, user, img, common
from src.config.config import settings
from src.config.log_config import logger
from src.core.rabbitmq_manager import rabbitmq_manager
from src.core.task_manager import TaskManager
from src.core.middleware_manager import MiddlewareManager
from src.core.router_manager import RouterManager

app = FastAPI(
    title=settings.api.project_name,
    # openapi_url="/api/v1/openapi.json"
     openapi_url=None
)

logger.info("FastAPI 应用已启动")

# 添加根路径路由
# @app.get("/")
# async def root():
#     """根路径健康检查"""
#     return {"message": "Creamoda Backend API is running", "status": "ok"}

# @app.get("/health")
# async def health_check():
#     """健康检查端点"""
#     return {"status": "healthy", "service": "creamoda-backend"}

MiddlewareManager.setup_middlewares(app)
RouterManager.register_routers(app)

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化操作"""
    await TaskManager.initialize_tasks()
    await TaskManager.start_scheduler()
    await rabbitmq_manager.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理操作"""
    await TaskManager.shutdown_scheduler()
    await rabbitmq_manager.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)