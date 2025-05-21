

from datetime import datetime
from requests import Session

from src.constants.credit_point_value import PointValue
from src.constants.order_status import OrderStatus
from src.constants.order_type import OrderType
from src.exceptions.base import CustomException
from src.models.models import BillingHistory, Credit, CreditHistory
from src.services.order_service import OrderService
from src.config.log_config import logger

class CreditService:
    @staticmethod
    async def create_credit_order(db: Session, uid: int, amount: int):
        # 创建订单
        if amount == PointValue.POINT_40:
            order_type = OrderType.POINTS_40
        elif amount == PointValue.POINT_100:
            order_type = OrderType.POINTS_100
        elif amount == PointValue.POINT_200:
            order_type = OrderType.POINTS_200
        else:
            raise CustomException(code=400, message="Invalid amount")
        
        order_res = await OrderService.create_order(db, uid, order_type)
        
        return order_res
    
    @staticmethod
    async def launch_credit(db: Session, uid: int, orderId: str, amount: int):
        try:
            # 更新积分
            credit = db.query(Credit).filter(Credit.uid == uid).first()
            if credit:
                credit.credit += amount
                credit.update_time = datetime.now()
            else:
                credit = Credit(
                    uid=uid,
                    credit=amount,
                    lock_credit=0,
                    create_time=datetime.now(),
                    update_time = datetime.now()
                    )
                db.add(credit)

            # 新增积分记录
            credit_history = CreditHistory(
                uid=uid,
                credit_change=amount,
                source="purchase credit",
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
            logger.error(f"Launch credit failed: {e}")
            db.rollback()
            raise CustomException(code=400, message="Launch credit failed")

