
from fastapi import APIRouter, Depends
from requests import Session

from src.core.context import get_current_user_context
from src.db.session import get_db
from src.dto.backdoor import CreatePaypalPlanRequest, CreatePaypalPlanResponse, CreatePaypalPlanResponseData, CreatePaypalProductRequest, CreatePaypalProductResponse, CreatePaypalProductResponseData
from src.exceptions.user import AuthenticationError
from src.pay.paypal_client import paypal_client
from src.tasks.release_free_credit_task import release_free_credit_task
from src.tasks.subscribe_status_refresh_task import subscribe_status_refresh_task

router = APIRouter()

@router.post("/create_paypal_product", response_model=CreatePaypalProductResponse)
async def create_paypal_product(
    request: CreatePaypalProductRequest,
    db: Session = Depends(get_db)
):
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    if user.email != "417253782@qq.com":
        raise AuthenticationError()
    
    res = paypal_client.create_product(request.name, request.description, request.category)
    return CreatePaypalProductResponse(
        code=0,
        msg="success",
        data=CreatePaypalProductResponseData(resp=res)
    )

@router.post("/create_paypal_plan", response_model=CreatePaypalPlanResponse)
async def create_paypal_plan(
    request: CreatePaypalPlanRequest,
):
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    if user.email != "417253782@qq.com":
        raise AuthenticationError()
    
    res = paypal_client.create_plan(request.product_id, request.plan_name, request.price, request.currency, request.interval_unit, request.interval_count, request.total_cycles)
    return CreatePaypalPlanResponse(
        code=0,
        msg="success",
        data=CreatePaypalPlanResponseData(resp=res)
    )

@router.post("/process_release_free_credit_task")
async def process_release_free_credit_task(
):
    release_free_credit_task()

@router.post("/process_subscribe_status_refresh_task")
async def process_subscribe_status_refresh_task(
):
    subscribe_status_refresh_task()