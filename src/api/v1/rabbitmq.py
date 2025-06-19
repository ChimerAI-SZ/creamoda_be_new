"""
RabbitMQ API 路由
提供消息发送和状态查询接口
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

from src.services.rabbitmq_service import rabbitmq_service
from src.core.rabbitmq_manager import MessageType, MessagePriority
from src.config.log_config import logger

router = APIRouter(prefix="/rabbitmq", tags=["RabbitMQ"])


class SendMessageRequest(BaseModel):
    """发送消息请求模型"""
    message_type: str
    data: Dict[str, Any]
    priority: str = "normal"
    routing_key: Optional[str] = None


class MessageResponse(BaseModel):
    """消息响应模型"""
    success: bool
    message: str
    message_id: Optional[str] = None


@router.post("/send-message", response_model=MessageResponse)
async def send_message(request: SendMessageRequest):
    """发送消息到 RabbitMQ"""
    try:
        # 验证消息类型
        try:
            msg_type = MessageType(request.message_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid message type: {request.message_type}"
            )
        
        # 验证优先级
        try:
            priority = MessagePriority[request.priority.upper()]
        except KeyError:
            priority = MessagePriority.NORMAL
        
        # 根据消息类型发送消息
        success = False
        if msg_type == MessageType.IMAGE_GENERATION:
            success = await rabbitmq_service.send_image_generation_message(
                request.data, priority
            )
        elif msg_type == MessageType.VIDEO_PROCESSING:
            success = await rabbitmq_service.send_video_processing_message(
                request.data, priority
            )
        elif msg_type == MessageType.NOTIFICATION:
            success = await rabbitmq_service.send_notification_message(
                request.data, priority
            )
        elif msg_type == MessageType.EMAIL:
            success = await rabbitmq_service.send_email_message(
                request.data, priority
            )
        elif msg_type == MessageType.TASK_COMPLETION:
            success = await rabbitmq_service.send_task_completion_message(
                request.data, priority
            )
        elif msg_type == MessageType.SYSTEM_ALERT:
            success = await rabbitmq_service.send_system_alert_message(
                request.data, priority
            )
        
        if success:
            return MessageResponse(
                success=True,
                message="Message sent successfully",
                message_id=f"{msg_type.value}_{int(request.data.get('timestamp', 0))}"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send message"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """RabbitMQ 健康检查"""
    try:
        health_status = await rabbitmq_service.health_check()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/queue-status")
async def get_queue_status():
    """获取队列状态"""
    try:
        status = await rabbitmq_service.get_queue_status()
        return {
            "success": True,
            "data": status,
            "timestamp": logger.info("Queue status retrieved successfully")
        }
    except Exception as e:
        logger.error(f"Failed to get queue status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get queue status: {str(e)}"
        )


@router.post("/send-image-generation")
async def send_image_generation_message(
    task_id: str,
    user_id: int,
    generation_type: str,
    parameters: Dict[str, Any],
    priority: str = "normal"
):
    """发送图像生成消息的便捷接口"""
    try:
        priority_enum = MessagePriority[priority.upper()]
    except KeyError:
        priority_enum = MessagePriority.NORMAL
    
    message_data = {
        "task_id": task_id,
        "user_id": user_id,
        "type": generation_type,
        "parameters": parameters
    }
    
    success = await rabbitmq_service.send_image_generation_message(
        message_data, priority_enum
    )
    
    if success:
        return {"success": True, "message": "Image generation message sent"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send image generation message"
        )


@router.post("/send-notification")
async def send_notification_message(
    user_id: int,
    notification_type: str,
    title: str,
    content: str,
    extra_data: Optional[Dict[str, Any]] = None,
    priority: str = "normal"
):
    """发送通知消息的便捷接口"""
    try:
        priority_enum = MessagePriority[priority.upper()]
    except KeyError:
        priority_enum = MessagePriority.NORMAL
    
    message_data = {
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "content": content,
        "extra_data": extra_data or {}
    }
    
    success = await rabbitmq_service.send_notification_message(
        message_data, priority_enum
    )
    
    if success:
        return {"success": True, "message": "Notification message sent"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send notification message"
        )


@router.post("/send-email")
async def send_email_message(
    to_email: str,
    subject: str,
    content: str,
    email_type: str = "general",
    template_data: Optional[Dict[str, Any]] = None,
    priority: str = "normal"
):
    """发送邮件消息的便捷接口"""
    try:
        priority_enum = MessagePriority[priority.upper()]
    except KeyError:
        priority_enum = MessagePriority.NORMAL
    
    message_data = {
        "to_email": to_email,
        "subject": subject,
        "content": content,
        "type": email_type,
        "template_data": template_data or {}
    }
    
    success = await rabbitmq_service.send_email_message(
        message_data, priority_enum
    )
    
    if success:
        return {"success": True, "message": "Email message sent"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send email message"
        )


@router.post("/send-system-alert")
async def send_system_alert_message(
    alert_type: str,
    title: str,
    description: str,
    severity: str = "medium",
    source: Optional[str] = None
):
    """发送系统告警消息的便捷接口"""
    message_data = {
        "alert_type": alert_type,
        "severity": severity,
        "title": title,
        "description": description,
        "source": source or "api"
    }
    
    success = await rabbitmq_service.send_system_alert_message(
        message_data, MessagePriority.HIGH
    )
    
    if success:
        return {"success": True, "message": "System alert message sent"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send system alert message"
        ) 