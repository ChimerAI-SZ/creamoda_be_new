from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from src.exceptions.base import CustomException

from ...dto.image import ChangeBackgroundRequest, ChangeBackgroundResponse, ChangeColorRequest, ChangeColorResponse, DelImageRequest, DelImageResponse, FabricToDesignRequest, FabricToDesignResponse, ParticialModificationRequest, ParticialModificationResponse, RemoveBackgroundRequest, RemoveBackgroundResponse, TextToImageRequest, TextToImageResponse, ImageGenerationData, CopyStyleRequest, CopyStyleResponse, ChangeClothesRequest, ChangeClothesResponse, GetImageHistoryRequest, GetImageHistoryResponse, ImageHistoryItem, ImageHistoryData, GetImageDetailRequest, GetImageDetailResponse, ImageDetailData, RefreshImageStatusRequest, RefreshImageStatusData, RefreshImageStatusDataItem, RefreshImageStatusResponse, UpscaleRequest, UpscaleResponse, VirtualTryOnRequest, VirtualTryOnResponse, StyleTransferRequest, StyleTransferResponse, FabricTransferRequest, FabricTransferResponse, ChangePatternRequest, ChangePatternResponse, ChangeFabricRequest, ChangeFabricResponse, ChangePrintingRequest, ChangePrintingResponse
from ...db.session import get_db
from ...services.image_service import ImageService
from ...core.context import get_current_user_context
from ...exceptions.user import AuthenticationError, ValidationError
from ...config.log_config import logger
from ...constants.image_constants import IMAGE_FORMAT_SIZE_MAP
from ...constants.refer_constants import REFER_LEVEL_MAP
from ...dto.image import SketchToDesignRequest, SketchToDesignResponse, MixImageRequest, MixImageResponse

router = APIRouter()


def get_image_size(format: str):
    """获取对应的图像尺寸"""
    return IMAGE_FORMAT_SIZE_MAP[format] 

def get_fidelity(refer_level: int):
    """获取对应的参考等级"""
    return REFER_LEVEL_MAP[refer_level] 

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
    
    # 验证prompt长度
    if len(request.prompt) > 10000:
        raise ValidationError("Prompt text is too long. Maximum 10000 characters allowed.")

    try:
        # 从请求中获取图像尺寸
        image_size = get_image_size(request.format)
        width = image_size["width"]
        height = image_size["height"]

        # 创建文生图任务
        task_info = await ImageService.create_text_to_image_task(
            db=db,
            uid=user.id,
            prompt=request.prompt,
            with_human_model=request.withHumanModel,
            gender=request.gender,
            age=request.age,
            country=request.country,
            model_size=request.modelSize,
            format=request.format,
            width=width,
            height=height
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
    
    # 验证prompt长度
    if len(request.prompt) > 10000:
        raise ValidationError("Prompt text is too long. Maximum 10000 characters allowed.")

    try:
        # 从请求中获取参考等级
        fidelity = get_fidelity(request.referLevel)

        # 创建洗图任务
        task_info = await ImageService.create_copy_style_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl,
            fidelity=fidelity,
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

    # 验证prompt长度
    if len(request.prompt) > 10000:
        raise ValidationError("Prompt text is too long. Maximum 10000 characters allowed.")
    
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
    page: int = 1,
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
            page=page,
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
                        isCollected=item["isCollected"],
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

@router.post("/del", response_model=DelImageResponse)
async def delete_image(
    request: DelImageRequest,
    db: Session = Depends(get_db)
):
    """删除图片接口"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    try:
        # 删除图片
        result = ImageService.delete_image(
            db=db,
            uid=user.id,
            gen_img_id=request.genImgId
        )
        
        if result != 1:
            raise CustomException(code=400, message="Failed to delete image")
        
        # 返回任务信息
        return DelImageResponse(
            code=0,
            msg="Delete image successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to delete image: {str(e)}")
        raise e


@router.post("/fabric_to_design", response_model=FabricToDesignResponse)
async def fabric_to_design(
    request: FabricToDesignRequest,
    db: Session = Depends(get_db)
):
    """面料转设计接口"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    # 验证prompt长度
    if len(request.prompt) > 10000:
        raise ValidationError("Prompt text is too long. Maximum 10000 characters allowed.")
    
    try:
        # 创建面料转设计任务
        task_info = await ImageService.create_fabric_to_design_task(
            db=db,
            uid=user.id,
            fabric_pic_url=request.fabricPicUrl,
            prompt=request.prompt
        )
        
        # 返回任务信息
        return FabricToDesignResponse(
            code=0,
            msg="Fabric to design task submitted successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to process fabric to design: {str(e)}")
        raise e 


@router.post("/virtual_try_on", response_model=VirtualTryOnResponse)
async def virtual_try_on(
    request: VirtualTryOnRequest,
    db: Session = Depends(get_db)
):
    """虚拟试穿接口 - 虚拟试穿图片中的服装"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    try:
        # 创建虚拟试穿任务
        task_info = await ImageService.create_virtual_try_on_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl,
            clothing_photo=request.clothingPhoto,
            cloth_type=request.clothType
        )
        
        # 返回任务信息
        return VirtualTryOnResponse(
            code=0,
            msg="Virtual try on task submitted successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to process virtual try on: {str(e)}")
        raise e 

@router.post("/sketch_to_design", response_model=SketchToDesignResponse)
async def sketch_to_design(
    request: SketchToDesignRequest,
    db: Session = Depends(get_db)
):
    """草图转设计接口 - 草图转设计"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    # 验证prompt长度
    if len(request.prompt) > 10000:
        raise ValidationError("Prompt text is too long. Maximum 10000 characters allowed.")
    
    try:

        # 创建复制面料任务
        task_info = await ImageService.create_sketch_to_design_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl,
            prompt=request.prompt
        )
        
        # 返回任务信息
        return SketchToDesignResponse(
            code=0,
            msg="Sketch to design task submitted successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to process sketch to design: {str(e)}")
        raise e 

