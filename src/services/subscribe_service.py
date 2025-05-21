

import datetime
from requests import Session

from src.constants.order_status import OrderStatus
from src.constants.order_type import OrderType
from src.constants.subscribe_action import SubscribeAction
from src.exceptions.base import CustomException
from src.models.models import BillingHistory, Credit, CreditHistory, Subscribe, SubscribeHistory
from src.services.order_service import OrderService
from src.config.log_config import logger


class SubscribeService:
    @staticmethod
    async def create_subscribe_order(db: Session, uid: int, level: int):
        # 检查用户是否已经订阅
        subscribe = db.query(Subscribe).filter(Subscribe.uid == uid).first()
        if subscribe and subscribe.level == level:
            raise CustomException(status_code=400, detail="User already subscribed")
        
        if level == 1:
            order_type = OrderType.BASIC_MEMBERSHIP
        elif level == 2:
            order_type = OrderType.PRO_MEMBERSHIP
        elif level == 3:
            order_type = OrderType.ENTERPRISE_MEMBERSHIP
        else:
            raise CustomException(status_code=400, detail="Invalid order type")
        
        # 创建订单
        order_res = await OrderService.create_order(db, uid, order_type)
        
        return order_res

    @staticmethod
    async def launch_subscribe(db: Session, uid: int, order_id: int, level: int):
        try:
            # 检查用户是否已经订阅
            subscribe = db.query(Subscribe).filter(Subscribe.uid == uid).first()
            if subscribe and subscribe.level == level:
                logger.info(f"User {uid} already subscribed")
                raise CustomException(status_code=400, detail="User already subscribed")
            
            today = datetime.now()

            # 更新订阅状态
            if subscribe:
                subscribe.level = level
                subscribe.sub_time = today
                renew_date = today + datetime.timedelta(days=31)
                renew_date_midnight = datetime.combine(renew_date.date(), datetime.time(0, 0, 0))
                subscribe.renew_time = renew_date_midnight
                subscribe.update_time = today

            # 创建订阅历史
            subscribe_history = SubscribeHistory(
                uid=uid,
                level=level,
                action=SubscribeAction.LAUNCH,
                created_time=datetime.now()
            )
            db.add(subscribe_history)

            # 发放积分
            launch_points = 0
            if level == 1:
                launch_points = 200
            elif level == 2:
                launch_points = 400
            elif level == 3:
                launch_points = 800

            # 更新积分
            credit = db.query(Credit).filter(Credit.uid == uid).first()
            if credit:
                credit.credit += launch_points
                credit.update_time = datetime.now()
            else:
                credit = Credit(
                    uid=uid,
                    credit=launch_points,
                    lock_credit=0,
                    created_time=datetime.now(),
                    update_time = datetime.now()
                    )
                db.add(credit)

            # 新增积分记录
            credit_history = CreditHistory(
                uid=uid,
                credit_change=launch_points,
                source="subscribe",
                created_time=datetime.now()
            )
            db.add(credit_history)

            # 更新订单状态
            billing_history = db.query(BillingHistory).filter(BillingHistory.uid == uid, BillingHistory.order_id == order_id).first()
            if not billing_history:
                raise CustomException(status_code=400, detail="Billing history not found")
            billing_history.status = OrderStatus.PAYMENT_SUCCESS
            billing_history.update_time = datetime.now()
            db.commit()
        except Exception as e:
            logger.error(f"Launch subscribe failed: {e}")
            db.rollback()
            raise CustomException(status_code=400, detail="Launch subscribe failed")
