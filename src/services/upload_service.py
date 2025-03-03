import os
import uuid
import oss2
from fastapi import UploadFile
from datetime import datetime
from ..config.config import settings
from ..config.log_config import logger

class UploadService:
    @staticmethod
    async def upload_to_oss(file: UploadFile, dir_prefix: str = None) -> dict:
        """上传文件到阿里云OSS
        
        Args:
            file: 上传的文件对象
            dir_prefix: 目录前缀，默认使用配置中的upload_dir
            
        Returns:
            包含URL和文件名的字典
        """
        try:
            # 确保目录前缀
            if dir_prefix is None:
                dir_prefix = settings.oss.upload_dir
            
            # 读取文件内容
            content = await file.read()
            
            # 生成唯一文件名
            file_ext = os.path.splitext(file.filename)[1]
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            random_str = str(uuid.uuid4()).replace('-', '')[:8]
            filename = f"{timestamp}_{random_str}{file_ext}"
            
            # 完整的OSS对象键
            object_key = f"{dir_prefix.rstrip('/')}/{filename}"
            
            # 初始化OSS客户端
            auth = oss2.Auth(settings.oss.access_key_id, settings.oss.access_key_secret)
            bucket = oss2.Bucket(auth, settings.oss.endpoint, settings.oss.bucket_name)
            
            # 上传文件
            bucket.put_object(object_key, content)
            
            # 构建访问URL
            if settings.oss.url_prefix:
                url = f"{settings.oss.url_prefix.rstrip('/')}/{object_key}"
            else:
                url = f"https://{settings.oss.bucket_name}.{settings.oss.endpoint}/{object_key}"
            
            logger.info(f"File uploaded to OSS: {object_key}")
            
            return {
                "url": url,
                "filename": filename
            }
            
        except Exception as e:
            logger.error(f"Failed to upload file to OSS: {str(e)}")
            raise 