from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from typing import List
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
from ...dto.csv_process import ProcessCsvResponse, GetFashionDataRequest, GetFashionDataResponse, GetFrontendImagesResponse, GetImageDetailResponse
from ...services.constant_service import ConstantService
from ...services.csv_process_service import CsvProcessService
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


@router.post("/process_csv_with_images", response_model=ProcessCsvResponse)
async def process_csv_with_images(
    csv_file: UploadFile = File(..., description="CSV文件"),
    db: Session = Depends(get_db)
):
    """处理CSV文件和图片上传"""
    try:
        # 验证文件类型
        if not csv_file.filename.lower().endswith('.csv'):
            raise ValueError("只支持CSV文件格式")
        
        # 验证文件大小 (例如限制为10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        csv_file.file.seek(0, 2)  # 移动到文件末尾
        file_size = csv_file.file.tell()
        csv_file.file.seek(0)  # 重置文件指针
        
        if file_size > max_size:
            raise ValueError("文件大小超过10MB限制")
        
        logger.info(f"开始处理CSV文件: {csv_file.filename}, 大小: {file_size}字节")
        
        # 处理CSV文件
        result = await CsvProcessService.process_csv_file(db, csv_file)
        
        logger.info(f"CSV文件处理完成: 总记录{result.total_records}, 成功{result.processed_records}, 失败{result.failed_records}")
        
        return ProcessCsvResponse(
            code=0,
            msg="处理完成",
            data=result
        )
        
    except ValueError as e:
        logger.error(f"CSV文件验证失败: {str(e)}")
        return ProcessCsvResponse(
            code=400,
            msg=str(e),
            data=None
        )
    except Exception as e:
        logger.error(f"处理CSV文件失败: {str(e)}")
        return ProcessCsvResponse(
            code=500,
            msg=f"处理失败: {str(e)}",
            data=None
        )


@router.get("/fashion_data", response_model=GetFashionDataResponse)
async def get_fashion_data(
    page: int = 1,
    page_size: int = 10,
    gender: str = None,
    type_filter: str = None,
    db: Session = Depends(get_db)
):
    """获取时尚数据列表"""
    try:
        # 验证分页参数
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 10
            
        logger.info(f"获取时尚数据列表: page={page}, page_size={page_size}, gender={gender}, type={type_filter}")
        
        # 获取数据
        result = CsvProcessService.get_fashion_data(
            db, page, page_size, gender, type_filter
        )
        
        return GetFashionDataResponse(
            code=0,
            msg="Success",
            data=result
        )
        
    except Exception as e:
        logger.error(f"获取时尚数据失败: {str(e)}")
        return GetFashionDataResponse(
            code=500,
            msg=f"获取数据失败: {str(e)}",
            data=None
        )


@router.get("/frontend/images", response_model=GetFrontendImagesResponse)
async def get_frontend_images(
    page: int = 1,
    page_size: int = 20,
    type: List[str] = Query(default=None, description="服装类型筛选，支持多个值"),
    gender: List[str] = Query(default=None, description="性别筛选，支持多个值"),
    db: Session = Depends(get_db)
):
    """获取前端图片列表（专门用于前端展示）
    
    Args:
        page: 页码，从1开始，默认1
        page_size: 每页数量，默认20，最大50
        type: 服装类型筛选，支持多个值，可选值：Evening Wear, Casual, Professional, Sportswear, Kidswear
        gender: 性别筛选，支持多个值，可选值：Female, Male
    
    Returns:
        前端图片列表，包含分页信息和图片数据
    """
    try:
        # 验证分页参数
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 50:
            page_size = 20
        
        # 验证筛选参数
        valid_types = ["Evening Wear", "Casual", "Professional", "Sportswear", "Kidswear"]
        valid_genders = ["Female", "Male"]
        
        if type:
            invalid_types = [t for t in type if t not in valid_types]
            if invalid_types:
                return GetFrontendImagesResponse(
                    code=400,
                    msg=f"无效的类型参数: {', '.join(invalid_types)}，支持的类型: {', '.join(valid_types)}",
                    data=None
                )
            
        if gender:
            invalid_genders = [g for g in gender if g not in valid_genders]
            if invalid_genders:
                return GetFrontendImagesResponse(
                    code=400,
                    msg=f"无效的性别参数: {', '.join(invalid_genders)}，支持的性别: {', '.join(valid_genders)}",
                    data=None
                )
            
        logger.info(f"获取前端图片列表: page={page}, page_size={page_size}, type={type}, gender={gender}")
        
        # 获取数据
        result = CsvProcessService.get_frontend_images(
            db, page, page_size, type, gender
        )
        
        logger.info(f"前端图片列表查询成功: 总数{result['total']}, 当前页{result['page']}, 返回{len(result['list'])}条")
        
        return GetFrontendImagesResponse(
            code=0,
            msg="Success",
            data=result
        )
        
    except Exception as e:
        logger.error(f"获取前端图片列表失败: {str(e)}")
        return GetFrontendImagesResponse(
            code=500,
            msg=f"获取数据失败: {str(e)}",
            data=None
        )


@router.get("/frontend/images/detail", response_model=GetImageDetailResponse)
async def get_image_detail(
    slug: str = None,
    record_id: str = None,
    db: Session = Depends(get_db)
):
    """获取图片详情（通过slug或record_id）
    
    Args:
        slug: URL友好标识，优先使用
        record_id: 记录ID，作为兜底参数
        
    Returns:
        图片详情信息
    """
    try:
        # 验证参数
        if not slug and not record_id:
            return GetImageDetailResponse(
                code=400,
                msg="必须提供slug或record_id参数",
                data=None
            )
        
        identifier = slug if slug else record_id
        identifier_type = "slug" if slug else "record_id"
        logger.info(f"获取图片详情: {identifier_type}={identifier}")
        
        # 获取详情数据
        detail = CsvProcessService.get_image_detail(db, slug, record_id)
        
        if not detail:
            return GetImageDetailResponse(
                code=404,
                msg=f"未找到指定的图片: {identifier_type}={identifier}",
                data=None
            )
        
        logger.info(f"图片详情获取成功: id={detail.id}, slug={detail.slug}")
        
        return GetImageDetailResponse(
            code=0,
            msg="Success",
            data=detail
        )
        
    except ValueError as e:
        logger.error(f"参数验证失败: {str(e)}")
        return GetImageDetailResponse(
            code=400,
            msg=str(e),
            data=None
        )
    except Exception as e:
        logger.error(f"获取图片详情失败: {str(e)}")
        return GetImageDetailResponse(
            code=500,
            msg=f"获取详情失败: {str(e)}",
            data=None
        )