
from datetime import datetime
from typing import Any, Dict
from src.dto.pay import BillingHistoryItem
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

    @staticmethod
    async def get_billing_history(
        db: Session,
        uid: int,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """获取用户账单历史记录
        
        Args:
            db: 数据库会话
            uid: 用户ID
            page_num: 页码，从1开始
            page_size: 每页记录数
            
        Returns:
            包含分页数据的字典
        """
        # 构建JOIN查询，把GenImgResult和GenImgRecord关联起来
        query = db.query(
            BillingHistory
        ).filter(
            BillingHistory.uid == uid,
            BillingHistory.status != OrderStatus.PAYMENT_PENDING
        )

        
        # 计算总记录数
        total_count = query.count()
        
        # 分页并按创建时间倒序排序
        paginated_results = query.order_by(BillingHistory.id.desc())\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
        
        # 构建结果列表
        result_list = []
        for record in paginated_results:
            # 格式化时间为字符串
            create_time = record.create_time.strftime("%Y-%m-%d %H:%M:%S") if record.create_time else ""

            status = ""
            if record.status == OrderStatus.PAYMENT_SUCCESS:
                status = "Success"
            elif record.status == OrderStatus.PAYMENT_FAILED:
                status = "Failed"
            elif record.status == OrderStatus.PAYMENT_CAPTURED:
                status = "Success"

            # 构建单条记录
            history_item = BillingHistoryItem(
                dueDate=create_time,
                description=record.description,
                status=status,
                invoice='$'+str(record.amount/100)
            )
            
            result_list.append(history_item)
        
        # 返回分页结果
        return {
            "total": total_count,
            "list": result_list
        } 