@router.post("/mix_image", response_model=MixImageResponse)
async def mix_image(
    request: MixImageRequest,
    db: Session = Depends(get_db)
):
    """复制面料接口 - 复制图片中的面料"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    # 验证prompt长度
    if len(request.prompt) > 10000:
        raise ValidationError("Prompt text is too long. Maximum 10000 characters allowed.")
    
    try:
        # 从请求中获取参考等级
        fidelity = get_fidelity(request.referLevel)

        # 创建复制面料任务
        task_info = await ImageService.create_mix_image_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl,
            refer_pic_url=request.referPicUrl,
            prompt=request.prompt,
            fidelity=fidelity
        )
        
        # 返回任务信息
        return MixImageResponse(
            code=0,
            msg="mix image task submitted successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to process mix image: {str(e)}")
        raise e 

@router.post("/style_transfer", response_model=StyleTransferResponse)
async def style_transfer(
    request: StyleTransferRequest,
    db: Session = Depends(get_db)
):
    """风格转换接口 - 将一张图片的风格应用到另一张图片上"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    try:
        # 创建风格转换任务
        task_info = await ImageService.create_style_transfer_task(
            db=db,
            uid=user.id,
            image_a_url=request.imageUrl,
            image_b_url=request.styleUrl,
            strength=request.strength
        )
        
        # 返回任务信息
        return StyleTransferResponse(
            code=0,
            msg="Style transfer task submitted successfully",
            data=task_info
        )
    
    except Exception as e:
        logger.error(f"Failed to process style transfer: {str(e)}")
        raise e 

@router.post("/fabric_transfer", response_model=FabricTransferResponse)
async def fabric_transfer(
    request: FabricTransferRequest,
    db: Session = Depends(get_db)
):
    """面料转换接口 - 将面料图案应用到服装上"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    try:
        # 创建面料转换任务
        task_info = await ImageService.create_fabric_transfer_task(
            db=db,
            uid=user.id,
            fabric_image_url=request.fabricUrl,
            model_image_url=request.modelUrl,
            model_mask_url=request.maskUrl
        )
        
        # 返回任务信息
        return FabricTransferResponse(
            code=0,
            msg="Fabric transfer task submitted successfully",
            data=task_info
        )
    
    except Exception as e:
        logger.error(f"Failed to process fabric transfer: {str(e)}")
        raise e


@router.post("/change_color", response_model=ChangeColorResponse)
async def change_color(
    request: ChangeColorRequest,
    db: Session = Depends(get_db)
):
    """改变颜色接口 - 改变图片中的颜色"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    # 校验clothingText不能为空
    if not request.clothingText:
        raise ValidationError("Clothing text cannot be empty")
    
    try:
        # 创建改变颜色任务
        task_info = await ImageService.create_change_color_task(
            db=db,
            uid=user.id,
            image_url=request.imageUrl,
            clothing_text=request.clothingText,
            hex_color=request.hexColor
        )
        
        # 返回任务信息
        return ChangeColorResponse(
            code=0,
            msg="Change color task submitted successfully",
            data=task_info
        )
    
    except Exception as e:
        logger.error(f"Failed to process change color: {str(e)}")
        raise e
    
