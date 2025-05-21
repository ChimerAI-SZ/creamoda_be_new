
import datetime
from models.models import BillingHistory
from requests import Session

from src.constants.order_status import OrderStatus
from src.constants.order_type import OrderType, get_order_info, get_order_price
from src.exceptions.base import CustomException
from src.pay.paypal_client import PayPalClient


class OrderService:
    @staticmethod
    async def create_order(
        db: Session,
        uid: int,
        order_type: OrderType
    ):
        """创建订单"""
        billing_history = BillingHistory(
            uid=uid,
            type=order_type,
            amount=int(get_order_price(order_type)*100),
            description=get_order_info(order_type).name,
            status=OrderStatus.PAYMENT_PENDING,
            create_time=datetime.now()
        )

        db.add(billing_history)
        db.commit()
        db.refresh(billing_history)

        order_res = PayPalClient.create_order(get_order_price(order_type))
        # 更新订单id
        billing_history.order_id = order_res.id
        db.commit()
        db.refresh(billing_history)

        return order_res

    @staticmethod
    async def capture_order(
        db: Session,
        uid: int,
        order_id: str
    ):
        """捕获订单"""
        order = db.query(BillingHistory).filter(BillingHistory.order_id == order_id, BillingHistory.uid == uid).first()
        if not order:
            raise CustomException(status_code=400, detail="Order not found")
        
        if order.status != OrderStatus.PAYMENT_PENDING:
            raise CustomException(status_code=400, detail="Order already captured")
        
        # 捕获订单
        capture_res = PayPalClient.capture_payment(order_id)

        if capture_res.status != "COMPLETED":
            raise CustomException(status_code=400, detail="Capture failed")

        # 更新订单状态
        order.status = OrderStatus.PAYMENT_CAPTURED
        db.commit()
        db.refresh(order)
