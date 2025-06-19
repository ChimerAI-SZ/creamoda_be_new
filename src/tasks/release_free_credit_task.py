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
from src.models.models import BillingHistory, Credit, CreditHistory, UserInfo

async def process_release_free_credit():
    """释放免费积分任务"""
    with get_db() as db:
        try:
            # 批量更新用户积分
            # 分页大小
            page_size = 100
            page = 0
            
            while True:
                # 获取当前页的用户
                users = db.query(UserInfo).filter(UserInfo.status == 1).offset(page * page_size).limit(page_size).all()
                
                if not users:
                    break
                    
                for user in users:
                    await release_free_credit_to_user(user.id, db)
                
                # 提交当前页的更改
                db.commit()
                page += 1
            
            logger.info("Free credit release task completed successfully")
            
        except Exception as e:
            logger.error(f"Error during free credit release: {str(e)}")
            db.rollback()
        finally:
            db.close()

async def release_free_credit_to_user(userId: int, db: Session):
    """释放免费积分到用户"""
    try:
        billing_history = db.query(BillingHistory).filter(BillingHistory.uid == userId, BillingHistory.status == OrderStatus.PAYMENT_SUCCESS).first()
        if billing_history:
            return
        
        try:
            credit = db.query(Credit).filter(Credit.uid == userId).with_for_update(nowait=True).first()
        except OperationalError as e:
            logger.warning(f"Failed to acquire lock for user {userId}: {str(e)}")
            raise CustomException(code=409, message="Resource is locked, please try again later")
        if credit:
            if credit.credit >= 5:
                return
            else:
                credit_add = 5 - (credit.credit)
                credit.credit += credit_add
                creditHistory = CreditHistory(uid=userId, credit_change=credit_add, source="每日积分发放", create_time=datetime.now())
                db.add(creditHistory)
        else:
            credit = Credit(uid=userId, credit=5, lock_credit=0, create_time=datetime.now(), update_time=datetime.now())
            db.add(credit)
            creditHistory = CreditHistory(uid=userId, credit_change=5, source="每日积分发放", create_time=datetime.now())
            db.add(creditHistory)
        
        db.commit()
    except Exception as e:
        logger.error(f"Error during release free credit to user: {str(e)}")
        db.rollback()

def release_free_credit_task():
    """同步版本的任务入口，用于调度器调用"""
    lock = Lock(redis_client, "release_free_credit_task_lock", timeout=300)
    
    if not lock.acquire(blocking=False):
        logger.info("Previous task is still running, skipping this execution")
        return
    try:
        # 检查是否已有事件循环在运行
        try:
            loop = asyncio.get_running_loop()
            # 如果有事件循环在运行，使用 create_task
            asyncio.create_task(process_release_free_credit())
        except RuntimeError:
            # 如果没有事件循环在运行，创建新的
            asyncio.run(process_release_free_credit())
    except Exception as e:
        logger.error(f"Error in process_release_free_credit: {str(e)}")
    finally:
        lock.release()