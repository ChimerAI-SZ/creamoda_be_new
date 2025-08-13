
from datetime import datetime
from fastapi import APIRouter, Depends
from requests import Session
from typing import Dict, Any

from sqlalchemy import or_

from src.core.context import get_current_user_context
from src.core.rabbitmq_manager import MessagePriority
from src.db.session import get_db
from src.dto.backdoor import CreatePaypalPlanRequest, CreatePaypalPlanResponse, CreatePaypalPlanResponseData, CreatePaypalProductRequest, CreatePaypalProductResponse, CreatePaypalProductResponseData, RechargeCreditRequest, RechargeCreditResponse, RechargeCreditResponseData
from src.dto.mq import ImageGenerationDto
from src.exceptions.base import CustomException
from src.exceptions.user import AuthenticationError
from src.models.models import GenImgResult, Credit, UserInfo
from src.pay.paypal_client import paypal_client
from src.services.rabbitmq_service import rabbitmq_service
from src.tasks.img_generation_task import img_generation_compensate_task
from src.tasks.release_free_credit_task import release_free_credit_task
from src.tasks.subscribe_status_refresh_task import subscribe_status_refresh_task
from src.dto.common import CommonResponse
from src.config.log_config import logger

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
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    if user.email != "417253782@qq.com":
        raise AuthenticationError()
    
    release_free_credit_task()

@router.post("/process_subscribe_status_refresh_task")
async def process_subscribe_status_refresh_task(
):
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    if user.email != "417253782@qq.com":
        raise AuthenticationError()
    
    subscribe_status_refresh_task()

@router.post("/process_img_generation_compensate_task")
async def process_img_generation_compensate_task(
):
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    if user.email != "417253782@qq.com":
        raise AuthenticationError()
    
    img_generation_compensate_task()

@router.post("/test_send_mq")
async def test_send_mq(
):
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    if user.email != "417253782@qq.com":
        raise AuthenticationError()
    
    task_data = {"genImgId":11}
    
    success = await rabbitmq_service.send_image_generation_message(task_data)
    
@router.post("/regenerate_img_label")
async def regenerate_img_label(
    db: Session = Depends(get_db)
):
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    if user.email != "417253782@qq.com":
        raise AuthenticationError()
    
    
    results = db.query(GenImgResult).filter(GenImgResult.status == 3, GenImgResult.result_pic is not None, or_(
        GenImgResult.seo_img_uid.is_(None), 
        GenImgResult.seo_img_uid.in_(['', ""])  
    )).all()
    for result in results:
        task_data = {"genImgId":result.id}
        await rabbitmq_service.send_image_generation_message(task_data)


@router.post("/recharge_credit", response_model=RechargeCreditResponse)
async def recharge_credit(
    request: RechargeCreditRequest,
    db: Session = Depends(get_db)
):
    """
    充值积分接口
    1. 校验秘钥是否正确
    2. 查询邮箱在user_info表中是否存在
    3. 根据user_id查询credit表中是否存在记录，如果存在则增加积分，如果不存在则创建记录
    """
    # 固定秘钥
    SECRET_KEY = "creamoda_backdoor_secret_key_2024"
    
    # 校验秘钥
    if request.secret_key != SECRET_KEY:
        raise AuthenticationError("Invalid secret key")
    
    # 查询用户是否存在
    user = db.query(UserInfo).filter(UserInfo.email == request.email).first()
    if not user:
        raise CustomException(code=404, msg=f"User with email {request.email} not found")
    
    # 查询用户积分记录
    credit_record = db.query(Credit).filter(Credit.uid == user.id).first()
    
    old_credit = 0
    if credit_record:
        # 如果存在积分记录，增加积分
        old_credit = credit_record.credit or 0
        credit_record.credit = old_credit + request.amount
        credit_record.update_time = datetime.utcnow()
    else:
        # 如果不存在积分记录，创建新记录
        credit_record = Credit(
            uid=user.id,
            credit=request.amount,
            lock_credit=0,
            create_time=datetime.utcnow(),
            update_time=datetime.utcnow()
        )
        db.add(credit_record)
    
    try:
        db.commit()
        db.refresh(credit_record)
        
        return RechargeCreditResponse(
            code=0,
            msg="Credit recharged successfully",
            data=RechargeCreditResponseData(
                user_id=user.id,
                old_credit=old_credit,
                new_credit=credit_record.credit,
                recharge_amount=request.amount
            )
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to recharge credit for user {user.email}: {str(e)}")
        raise CustomException(code=500, msg="Failed to recharge credit")

