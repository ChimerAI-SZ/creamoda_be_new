from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
import os

from ...dto.contact import ContactBusinessRequest, ContactBusinessResponse
from ...dto.common import UploadImageResponse, UploadResponse
from ...db.session import get_db
from ...services.contact_service import ContactService
from ...services.upload_service import UploadService
from ...core.context import get_current_user_context
from ...exceptions.user import AuthenticationError
from ...config.log_config import logger
from ...dto.constant import GetEnumResponse, EnumData, EnumItem
from ...services.constant_service import ConstantService
from src.validators.user import UserValidator

router = APIRouter()

@router.post("/contact", response_model=ContactBusinessResponse)
async def contact_business(
    request: ContactBusinessRequest,
    db: Session = Depends(get_db)
):
    """联系商务接口"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    # 验证邮箱格式
    UserValidator.validate_email(request.contactEmail)

    try:
        # 创建联系记录
        success = ContactService.create_contact_record(
            db=db,
            uid=user.id,
            contactEmail=request.contactEmail,
            source=request.source,
            genImgId=request.genImgId
        )
        
        if success:
            return ContactBusinessResponse(
                code=0,
                msg="Contact request submitted successfully"
            )
        else:
            return ContactBusinessResponse(
                code=500,
                msg="Failed to submit contact request"
            )
    
    except Exception as e:
        logger.error(f"Failed to process contact business request: {str(e)}")
        raise e

@router.post("/img/upload", response_model=UploadImageResponse)
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传图片接口"""
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()

    try:
        # 验证文件类型
        content_type = file.content_type
        if not content_type or not content_type.startswith('image/'):
            return UploadImageResponse(
                code=400,
                msg="Invalid file type. Only images are allowed."
            )
        
        # 验证文件后缀
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.jpg', '.jpeg', '.png']:
            return UploadImageResponse(
                code=400,
                msg="Invalid file type. Only images are allowed."
            )
        
        # 上传文件到OSS并创建记录
        upload_result = await UploadService.upload_image_with_record(
            db=db,
            uid=user.id,
            file=file
        )
        
        # 返回上传结果
        return UploadImageResponse(
            code=0,
            msg="Image uploaded successfully",
            data=UploadResponse(
                url=upload_result["fileUrl"],
                filename=upload_result["fileName"]
            )
        )
    
    except Exception as e:
        logger.error(f"Failed to upload image: {str(e)}")
        raise e

@router.get("/modelSize/list", response_model=GetEnumResponse)
async def get_model_size_list(
    db: Session = Depends(get_db)
):
    """获取模特身材尺寸选项列表"""
    try:
        # 获取枚举值
        enum_items = ConstantService.get_enum_by_type(db, 1)
        
        # 构建响应，确保即使枚举项为空也能返回有效结果
        return GetEnumResponse(
            code=0,
            msg="Success",
            data=EnumData(
                list=[
                    EnumItem(
                        code=item["code"],
                        name=item["name"]
                    ) for item in enum_items
                ],
                type="modelSize"  # 添加类型信息
            )
        )
    
    except Exception as e:
        logger.error(f"Failed to get model size list: {str(e)}")
        raise e 
    
@router.get("/variationType/list", response_model=GetEnumResponse)
async def get_variation_list(
    db: Session = Depends(get_db)
):
    """获取图片变化类型选项列表"""
    try:
        # 获取枚举值
        enum_items = ConstantService.get_enum_by_type(db, 2)
        
        # 构建响应，确保即使枚举项为空也能返回有效结果
        return GetEnumResponse(
            code=0,
            msg="Success",
            data=EnumData(
                list=[
                    EnumItem(
                        code=item["code"],
                        name=item["name"]
                    ) for item in enum_items
                ],
                type="variation"  # 添加类型信息
            )
        )
    
    except Exception as e:
        logger.error(f"Failed to get variation list: {str(e)}")
        raise e 