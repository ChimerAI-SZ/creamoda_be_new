
from datetime import datetime
from src.exceptions.pay import PayError
from src.models.models import BillingHistory
from requests import Session
from src.config.log_config import logger
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
            amount=get_order_price(order_type),
            description=get_order_info(order_type).name,
            status=OrderStatus.PAYMENT_PENDING,
            create_time=datetime.now()
        )

        db.add(billing_history)

        try:
            order_res = PayPalClient.create_order(get_order_price(order_type) / 100)
            # 更新订单id
            billing_history.order_id = order_res.id
            db.commit()
            db.refresh(billing_history)

        except PayError as e:
            logger.error(f"创建订单失败: {e}")
            db.rollback()
            raise e

        db.commit()
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
            raise CustomException(code=400, message="Order not found")
        
        if order.status != OrderStatus.PAYMENT_PENDING:
            raise CustomException(code=400, message="Order already captured")
        
        # 捕获订单
        capture_res = PayPalClient.capture_payment(order_id)

        if capture_res.status != "COMPLETED":
            raise CustomException(code=400, message="Capture failed")

        # 更新订单状态
        order.status = OrderStatus.PAYMENT_CAPTURED
        db.commit()
