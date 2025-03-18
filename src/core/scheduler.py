from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from src.config.config import settings
from src.config.log_config import logger
from src.db.redis import redis_client

# 配置 job stores
jobstores = {
    'default': RedisJobStore(
        jobs_key='apscheduler.jobs',
        run_times_key='apscheduler.run_times',
        # host=settings.redis.host,
        # port=settings.redis.port,
        # password=settings.redis.password,
        # db=settings.redis.db
        redis=redis_client
    )
}

# 配置执行器
executors = {
    'default': AsyncIOExecutor()
}

job_defaults = {
    'coalesce': settings.scheduler.job_defaults.coalesce,
    'max_instances': settings.scheduler.job_defaults.max_instances,
    'misfire_grace_time': settings.scheduler.job_defaults.misfire_grace_time
}

# 创建调度器
scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    executors=executors,
    job_defaults=job_defaults,
    timezone='Asia/Shanghai'
) 