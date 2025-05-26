from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from src.core.context import get_current_user_context
from src.exceptions.user import AuthenticationError
from src.services.credit_service import CreditService
from src.services.order_service import OrderService
from src.services.subscribe_service import SubscribeService
from src.config.log_config import logger

from ...dto.pay import BillingHistoryData, PurchaseCreditResponseData, SubscribeRequest, SubscribeResponse, CancelSubscribeRequest, CancelSubscribeResponse, PurchaseCreditRequest, PurchaseCreditResponse, BillingHistoryRequest, BillingHistoryResponse, SubscribeResponseData
from ...db.session import get_db

router = APIRouter()

@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(
    request: SubscribeRequest,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    order_res = await SubscribeService.create_subscribe_order(db, user.id, request.level)
    
    return SubscribeResponse(
        data=SubscribeResponseData(
            id=order_res['subscription_id'],
            url=order_res['approval_url']
        )
    )

@router.post("/cancel_subscribe", response_model=CancelSubscribeResponse)
async def cancel_subscribe(
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    await SubscribeService.cancel_subscribe(db, user.id)

    return CancelSubscribeResponse(
        code=0,
        msg="Cancel subscribe success"
    )

@router.post("/purchase_credit", response_model=PurchaseCreditResponse)
async def purchase_credit(
    request: PurchaseCreditRequest,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    order_res = await CreditService.create_credit_order(db, user.id, request.value)
    
    return PurchaseCreditResponse(
        data=PurchaseCreditResponseData(
            id=order_res.id,
            url=order_res.get_approve_link()
        )
    )

@router.get("/billing_history", response_model=BillingHistoryResponse)
async def billing_history(
    page: int = 1,
    pageSize: int = 10,
    db: Session = Depends(get_db)
):
    """查询账单历史记录"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    try:
        billing_history = await OrderService.get_billing_history(db, user.id, page, pageSize)
        return BillingHistoryResponse(
            data=BillingHistoryData(
                total=billing_history['total'],
                list=billing_history['list']
            )
        )
    except Exception as e:
        logger.error(f"获取账单历史记录失败: {e}")
        raise e
