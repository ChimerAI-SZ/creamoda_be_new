from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from ...dto.image import TextToImageRequest, TextToImageResponse, ImageGenerationData, CopyStyleRequest, CopyStyleResponse, ChangeClothesRequest, ChangeClothesResponse, GetImageHistoryRequest, GetImageHistoryResponse, ImageHistoryItem, ImageHistoryData, GetImageDetailRequest, GetImageDetailResponse, ImageDetailData, RefreshImageStatusRequest, RefreshImageStatusData, RefreshImageStatusDataItem, RefreshImageStatusResponse
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

@router.get("/generate/list", response_model=GetImageHistoryResponse)
async def get_image_history(
    pageNum: int = 1,
    pageSize: int = 10,
    type: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """查询图片生成记录列表"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    try:
        # 获取历史记录
        history_data = ImageService.get_image_history(
            db=db,
            uid=user.id,
            page_num=pageNum,
            page_size=pageSize,
            record_type=type
        )
        
        # 构建响应
        return GetImageHistoryResponse(
            code=0,
            msg="Success",
            data=ImageHistoryData(
                total=history_data["total"],
                list=[
                    ImageHistoryItem(
                        genImgId=item["genImgId"],
                        genId=item["genId"],
                        type=item["type"],
                        variationType=item["variationType"],
                        status=item["status"],
                        resultPic=item["resultPic"],
                        createTime=item["createTime"]
                    ) for item in history_data["list"]
                ]
            )
        )
    
    except Exception as e:
        logger.error(f"Failed to get image history: {str(e)}")
        raise e 

@router.get("/generate/info", response_model=GetImageDetailResponse)
async def get_image_info(
    genImgId: int,
    db: Session = Depends(get_db)
):
    """查询图片生成信息"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    try:
        # 获取图片详情
        detail = ImageService.get_image_detail(
            db=db,
            uid=user.id,
            gen_img_id=genImgId
        )
        
        # 构建响应
        return GetImageDetailResponse(
            code=0,
            msg="Success",
            data=ImageDetailData(
                genImgId=detail["genImgId"],
                genId=detail["genId"],
                type=detail["type"],
                variationType=detail["variationType"],
                prompt=detail["originalPrompt"],
                originalPicUrl=detail["originalPicUrl"],
                resultPic=detail["resultPic"],
                status=detail["status"],
                createTime=detail["createTime"],
                withHumanModel=detail["withHumanModel"],
                gender=detail["gender"],
                age=detail["age"],
                country=detail["country"],
                modelSize=detail["modelSize"],
                fidelity=detail["fidelity"]
            )
        )
    
    except ValueError as e:
        logger.error(f"Invalid request for image detail: {str(e)}")
        return GetImageDetailResponse(
            code=404,
            msg=f"Image not found: {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Failed to get image detail: {str(e)}")
        raise e 

@router.get("/generate/refresh_status", response_model=RefreshImageStatusResponse)
async def refresh_image_status(
    genImgIdList: str = Query(default="", description="图片ID列表，逗号分隔的数字"),
    db: Session = Depends(get_db)
):
    """刷新图片生成状态"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    try:
        # 解析逗号分隔的ID字符串为整数列表
        img_id_list = []
        if genImgIdList:
            try:
                # 分割字符串并转换每个部分为整数
                img_id_list = [int(id_str.strip()) for id_str in genImgIdList.split(',') if id_str.strip()]
            except ValueError as e:
                logger.error(f"Invalid genImgIdList format: {genImgIdList}. Error: {str(e)}")
                return RefreshImageStatusResponse(
                    code=400,
                    msg="Invalid image ID list format. Expected comma-separated integers."
                )
        
        # 获取图片状态列表
        status_list = ImageService.refresh_image_status(
            db=db,
            uid=user.id,
            gen_img_id_list=img_id_list
        )
        
        # 构建响应
        return RefreshImageStatusResponse(
            code=0,
            msg="Success",
            data=RefreshImageStatusData(
                list=[
                    RefreshImageStatusDataItem(
                        genImgId=item["genImgId"],
                        genId=item["genId"],
                        type=item["type"],
                        variationType=item["variationType"],
                        resultPic=item["resultPic"] if "resultPic" in item and item["resultPic"] else "",
                        status=item["status"],
                        createTime=item["createTime"]
                    ) for item in status_list
                ]
            )
        )
    
    except Exception as e:
        logger.error(f"Failed to refresh image status: {str(e)}")
        raise e 