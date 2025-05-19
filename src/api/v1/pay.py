from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from ...dto.pay import SubscribeRequest, SubscribeResponse, CancelSubscribeRequest, CancelSubscribeResponse, PurchaseCreditRequest, PurchaseCreditResponse, BillingHistoryRequest, BillingHistoryResponse
from ...db.session import get_db

router = APIRouter()

@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(
    request: SubscribeRequest,
    db: Session = Depends(get_db)
):
    pass

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