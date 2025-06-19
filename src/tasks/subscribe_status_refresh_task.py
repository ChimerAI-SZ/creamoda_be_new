from redis.lock import Lock
import asyncio
from datetime import datetime

from pymysql import OperationalError
from src.constants.order_status import OrderStatus
from src.db.session import SessionLocal, get_db
from sqlalchemy.orm import Session
from src.config.log_config import logger
from src.db.redis import redis_client
from src.exceptions.base import CustomException
from src.models.models import BillingHistory, Credit, CreditHistory, Subscribe, UserInfo

async def process_subscribe_status_refresh():
    """释放免费积分任务"""
    db = get_db()
    try:
        # 批量更新用户积分
        # 分页大小
        page_size = 100
        page = 0
        
        while True:
            # 获取当前页的用户
            subs = db.query(Subscribe).filter(Subscribe.level != 0).offset(page * page_size).limit(page_size).all()
            
            if not subs:
                break
                
            for sub in subs:
                await refresh_subscribe_status(sub, db)
            
            # 提交当前页的更改
            db.commit()
            page += 1
        
        logger.info("Subscribe status refresh task completed successfully")
        
    except Exception as e:
        logger.error(f"Error during subscribe status refresh: {str(e)}")
        db.rollback()
    finally:
        db.close()

async def refresh_subscribe_status(sub: Subscribe, db: Session):
    """刷新订阅状态"""
    now = datetime.now()
    if sub.sub_end_time < now:
        sub.level = 0
        sub.update_time = now
        db.commit()

def subscribe_status_refresh_task():
    """同步版本的任务入口，用于调度器调用"""
    lock = Lock(redis_client, "subscribe_status_refresh_task_lock", timeout=300)
    
    if not lock.acquire(blocking=False):
        logger.info("Previous task is still running, skipping this execution")
        return
    try:
        # 检查是否已有事件循环在运行
        try:
            loop = asyncio.get_running_loop()
            # 如果有事件循环在运行，使用 create_task
            asyncio.create_task(process_subscribe_status_refresh())
        except RuntimeError:
            # 如果没有事件循环在运行，创建新的
            asyncio.run(process_subscribe_status_refresh())
    except Exception as e:
        logger.error(f"Error in process_subscribe_status_refresh: {str(e)}")
    finally:
        lock.release()