

from datetime import datetime, timedelta
from requests import Session
from calendar import monthrange

from src.pay.paypal_client import paypal_client
from src.constants.order_status import OrderStatus
from src.constants.order_type import OrderType
from src.constants.subscribe_action import SubscribeAction
from src.core.context import get_current_user_context
from src.exceptions.base import CustomException
from src.exceptions.user import AuthenticationError
from src.models.models import BillingHistory, Credit, CreditHistory, Subscribe, SubscribeHistory
from src.services.order_service import OrderService
from src.config.log_config import logger


class SubscribeService:
    @staticmethod
    async def create_subscribe_order(db: Session, uid: int, level: int):
        # 检查用户是否已经订阅
        subscribe = db.query(Subscribe).filter(Subscribe.uid == uid).first()
        if subscribe and subscribe.level != 0:
            raise CustomException(code=400, message="User already subscribed")
        
        if level == 1:
            order_type = OrderType.BASIC_MEMBERSHIP
        elif level == 2:
            order_type = OrderType.PRO_MEMBERSHIP
        elif level == 3:
            order_type = OrderType.ENTERPRISE_MEMBERSHIP
        else:
            raise CustomException(code=400, message="Invalid order type")
        
        # 创建订单
        order_res = await OrderService.create_subscribe_order(db, uid, order_type)
        
        return order_res

    @staticmethod
    async def launch_subscribe(db: Session, uid: int, orderId: str, level: int):
        try:
            # 获取当前用户信息
            user = get_current_user_context()
            if not user:
                raise AuthenticationError()
            
            # 检查用户是否已经订阅
            subscribe = db.query(Subscribe).filter(Subscribe.uid == uid).first()
            if subscribe and subscribe.level != 0:
                logger.info(f"User {uid} already subscribed")
                raise CustomException(code=400, message="User already subscribed")
            
            today = datetime.now()
            today_midnight = datetime.combine(today.date(), datetime.time(0, 0, 0))
            renew_date = SubscribeService.calculate_next_billing_date(today_midnight)
            renew_date_last_second = datetime.combine(renew_date.date(), datetime.time(23, 59, 59))

            # 更新订阅状态
            if subscribe:
                subscribe.level = level
                subscribe.paypal_sub_id = orderId
                subscribe.is_renew = 1
                subscribe.sub_start_time = today_midnight
                subscribe.sub_end_time = renew_date_last_second
                subscribe.renew_date = renew_date
                subscribe.update_time = today
            else:
                subscribe = Subscribe(
                    uid=uid,
                    paypal_sub_id = orderId,
                    level=level,
                    is_renew=1,
                    sub_start_time=today_midnight,
                    sub_end_time=renew_date_last_second,
                    renew_date=renew_date,
                    billing_email=user.email,
                    create_time=datetime.now(),
                    update_time=datetime.now()
                )
                db.add(subscribe)
            
            subscribe_history = SubscribeHistory(
                uid=uid,
                level=level,
                action=SubscribeAction.LAUNCH,
                create_time=datetime.now()
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
                    create_time=datetime.now(),
                    update_time = datetime.now()
                    )
                db.add(credit)

            # 新增积分记录
            credit_history = CreditHistory(
                uid=uid,
                credit_change=launch_points,
                source="subscribe",
                create_time=datetime.now()
            )
            db.add(credit_history)

            # 更新订单状态
            billing_history = db.query(BillingHistory).filter(BillingHistory.uid == uid, BillingHistory.order_id == orderId).first()
            if not billing_history:
                raise CustomException(code=400, message="Billing history not found")
            billing_history.status = OrderStatus.PAYMENT_SUCCESS
            billing_history.update_time = datetime.now()
            db.commit()
        except Exception as e:
            logger.error(f"Launch subscribe failed: {e}")
            db.rollback()
            raise CustomException(code=400, message="Launch subscribe failed")

    @staticmethod
    def calculate_next_billing_date(start_date: datetime, months: int = 1) -> datetime:
        year = start_date.year
        month = start_date.month + months
        while month > 12:
            month -= 12
            year += 1

        day = start_date.day

        # 获取目标月份的最后一天
        last_day = monthrange(year, month)[1]
        day = min(day, last_day)

        return datetime(year, month, day)

    @staticmethod
    async def cancel_subscribe(db: Session, uid: int):
        # 检查用户是否已经订阅
        try:
            subscribe = db.query(Subscribe).filter(Subscribe.uid == uid).first()
            if subscribe or subscribe.level == 0:
                raise CustomException(code=400, message="User not subscribed")
            if subscribe.is_renew == 0:
                raise CustomException(code=400, message="User not subscribed")
            if not subscribe.paypal_sub_id:
                raise CustomException(code=400, message="Paypal subscription id not found")
            
            # 更新订阅状态
            subscribe.is_renew = 0
            subscribe.update_time = datetime.now()
            subscribe.cancel_time = datetime.now()

            subscribe_history = SubscribeHistory(
                uid=uid,
                level=0,
                action=SubscribeAction.CANCEL,
                create_time=datetime.now()
            )
            db.add(subscribe_history)

            # 取消订阅
            res = paypal_client.cancel_subscription(subscribe.paypal_sub_id)
            if not res:
                raise CustomException(code=400, message="Cancel subscription failed")

            db.commit()
        except Exception as e:
            logger.error(f"Cancel subscribe failed: {e}")
            db.rollback()
            raise CustomException(code=400, message="Cancel subscribe failed")

