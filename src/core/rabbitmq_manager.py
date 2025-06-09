"""
RabbitMQ 管理器
负责 RabbitMQ 连接管理、消息发送和消费者管理
"""

import asyncio
import json
import traceback
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum

import pika
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.exchange_type import ExchangeType

from src.config.log_config import logger
from src.config.config import settings
from src.exceptions.base import CustomException
from src.handlers.rabbitmq_handlers import MESSAGE_HANDLERS


class MessagePriority(Enum):
    """消息优先级枚举"""
    LOW = 1
    NORMAL = 5
    HIGH = 10


class MessageType(Enum):
    """消息类型枚举"""
    IMAGE_GENERATION = "image_generation"

class RabbitMQManager:
    """RabbitMQ 管理器"""
    
    def __init__(self):
        self.default_exchange = "creamoda_exchange"
        self.initialized = False
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.consumers: Dict[str, Callable] = {}
        self.is_connected = False
        self._connection_params = None
        self._setup_connection_params()

    async def initialize(self):
        """初始化 RabbitMQ 服务"""
        try:
            if self.initialized:
                return True
            
            # 连接到 RabbitMQ
            connected = await self.connect()
            if not connected:
                logger.error("Failed to connect to RabbitMQ")
                return False
            
            # 声明默认的交换机和队列
            await self._setup_default_queues()

            for queue_name, handler in MESSAGE_HANDLERS.items():
                self.register_consumer(queue_name, handler)
            self.start_all_consumers()
            
            self.initialized = True
            logger.info("RabbitMQ service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize RabbitMQ service: {str(e)}")
            return False
    
    async def _setup_default_queues(self):
        """设置默认的队列"""
        try:
            # 图像生成队列
            self.declare_exchange_and_queue(
                exchange_name=self.default_exchange,
                queue_name="image_generation_queue",
                routing_key="image.generation"
            )
            
            logger.info("Default queues setup completed")
        except Exception as e:
            logger.error(f"Failed to setup default queues: {str(e)}")
            raise

    def _setup_connection_params(self):
        """设置连接参数"""
        try:
            # 从配置中获取 RabbitMQ 连接参数
            rabbitmq_config = getattr(settings, 'rabbitmq', None)
            if rabbitmq_config:
                host = getattr(rabbitmq_config, 'host', 'localhost')
                port = getattr(rabbitmq_config, 'port', 5672)
                username = getattr(rabbitmq_config, 'username', 'guest')
                password = getattr(rabbitmq_config, 'password', 'guest')
                virtual_host = getattr(rabbitmq_config, 'virtual_host', '/')
            else:
                raise CustomException("RabbitMQ 配置未找到")
            
            credentials = pika.PlainCredentials(username, password)
            self._connection_params = pika.ConnectionParameters(
                host=host,
                port=port,
                virtual_host=virtual_host,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            logger.info(f"RabbitMQ connection params set: {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to setup RabbitMQ connection params: {str(e)}")
            raise

    def start_consumers(self):
        """启动所有消费者"""
        try:
            self.start_all_consumers()
        except Exception as e:
            logger.error(f"Error starting consumers: {str(e)}")
            raise
    
    def stop_consumers(self):
        """停止所有消费者"""
        self.stop_consuming()
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """获取所有队列状态"""
        queues = [
            "image_generation_queue"
        ]
        
        status = {}
        for queue in queues:
            status[queue] = self.get_queue_info(queue)
        
        return status
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return self.health_check()
    
    async def shutdown(self):
        """关闭服务"""
        try:
            self.stop_consumers()
            await self.disconnect()
            self.initialized = False
            logger.info("RabbitMQ service shutdown completed")
        except Exception as e:
            logger.error(f"Error during RabbitMQ service shutdown: {str(e)}")

    async def connect(self) -> bool:
        """连接到 RabbitMQ"""
        try:
            if self.is_connected:
                return True
            
            self.connection = pika.BlockingConnection(self._connection_params)
            self.channel = self.connection.channel()
            
            # 设置 QoS
            self.channel.basic_qos(prefetch_count=10)
            
            self.is_connected = True
            logger.info("Successfully connected to RabbitMQ")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """断开 RabbitMQ 连接"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            self.is_connected = False
            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {str(e)}")
    
    def _ensure_connection(self):
        """确保连接可用"""
        if not self.is_connected or not self.connection or self.connection.is_closed:
            # 同步重连
            try:
                self.connection = pika.BlockingConnection(self._connection_params)
                self.channel = self.connection.channel()
                self.channel.basic_qos(prefetch_count=10)
                self.is_connected = True
                logger.info("Reconnected to RabbitMQ")
            except Exception as e:
                logger.error(f"Failed to reconnect to RabbitMQ: {str(e)}")
                raise
    
    def declare_exchange_and_queue(self, exchange_name: str, queue_name: str, 
                                 routing_key: str = "", exchange_type: str = "direct"):
        """声明交换机和队列"""
        try:
            self._ensure_connection()
            
            # 声明交换机
            self.channel.exchange_declare(
                exchange=exchange_name,
                exchange_type=exchange_type,
                durable=True
            )
            
            # 声明队列（支持优先级）
            self.channel.queue_declare(
                queue=queue_name,
                durable=True,
                arguments={'x-max-priority': 10}
            )
            
            # 绑定队列到交换机
            self.channel.queue_bind(
                exchange=exchange_name,
                queue=queue_name,
                routing_key=routing_key or queue_name
            )
            
            logger.info(f"Declared exchange '{exchange_name}' and queue '{queue_name}'")
        except Exception as e:
            logger.error(f"Failed to declare exchange and queue: {str(e)}")
            raise
    
    async def send_message(self, 
                          exchange_name: str,
                          routing_key: str,
                          message: Dict[str, Any],
                          message_type: MessageType = MessageType.IMAGE_GENERATION,
                          priority: MessagePriority = MessagePriority.NORMAL) -> bool:
        """发送消息"""
        try:
            self._ensure_connection()
            
            # 构造消息体
            message_body = {
                "id": f"{datetime.now().timestamp()}_{message_type.value}",
                "type": message_type.value,
                "timestamp": datetime.now().isoformat(),
                "priority": priority.value,
                "data": message
            }
            
            # 发送消息
            self.channel.basic_publish(
                exchange=exchange_name,
                routing_key=routing_key,
                body=json.dumps(message_body, ensure_ascii=False),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # 持久化消息
                    priority=priority.value,
                    content_type='application/json',
                    timestamp=int(datetime.now().timestamp())
                )
            )
            
            logger.info(f"Message sent to {exchange_name}/{routing_key}: {message_type.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            return False
    
    def register_consumer(self, queue_name: str, callback: Callable):
        """注册消费者"""
        self.consumers[queue_name] = callback
        logger.info(f"Registered consumer for queue: {queue_name}")
    
    def start_consuming(self, queue_name: str):
        """开始消费消息"""
        try:
            self._ensure_connection()
            
            if queue_name not in self.consumers:
                logger.error(f"No consumer registered for queue: {queue_name}")
                return
            
            callback = self.consumers[queue_name]
            
            def wrapper(ch, method, properties, body):
                try:
                    # 解析消息
                    message = json.loads(body.decode('utf-8'))
                    logger.info(f"Received message from {queue_name}: {message.get('type', 'unknown')}")
                    
                    # 调用回调函数
                    result = callback(message)
                    
                    # 确认消息
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.debug(f"Message processed successfully from {queue_name}")
                    
                except Exception as e:
                    logger.error(f"Error processing message from {queue_name}: {str(e)}")
                    logger.error(traceback.format_exc())
                    # 拒绝消息并重新排队
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
            # 设置消费者
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=wrapper
            )
            
            logger.info(f"Started consuming from queue: {queue_name}")
            
        except Exception as e:
            logger.error(f"Failed to start consuming from {queue_name}: {str(e)}")
            raise
    
    def start_all_consumers(self):
        """启动所有消费者"""
        try:
            if not self.consumers:
                logger.info("No consumers registered")
                return
            
            for queue_name in self.consumers.keys():
                self.start_consuming(queue_name)
            
            logger.info("Starting to consume messages...")
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Stopping consumers...")
            self.channel.stop_consuming()
        except Exception as e:
            logger.error(f"Error in consumer loop: {str(e)}")
            raise
    
    def stop_consuming(self):
        """停止消费"""
        try:
            if self.channel:
                self.channel.stop_consuming()
            logger.info("Stopped consuming messages")
        except Exception as e:
            logger.error(f"Error stopping consumers: {str(e)}")
    
    def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """获取队列信息"""
        try:
            self._ensure_connection()
            method = self.channel.queue_declare(queue=queue_name, passive=True)
            return {
                "queue": queue_name,
                "message_count": method.method.message_count,
                "consumer_count": method.method.consumer_count
            }
        except Exception as e:
            logger.error(f"Failed to get queue info for {queue_name}: {str(e)}")
            return {}
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            self._ensure_connection()
            return {
                "status": "healthy",
                "connected": self.is_connected,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# 全局 RabbitMQ 管理器实例
rabbitmq_manager = RabbitMQManager() 