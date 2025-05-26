"""
定时任务管理模块，负责所有调度任务的初始化、启动和关闭
"""

from typing import Dict, Any, Optional
from src.core.scheduler import scheduler
from src.config.config import settings
from src.config.log_config import logger
from src.tasks.img_generation_task import img_generation_compensate_task
from src.tasks.release_free_credit_task import release_free_credit_task
from src.tasks.subscribe_status_refresh_task import subscribe_status_refresh_task

class TaskManager:
    """定时任务管理器，处理调度器的生命周期和任务配置"""
    
    @staticmethod
    async def initialize_tasks():
        """初始化所有定时任务，但不启动调度器"""
        try:
            logger.info("Initializing scheduled tasks...")
            
            # 获取图像补偿任务的配置
            # 直接使用 settings 对象读取值
            try:
                img_compensate_enabled = settings.scheduler.tasks.image_compensate.enabled
            except (AttributeError, KeyError):
                img_compensate_enabled = True  # 默认启用
                
            try:
                img_compensate_interval = settings.scheduler.tasks.image_compensate.interval_seconds
            except (AttributeError, KeyError):
                img_compensate_interval = 30  # 默认30秒
            
            if img_compensate_enabled:
                # 添加图像生成补偿定时任务
                scheduler.add_job(
                    img_generation_compensate_task,
                    'interval',
                    seconds=img_compensate_interval,
                    id='img_generation_compensate_task',
                    replace_existing=True,
                )
                logger.info(f"Added image generation compensate task with interval {img_compensate_interval}s")
            else:
                logger.info("Image generation compensate task is disabled in configuration")

            # 新每天凌晨免费积分发放任务配置
            try:
                release_free_credit_task_enabled = settings.scheduler.tasks.release_free_credit_task.enabled
            except (AttributeError, KeyError):
                release_free_credit_task_enabled = True
                
            if release_free_credit_task_enabled:
                scheduler.add_job(
                    release_free_credit_task,
                    'cron',
                    hour=0,
                    minute=0,
                    id='release_free_credit_task',
                    replace_existing=True,
                )
                logger.info("Added release free credit task")
            else:
                logger.info("Release free credit task is disabled in configuration")
            
            # 新每天凌晨订阅状态刷新任务配置
            try:
                subscribe_status_refresh_task_enabled = settings.scheduler.tasks.subscribe_status_refresh_task.enabled
            except (AttributeError, KeyError):
                subscribe_status_refresh_task_enabled = True
                
            if subscribe_status_refresh_task_enabled:
                scheduler.add_job(
                    subscribe_status_refresh_task,
                    'cron',
                    hour=0,
                    minute=0,
                    id='subscribe_status_refresh_task',
                    replace_existing=True,
                )
                logger.info("Added subscribe status refresh task")
            else:
                logger.info("Subscribe status refresh task is disabled in configuration")

            # 这里可以添加更多的定时任务，根据配置文件控制是否启用
            # ...
            
            logger.info("Scheduled tasks initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize scheduled tasks: {str(e)}")
            return False
    
    @staticmethod
    async def start_scheduler():
        """启动调度器，开始执行所有定时任务"""
        try:
            # 直接尝试访问配置项
            try:
                scheduler_enabled = settings.scheduler.enabled
            except (AttributeError, KeyError):
                scheduler_enabled = True  # 默认启用
            
            if not scheduler_enabled:
                logger.info("Scheduler is disabled in configuration")
                return True
            
            # 启动调度器
            scheduler.start()
            logger.info("APScheduler started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start APScheduler: {str(e)}")
            return False
    
    @staticmethod
    async def shutdown_scheduler():
        """关闭调度器，停止所有定时任务"""
        try:
            if scheduler.running:
                scheduler.shutdown()
                logger.info("APScheduler shutdown completed")
            else:
                logger.info("APScheduler was not running")
            return True
        except Exception as e:
            logger.error(f"Error during APScheduler shutdown: {str(e)}")
            return False
    