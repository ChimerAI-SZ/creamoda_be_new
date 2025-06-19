"""
RabbitMQ 服务层
提供高级的消息处理接口，封装常用的消息队列操作
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.core.rabbitmq_manager import rabbitmq_manager,MessageType, MessagePriority
from src.config.log_config import logger
from src.dto.mq import ImageGenerationDto


class RabbitMQService:
    """RabbitMQ 服务类"""
    
    async def send_image_generation_message(self, 
                                          task_data: ImageGenerationDto,
                                          priority: MessagePriority = MessagePriority.NORMAL) -> bool:
        """发送图像生成消息"""
        return await rabbitmq_manager.send_message(
            exchange_name=rabbitmq_manager.default_exchange,
            routing_key="image.generation",
            message=task_data,
            message_type=MessageType.IMAGE_GENERATION,
            priority=priority
        )
    
# 全局 RabbitMQ 服务实例
rabbitmq_service = RabbitMQService() 