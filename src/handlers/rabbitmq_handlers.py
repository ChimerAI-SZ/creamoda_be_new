"""
RabbitMQ 消息处理器
定义各种消息类型的处理逻辑
"""

import asyncio
from typing import Dict, Any

from src.config.log_config import logger
from src.dto.mq import MQBaseDto, ImageGenerationDto
from src.services.image_service import ImageService


class RabbitMQHandlers:
    """RabbitMQ 消息处理器集合"""
    
    @staticmethod
    def handle_image_generation_message(message: Dict[str, Any]) -> bool:
        """处理图像生成消息"""
        try:
            logger.info(f"Processing image generation message: {message}")

            mq_base_dto = MQBaseDto(**message)
            img_gen_dto = ImageGenerationDto(**mq_base_dto.data)
            
            result = asyncio.run(ImageService.process_caption(img_gen_dto.genImgId))
            
            logger.info(f"Image generation task {img_gen_dto.genImgId} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error processing image generation message: {str(e)}")
            return False
    

# 消息处理器映射
MESSAGE_HANDLERS = {
    'image_generation_queue': RabbitMQHandlers.handle_image_generation_message,
} 