

import json
from fastapi import APIRouter, Depends, Request
from requests import Session
from src.constants.order_status import OrderStatus
from src.constants.order_type import OrderType
from src.core.context import get_current_user_context
from src.db.session import get_db
from src.dto.paypal import PayPalWebhookEvent, PaypalCallbackRequest, PaypalCallbackResponse, PaypalCaptureRequest, PaypalCaptureResponse
from src.exceptions.base import CustomException
from src.exceptions.user import AuthenticationError
from src.models.models import BillingHistory
from src.pay.paypal_client import PayPalClient
from src.services.order_service import OrderService
from src.services.subscribe_service import SubscribeService


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
    await OrderService.capture_order(db, user.id, request.order_id)
    return PaypalCaptureResponse(
    )

@router.post("/callback", response_model=PaypalCallbackResponse)
async def paypal_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    raw_body = await request.body()  # 返回bytes类型
    body_text = raw_body.decode("utf-8")

    # 验证签名
    verify_res = PayPalClient.verify_webhook(request.headers, body_text)
    if not verify_res:
        raise CustomException(status_code=400, detail="Invalid webhook")
    
    # 解析请求体
    paypal_callback_event = PayPalWebhookEvent(**json.loads(body_text))

    # 处理事件
    if paypal_callback_event.event_type == "PAYMENT.CAPTURE.COMPLETED":
        # 处理支付成功事件
        await handle_payment_success(paypal_callback_event.resource.id, db)
        pass
    elif paypal_callback_event.event_type == "PAYMENT.CAPTURE.DENIED":
        # 处理拒绝事件
        pass
    elif paypal_callback_event.event_type == "PAYMENT.CAPTURE.EXPIRED":
        # 处理过期事件
        pass
    else:
        raise CustomException(status_code=400, detail="Invalid event type")

async def handle_payment_success(
    order_id: str,
    db: Session = Depends(get_db)
):
    try:
        # 获取订单
        order = db.query(BillingHistory).filter(BillingHistory.order_id == order_id).first()
        if not order:
            raise CustomException(status_code=400, detail="Order not found")
        
        if order.type == OrderType.POINTS_40:
            pass
        elif order.type == OrderType.POINTS_100:
            pass
        elif order.type == OrderType.POINTS_200:
            pass
        elif order.type == OrderType.BASIC_MEMBERSHIP:
            await SubscribeService.launch_subscribe(db, order.uid, order.id, 1)
        elif order.type == OrderType.PRO_MEMBERSHIP:
            await SubscribeService.launch_subscribe(db, order.uid, order.id, 2)
        elif order.type == OrderType.ENTERPRISE_MEMBERSHIP:
            await SubscribeService.launch_subscribe(db, order.uid, order.id, 3)
        else:
            raise CustomException(status_code=400, detail="Invalid order type")

    except Exception as e:
        raise CustomException(status_code=400, detail=str(e))