@router.post("/change_background", response_model=ChangeBackgroundResponse)
async def change_background(
    request: ChangeBackgroundRequest,
    db: Session = Depends(get_db)
):
    """改变背景接口 - 改变图片中的背景"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    try:
        # 创建改变背景任务
        task_info = await ImageService.create_change_background_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl,
            refer_pic_url=request.referencePicUrl,
            background_prompt=request.backgroundPrompt
        )
        
        # 返回任务信息
        return ChangeBackgroundResponse(
            code=0,
            msg="Change background task submitted successfully",
            data=task_info
        )
    
    except Exception as e:
        logger.error(f"Failed to process change background: {str(e)}")
        raise e
    
        
@router.post("/remove_background", response_model=RemoveBackgroundResponse)
async def remove_background(
    request: RemoveBackgroundRequest,
    db: Session = Depends(get_db)
):
    """移除背景接口 - 移除图片中的背景"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    try:
        # 创建改变背景任务
        task_info = await ImageService.create_remove_background_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl
        )
        
        # 返回任务信息
        return RemoveBackgroundResponse(
            code=0,
            msg="Remove background task submitted successfully",
            data=task_info
        )
    
    except Exception as e:
        logger.error(f"Failed to process remove background: {str(e)}")
        raise e

@router.post("/particial_modification", response_model=ParticialModificationResponse)
async def particial_modification(
    request: ParticialModificationRequest,
    db: Session = Depends(get_db)
):
    """局部修改接口 - 局部修改图片"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    try:
        # 创建改变背景任务
        task_info = await ImageService.create_particial_modification_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl,
            mask_pic_url=request.maskPicUrl,
            prompt=request.prompt
        )
        
        # 返回任务信息
        return ParticialModificationResponse(
            code=0,
            msg="Particial modification task submitted successfully",
            data=task_info
        )
    
    except Exception as e:
        logger.error(f"Failed to process particial modification: {str(e)}")
        raise e
    
  
@router.post("/upscale", response_model=UpscaleResponse)
async def upscale(
    request: UpscaleRequest,
    db: Session = Depends(get_db)
):
    """高清化图片接口 - 高清化图片"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    try:
        # 创建改变背景任务
        task_info = await ImageService.create_upscale_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl
        )
        
        # 返回任务信息
        return UpscaleResponse(
            code=0,
            msg="Upscale task submitted successfully",
            data=task_info
        )
    
    except Exception as e:
        logger.error(f"Failed to process upscale: {str(e)}")
        raise e
    
@router.post("/change_pattern", response_model=ChangePatternResponse)
async def change_pattern(
    request: ChangePatternRequest,
    db: Session = Depends(get_db)
):
    """改变版型接口 - 改变图片中的版型"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    try:
        # 创建改变背景任务
        task_info = await ImageService.create_change_pattern_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl
        )
        
        # 返回任务信息
        return ChangePatternResponse(
            code=0,
            msg="Change pattern task submitted successfully",
            data=task_info
        )
    
    except Exception as e:
        logger.error(f"Failed to process change pattern: {str(e)}")
        raise e

@router.post("/change_fabric", response_model=ChangeFabricResponse)
async def change_fabric(
    request: ChangeFabricRequest,
    db: Session = Depends(get_db)
):
    """改变面料接口 - 改变图片中的面料"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    try:
        # 创建改变背景任务
        task_info = await ImageService.create_change_fabric_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl,
            fabric_pic_url=request.fabricPicUrl,
            mask_pic_url=request.maskPicUrl
        )
        
        # 返回任务信息
        return ChangeFabricResponse(
            code=0,
            msg="Change fabric task submitted successfully",
            data=task_info
        )
    
    except Exception as e:
        logger.error(f"Failed to process change fabric: {str(e)}")
        raise e

@router.post("/change_printing", response_model=ChangePrintingResponse)
async def change_printing(
    request: ChangePrintingRequest,
    db: Session = Depends(get_db)
):
    """改变印花接口 - 改变图片中的印花"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    try:
        # 创建改变印花任务
        task_info = await ImageService.create_change_printing_task(
            db=db,
            uid=user.id,
            original_pic_url=request.originalPicUrl,
        )
        
        # 返回任务信息
        return ChangePrintingResponse(
            code=0,
            msg="Change printing task submitted successfully",
            data=task_info
        )
    
    except Exception as e:
        logger.error(f"Failed to process change printing: {str(e)}")
        raise e