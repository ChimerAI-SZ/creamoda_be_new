from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...dto.image import TextToImageRequest, TextToImageResponse, ImageGenerationData, CopyStyleRequest, CopyStyleResponse, ChangeClothesRequest, ChangeClothesResponse
from ...db.session import get_db
from ...services.image_service import ImageService
from ...core.context import get_current_user_context
from ...exceptions.user import AuthenticationError
from ...config.log_config import logger

router = APIRouter()

@router.post("/txt_generate", response_model=TextToImageResponse)
async def text_to_image(
    request: TextToImageRequest,
    db: Session = Depends(get_db)
):
    """文生图接口"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    try:
        # 创建文生图任务
        task_info = await ImageService.create_text_to_image_task(
            db=db,
            uid=user.id,
            prompt=request.prompt,
            with_human_model=request.withHumanModel,
            gender=request.gender,
            age=request.age,
            country=request.country,
            model_size=request.modelSize
        )
        
        # 返回任务信息
        return TextToImageResponse(
            code=0,
            msg="Task submitted successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to process image generation: {str(e)}")
        raise e 

@router.post("/copy_style_generate", response_model=CopyStyleResponse)
async def copy_style_generate(
    request: CopyStyleRequest,
    db: Session = Depends(get_db)
):
    """洗图接口 - 图片风格转换"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    try:
        # 创建洗图任务
        task_info = await ImageService.create_copy_style_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl,
            fidelity=request.fidelity,
            prompt=request.prompt
        )
        
        # 返回任务信息
        return CopyStyleResponse(
            code=0,
            msg="Copy style task submitted successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to process copy style generation: {str(e)}")
        raise e 

@router.post("/change_clothes_generate", response_model=ChangeClothesResponse)
async def change_clothes_generate(
    request: ChangeClothesRequest,
    db: Session = Depends(get_db)
):
    """更换服装接口 - 修改图片中的服装"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    try:
        # 创建更换服装任务
        task_info = await ImageService.create_change_clothes_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl,
            replace=request.prompt,
        )
        
        # 返回任务信息
        return ChangeClothesResponse(
            code=0,
            msg="Change clothes task submitted successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to process change clothes: {str(e)}")
        raise e 