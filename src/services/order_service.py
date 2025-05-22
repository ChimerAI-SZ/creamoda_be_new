
from datetime import datetime
from src.exceptions.pay import PayError
from src.models.models import BillingHistory, Constant
from requests import Session
from src.config.log_config import logger
from src.constants.order_status import OrderStatus
from src.constants.order_type import OrderType, get_order_info, get_order_price
from src.exceptions.base import CustomException
from src.pay.paypal_client import paypal_client
from src.db.redis import redis_client

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
            order_res = paypal_client.create_order(get_order_price(order_type) / 100)
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
    async def create_subscribe_order(
        db: Session,
        uid: int,
        order_type: OrderType
    ):
        """创建订阅订单"""
        billing_history = BillingHistory(
            uid=uid,
            type=order_type,
            amount=get_order_price(order_type),
            description=get_order_info(order_type).name,
            status=OrderStatus.PAYMENT_PENDING,
            create_time=datetime.now()
        )
        db.add(billing_history)

        plan_id = await OrderService.get_plan_id(db, order_type)
        
        try:
            order_res = paypal_client.create_subscription(plan_id)
            # 更新订单id
            billing_history.order_id = order_res['subscription_id']
            
            db.commit()

        except PayError as e:
            logger.error(f"创建订单失败: {e}")
            db.rollback()
            raise e

        db.commit()
        return order_res

    @staticmethod
    async def get_plan_id(db: Session, order_type: OrderType):
        if order_type == OrderType.BASIC_MEMBERSHIP:
            plan_id_const = db.query(Constant).filter(Constant.type == 3, Constant.code == 1).first()
            if not plan_id_const:
                raise CustomException(code=400, message="Basic membership plan not found")
            plan_id = plan_id_const.name
        elif order_type == OrderType.PRO_MEMBERSHIP:
            plan_id_const = db.query(Constant).filter(Constant.type == 3, Constant.code == 2).first()
            if not plan_id_const:
                raise CustomException(code=400, message="Pro membership plan not found")
            plan_id = plan_id_const.name
        elif order_type == OrderType.ENTERPRISE_MEMBERSHIP:
            plan_id_const = db.query(Constant).filter(Constant.type == 3, Constant.code == 3).first()
            if not plan_id_const:
                raise CustomException(code=400, message="Enterprise membership plan not found")
            plan_id = plan_id_const.name
        else:
            raise CustomException(code=400, message="Invalid order type")
        return plan_id
    
    @staticmethod
    async def capture_order(
        db: Session,
        uid: int,
        order_id: str
    ):
        """捕获订单"""
        try:
            # redis锁订单
            redis_key = f"order_lock:{order_id}"
            if not redis_client.set(redis_key, "1", ex=300):
                raise CustomException(code=400, message=f"Redis lock order failed:{redis_key}")

            order = db.query(BillingHistory).filter(BillingHistory.order_id == order_id, BillingHistory.uid == uid).first()
            if not order:
                raise CustomException(code=400, message="Order not found")
            
            if order.status != OrderStatus.PAYMENT_PENDING:
                raise CustomException(code=400, message="Order already captured")
            
            # 捕获订单
            capture_res = paypal_client.capture_payment(order_id)

            if capture_res.status != "COMPLETED":
                raise CustomException(code=400, message="Capture failed")

            # 更新订单状态
            order.status = OrderStatus.PAYMENT_CAPTURED
            db.commit()
        except Exception as e:
            logger.error(f"捕获订单失败: {e}")
            db.rollback()
            raise e
        finally:
            redis_client.delete(redis_key)

    @staticmethod
    async def capture_subscribe_order(
        db: Session,
        uid: int,
        subscription_id: str
    ):
        """查询订阅订单"""
        try:
            # redis锁订单
            redis_key = f"order_lock:{subscription_id}"
            if not redis_client.set(redis_key, "1", ex=300):
                raise CustomException(code=400, message=f"Redis lock order failed:{redis_key}")

            order = db.query(BillingHistory).filter(BillingHistory.order_id == subscription_id, BillingHistory.uid == uid).first()
            if not order:
                raise CustomException(code=400, message="Order not found")
            
            paypal_res = paypal_client.get_subscription_details(subscription_id)
            if paypal_res["status"] != "ACTIVE":
                raise CustomException(code=400, message="Subscription not active")

            # 更新订单状态
            order.status = OrderStatus.PAYMENT_CAPTURED
            db.commit()

        except Exception as e:
            logger.error(f"捕获订阅订单失败: {e}")
            db.rollback()
            raise e
        finally:
            redis_client.delete(redis_key)

