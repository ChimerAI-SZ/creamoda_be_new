

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
from src.pay.paypal_client import PayPalClient
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
    await OrderService.capture_order(db, user.id, request.orderId)

    # 更新支付状态
    await handle_payment_success(request.orderId, db)

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
    # verify_res = PayPalClient.verify_webhook(request.headers, body_text)
    # if not verify_res:
    #     raise CustomException(code=400, message="Invalid webhook")
    
    # 解析请求体
    paypal_callback_event = PayPalWebhookEvent(**json.loads(body_text))

    # 处理事件
    if paypal_callback_event.event_type == "PAYMENT.CAPTURE.COMPLETED":
        # 处理支付成功事件
        await handle_payment_success(paypal_callback_event.resource.supplementary_data.related_ids.order_id, db)
        pass
    elif paypal_callback_event.event_type == "PAYMENT.CAPTURE.DENIED":
        # 处理拒绝事件
        pass
    elif paypal_callback_event.event_type == "PAYMENT.CAPTURE.EXPIRED":
        # 处理过期事件
        pass
    else:
        raise CustomException(code=400, message="Invalid event type")
    
    return PaypalCallbackResponse(
        code=0,
        msg="Callback successfully"
    )

async def handle_payment_success(
    order_id: str,
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Handle payment success: {order_id}")

        # redis锁订单
        redis_key = f"order_lock:{order_id}"
        if not redis_client.set(redis_key, "1", ex=300):
            raise CustomException(code=400, message=f"Order already handled: redis lock failed:{redis_key}")

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
            pass
        elif order.type == OrderType.POINTS_100:
            pass
        elif order.type == OrderType.POINTS_200:
            pass
        elif order.type == OrderType.BASIC_MEMBERSHIP:
            await SubscribeService.launch_subscribe(db, order.uid, order_id, 1)
        elif order.type == OrderType.PRO_MEMBERSHIP:
            await SubscribeService.launch_subscribe(db, order.uid, order_id, 2)
        elif order.type == OrderType.ENTERPRISE_MEMBERSHIP:
            await SubscribeService.launch_subscribe(db, order.uid, order_id, 3)
        else:
            raise CustomException(code=400, message="Invalid order type")

    except Exception as e:
        raise CustomException(code=400, message=str(e))
    finally:
        redis_client.delete(redis_key)