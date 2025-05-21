from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from src.core.context import get_current_user_context
from src.exceptions.user import AuthenticationError
from src.services.subscribe_service import SubscribeService

from ...dto.pay import SubscribeRequest, SubscribeResponse, CancelSubscribeRequest, CancelSubscribeResponse, PurchaseCreditRequest, PurchaseCreditResponse, BillingHistoryRequest, BillingHistoryResponse, SubscribeResponseData
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
            url=order_res.get_approve_link()
        )
    )

@router.post("/cancel_subscribe", response_model=CancelSubscribeResponse)
async def cancel_subscribe(
    request: CancelSubscribeRequest,
    db: Session = Depends(get_db)
):
    pass

@router.post("/purchase_credit", response_model=PurchaseCreditResponse)
async def purchase_credit(
    request: PurchaseCreditRequest,
    db: Session = Depends(get_db)
):
    pass

@router.get("/billing_history", response_model=BillingHistoryResponse)
async def billing_history(
    request: BillingHistoryRequest,
    db: Session = Depends(get_db)
):
    pass