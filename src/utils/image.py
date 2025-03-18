import httpx
from io import BytesIO
from typing import Optional
from fastapi import UploadFile

from ..config.log_config import logger
from ..services.upload_service import UploadService

async def download_and_upload_image(
    image_url: str, 
    filename_prefix: str = "external_image", 
    timeout: int = 30
) -> Optional[str]:
    """
    下载外部图片并上传到阿里云OSS
    
    Args:
        image_url: 外部图片URL
        filename_prefix: 文件名前缀
        timeout: 下载超时时间(秒)
        
    Returns:
        上传成功返回OSS图片URL，失败返回None
    """
    try:
        logger.info(f"Downloading image from: {image_url}")
        
        # 下载外部图片
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            
            # 获取图片内容
            image_content = BytesIO(response.content)
            
            # 从URL中提取文件扩展名
            file_ext = ".jpg"  # 默认扩展名
            if "." in image_url.split("?")[0].split("/")[-1]:
                original_ext = image_url.split("?")[0].split("/")[-1].split(".")[-1].lower()
                if original_ext in ["jpg", "jpeg", "png", "gif", "webp"]:
                    file_ext = f".{original_ext}"
            
            # 创建一个类似UploadFile的对象
            class MockUploadFile:
                def __init__(self, content, filename):
                    self.file = content
                    self.filename = filename
                    # 根据扩展名设置内容类型
                    content_types = {
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".png": "image/png",
                        ".gif": "image/gif",
                        ".webp": "image/webp"
                    }
                    self.content_type = content_types.get(file_ext, "image/jpeg")
                
                async def read(self):
                    return self.file.getvalue()
            
            # 创建模拟文件对象
            mock_file = MockUploadFile(
                image_content, 
                f"{filename_prefix}{file_ext}"
            )
            
            # 上传到OSS
            upload_result = await UploadService.upload_to_oss(mock_file)
            oss_url = upload_result["url"]
            
            logger.info(f"Successfully uploaded image to OSS: {oss_url}")
            return oss_url
            
    except Exception as e:
        logger.error(f"Failed to download and upload image: {str(e)}")
        return None 