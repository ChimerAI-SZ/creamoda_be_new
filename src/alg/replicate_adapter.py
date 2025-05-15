from src.alg.replicate import Replicate
import uuid
from io import BytesIO

from src.dto.upload_file import MockUploadFile
import logging

from src.services.upload_service import UploadService

logger = logging.getLogger(__name__)

class ReplicateAdapter:
    _adapter = None

    def __init__(self):
        self.replicate = Replicate()

    @classmethod
    def get_adapter(cls):
        if cls._adapter is None:
            cls._adapter = ReplicateAdapter()
        return cls._adapter

    async def remove_background(self, image_url: str) -> str:   
        # 获取图片二进制内容
        img_bytes = self.replicate.remove_background(image_url)
        
        # 生成唯一的文件名
        file_name = f"bg_removed_{uuid.uuid4()}.png"
        
        # 将bytes转换为BytesIO
        img_bytesio = BytesIO(img_bytes)
        
        # 上传到阿里云OSS
        mock_file = MockUploadFile(
            img_bytesio,  # 使用BytesIO对象而不是bytes
            file_name,
            ".png"
        )
        
        # 上传到OSS
        upload_result = await UploadService.upload_to_oss(mock_file)
        oss_url = upload_result["url"]
        
        # 记录日志
        logger.info(f"Uploaded background removed image to OSS: {oss_url}")
        
        # 返回OSS URL
        return oss_url

    async def upscale(self, image_url: str) -> str:
        img_bytes = self.replicate.upscale(image_url)

        # 生成唯一的文件名
        file_name = f"upscaled_{uuid.uuid4()}.png"
        
        # 将bytes转换为BytesIO
        img_bytesio = BytesIO(img_bytes)
        
        # 上传到阿里云OSS
        mock_file = MockUploadFile(
            img_bytesio,  # 使用BytesIO对象而不是bytes
            file_name,
            ".png"
        )
        
        # 上传到OSS
        upload_result = await UploadService.upload_to_oss(mock_file)
        oss_url = upload_result["url"]
        
        # 记录日志
        logger.info(f"Uploaded upscaled image to OSS: {oss_url}")
        
        # 返回OSS URL
        return oss_url
