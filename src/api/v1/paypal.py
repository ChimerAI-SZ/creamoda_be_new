

from datetime import datetime
import json
from fastapi import APIRouter, Depends, Request
from requests import Session
from src.constants.order_status import OrderStatus
from src.constants.order_type import OrderType
from src.core.context import get_current_user_context
from src.db.session import get_db
from src.dto.paypal import PayPalWebhookEvent, PaypalCallbackResponse, PaypalCaptureRequest, PaypalCaptureResponse
from src.exceptions.base import CustomException
from src.exceptions.user import AuthenticationError
from src.models.models import BillingHistory
from src.pay.paypal_client import paypal_client
from src.services.credit_service import CreditService
from src.services.order_service import OrderService
from src.services.subscribe_service import SubscribeService
from src.config.log_config import logger
from src.db.redis import redis_client

router = APIRouter()

@router.post("/capture", response_model=PaypalCaptureResponse)
async def paypal_capture(
    request: PaypalCaptureRequest,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    # 捕获订单
    if request.subscription_id:
        await OrderService.capture_subscribe_order(db, user.id, request.subscription_id)
        # await handle_subscribe_payment_success(order_id=request.subscription_id, db=db)
    else:
        await OrderService.capture_order(db, user.id, request.token)
        # 更新支付状态
        await handle_credit_payment_success(request.token, db)

    return PaypalCaptureResponse(
        code=0,
        msg="Capture successfully"
    )

@router.post("/callback", response_model=PaypalCallbackResponse)
async def paypal_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    raw_body = await request.body()  # 返回bytes类型
    body_text = raw_body.decode("utf-8")
    logger.info(f"Paypal callback received:{body_text}")

    # 验证签名 暂时关闭
    # verify_res = paypal_client.verify_webhook(request.headers, body_text)
    # if not verify_res:
    #     raise CustomException(code=400, message="Invalid webhook")
    
    # 解析请求体
    paypal_callback_event = PayPalWebhookEvent(**json.loads(body_text))

    # 处理事件
    if paypal_callback_event.event_type == "PAYMENT.CAPTURE.COMPLETED":
        # 处理支付成功事件
        await handle_credit_payment_success(paypal_callback_event.resource.supplementary_data.related_ids.order_id, db)
    elif paypal_callback_event.event_type == "PAYMENT.CAPTURE.DENIED":
        # 处理拒绝事件
        await handle_credit_payment_failed(paypal_callback_event.resource.supplementary_data.related_ids.order_id, db)
    elif paypal_callback_event.event_type == "PAYMENT.CAPTURE.EXPIRED":
        # 处理过期事件
        await handle_credit_payment_failed(paypal_callback_event.resource.supplementary_data.related_ids.order_id, db)
    elif paypal_callback_event.event_type == "PAYMENT.SALE.COMPLETED":
        # 处理订阅成功事件
        await handle_subscribe_payment_success(paypal_callback_event.resource.billing_agreement_id, paypal_callback_event.resource.id, db)
    elif paypal_callback_event.event_type == "BILLING.SUBSCRIPTION.CANCELLED":
        # 处理订阅取消事件
        await SubscribeService.handle_cancel_subscribe_event(db, paypal_callback_event.resource.id)
    else:
        logger.info(f"Invalid event type: {paypal_callback_event.event_type}")
    
    return PaypalCallbackResponse(
        code=0,
        msg="Callback successfully"
    )

async def handle_credit_payment_success(
    order_id: str,
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Handle payment success: {order_id}")

        # redis锁订单
        redis_key = f"order_lock:{order_id}"
        if not redis_client.set(redis_key, "1", ex=300):
            raise CustomException(code=400, message=f"Redis lock order failed:{redis_key}")

        # 获取订单
        order = db.query(BillingHistory).filter(BillingHistory.order_id == order_id).first()
        if not order:
            raise CustomException(code=400, message="Order not found")
        if order.status == OrderStatus.PAYMENT_SUCCESS:
            logger.info(f"Order {order_id} already handled")
            return
        if order.status != OrderStatus.PAYMENT_CAPTURED and order.status != OrderStatus.PAYMENT_PENDING:
            raise CustomException(code=400, message="Order not captured status")
        
        if order.type == OrderType.POINTS_40:
            await CreditService.launch_credit(db, order.uid, order_id, 40)
        elif order.type == OrderType.POINTS_100:
            await CreditService.launch_credit(db, order.uid, order_id, 100)
        elif order.type == OrderType.POINTS_200:
            await CreditService.launch_credit(db, order.uid, order_id, 200)
        else:
            raise CustomException(code=400, message="Invalid order type")

    except Exception as e:
        raise CustomException(code=400, message=str(e))
    finally:
        redis_client.delete(redis_key)

async def handle_credit_payment_failed(
    order_id: str,
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Handle payment success: {order_id}")

        # redis锁订单
        redis_key = f"order_lock:{order_id}"
        if not redis_client.set(redis_key, "1", ex=300):
            raise CustomException(code=400, message=f"Redis lock order failed:{redis_key}")

        # 获取订单
        order = db.query(BillingHistory).filter(BillingHistory.order_id == order_id).first()
        if not order:
            raise CustomException(code=400, message="Order not found")
        if order.status == OrderStatus.PAYMENT_SUCCESS or order.status == OrderStatus.PAYMENT_CAPTURED or order.status == OrderStatus.PAYMENT_CAPTURED:
            logger.info(f"Order {order_id} already handled")
            return
        
        order.status = OrderStatus.PAYMENT_FAILED
        order.update_time = datetime.now()
        db.commit()
    except Exception as e:
        raise CustomException(code=400, message=str(e))
    finally:
        redis_client.delete(redis_key)

async def handle_subscribe_payment_success(
    order_id: str,
    sub_order_id: str = None,
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Handle payment success: {order_id}")

        # redis锁订单
        redis_key = f"order_lock:{order_id}"
        if not redis_client.set(redis_key, "1", ex=300):
            raise CustomException(code=400, message=f"Redis lock order failed:{redis_key}")

        # 获取订单
        order = db.query(BillingHistory).filter(BillingHistory.order_id == order_id, BillingHistory.sub_order_id.is_(None)).first()
        if not order:
            order = db.query(BillingHistory).filter(BillingHistory.order_id == order_id, BillingHistory.sub_order_id == sub_order_id).first()
            if not order:
                order = await create_subscribe_order(order_id, sub_order_id, db)
        else:
            # 更新订单subOrderId
            order.sub_order_id = sub_order_id
            db.commit()
            db.refresh(order)

        if order.status == OrderStatus.PAYMENT_SUCCESS:
            logger.info(f"Order {order_id} already handled")
            return
        if order.status != OrderStatus.PAYMENT_CAPTURED and order.status != OrderStatus.PAYMENT_PENDING:
            raise CustomException(code=400, message="Order not captured status")
        
        if order.type == OrderType.BASIC_MEMBERSHIP:
            await SubscribeService.launch_subscribe(db, order.uid, order_id, sub_order_id, 1)
        elif order.type == OrderType.PRO_MEMBERSHIP:
            await SubscribeService.launch_subscribe(db, order.uid, order_id, sub_order_id, 2)
        elif order.type == OrderType.ENTERPRISE_MEMBERSHIP:
            await SubscribeService.launch_subscribe(db, order.uid, order_id, sub_order_id, 3)
        else:
            raise CustomException(code=400, message="Invalid order type")

    except Exception as e:
        raise CustomException(code=400, message=str(e))
    finally:
        redis_client.delete(redis_key)

async def create_subscribe_order(
    order_id: str,
    sub_order_id: str,
    db: Session
) -> BillingHistory:
    old_order = db.query(BillingHistory).filter(BillingHistory.order_id == order_id).first()
    if not old_order:
        raise CustomException(code=400, message="Order not found")
    
    logger.info(f"Create subscribe order: {order_id} {sub_order_id}")
    
    new_order = BillingHistory(
        uid=old_order.uid,
        type=old_order.type,
        order_id=order_id,
        sub_order_id=sub_order_id,
        description=old_order.description,
        amount=old_order.amount,
        status=OrderStatus.PAYMENT_PENDING,
        create_time=datetime.now()
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order

