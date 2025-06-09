"""
RabbitMQ 管理器
负责 RabbitMQ 连接管理、消息发送和消费者管理
"""

import asyncio
import json
import traceback
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

import aio_pika
from aio_pika import connect_robust, Message, ExchangeType
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractQueue

from src.config.log_config import logger
from src.config.config import settings
from src.dto.mq import MQBaseDto
from src.exceptions.base import CustomException



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
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.exchange: Optional[aio_pika.abc.AbstractExchange] = None
        self.consumers: Dict[str, Callable] = {}
        self.queues: Dict[str, AbstractQueue] = {}
        self.is_connected = False
        self._connection_url = None
        self._setup_connection_url()

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

            from src.handlers.rabbitmq_handlers import MESSAGE_HANDLERS
            for queue_name, handler in MESSAGE_HANDLERS.items():
                self.register_consumer(queue_name, handler)
            await self.start_all_consumers()
            
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

    def _setup_connection_url(self):
        """设置连接URL"""
        try:
            rabbitmq_config = getattr(settings, 'rabbitmq', None)
            if rabbitmq_config:
                host = getattr(rabbitmq_config, 'host', 'localhost')
                port = getattr(rabbitmq_config, 'port', 5672)
                username = getattr(rabbitmq_config, 'username', 'guest')
                password = getattr(rabbitmq_config, 'password', 'guest')
                virtual_host = getattr(rabbitmq_config, 'virtual_host', '/')
            else:
                raise CustomException("RabbitMQ 配置未找到")
            
            # 构建连接URL
            self._connection_url = f"amqp://{username}:{password}@{host}:{port}/{virtual_host}"
            logger.info(f"RabbitMQ connection URL set: amqp://{username}:***@{host}:{port}/{virtual_host}")
        except Exception as e:
            logger.error(f"Failed to setup RabbitMQ connection URL: {str(e)}")
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
            if self.is_connected and self.connection and not self.connection.is_closed:
                return True
            
            # 使用 connect_robust 支持自动重连
            self.connection = await connect_robust(
                self._connection_url,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            
            self.channel = await self.connection.channel()
            
            # 设置 QoS
            await self.channel.set_qos(prefetch_count=10)
            
            # 声明默认交换机
            self.exchange = await self.channel.declare_exchange(
                self.default_exchange,
                ExchangeType.DIRECT,
                durable=True
            )
            
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
            # 停止所有消费者
            for queue_name in list(self.queues.keys()):
                await self._stop_queue_consuming(queue_name)
            
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
            
            self.is_connected = False
            self.queues.clear()
            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {str(e)}")
    
    async def declare_exchange_and_queue(self, exchange_name: str, queue_name: str, 
                                 routing_key: str = "", exchange_type: str = "direct"):
        """声明交换机和队列"""
        try:
            if not self.is_connected:
                await self.connect()
            
            # 声明交换机
            exchange = await self.channel.declare_exchange(
                exchange_name,
                exchange_type,
                durable=True
            )
            
            # 声明队列（支持优先级）
            queue = await self.channel.declare_queue(
                queue_name,
                durable=True,
                arguments={'x-max-priority': 10}
            )
            
            # 绑定队列到交换机
            await queue.bind(exchange, routing_key or queue_name)
            
            # 保存队列引用
            self.queues[queue_name] = queue
            
            logger.info(f"Declared exchange '{exchange_name}' and queue '{queue_name}'")
            return queue
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
            if not self.is_connected:
                await self.connect()
            
            # 构造消息体
            message_body = {
                "id":f"{datetime.now().timestamp()}_{message_type.value}",
                "type":message_type.value,
                "timestamp":datetime.now().isoformat(),
                "priority":priority.value,
                "data":message
            }
            
            # 创建消息
            aio_message = Message(
                json.dumps(message_body, ensure_ascii=False).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                priority=priority.value,
                content_type='application/json',
                timestamp=datetime.now()
            )
            
            # 获取交换机
            if exchange_name == self.default_exchange:
                exchange = self.exchange
            else:
                exchange = await self.channel.declare_exchange(
                    exchange_name,
                    ExchangeType.DIRECT,
                    durable=True
                )
            
            # 发送消息
            await exchange.publish(aio_message, routing_key=routing_key)
            
            logger.info(f"Message sent to {exchange_name}/{routing_key}: {message_type.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            return False
    
    def register_consumer(self, queue_name: str, callback: Callable):
        """注册消费者"""
        self.consumers[queue_name] = callback
        logger.info(f"Registered consumer for queue: {queue_name}")
    
    async def start_consuming(self, queue_name: str):
        """开始消费消息"""
        try:
            if not self.is_connected:
                await self.connect()
            
            if queue_name not in self.consumers:
                logger.error(f"No consumer registered for queue: {queue_name}")
                return
            
            # 获取或声明队列
            if queue_name not in self.queues:
                await self.declare_exchange_and_queue(
                    self.default_exchange,
                    queue_name,
                    queue_name
                )
            
            queue = self.queues[queue_name]
            callback = self.consumers[queue_name]
            
            async def message_handler(message: aio_pika.abc.AbstractIncomingMessage):
                async with message.process():
                    try:
                        # 解析消息
                        body = json.loads(message.body.decode('utf-8'))
                        logger.info(f"Received message from {queue_name}: {body.get('type', 'unknown')}")
                        
                        # 调用回调函数（如果是同步函数，在线程池中执行）
                        if asyncio.iscoroutinefunction(callback):
                            result = await callback(body)
                        else:
                            # 在线程池中执行同步回调
                            loop = asyncio.get_event_loop()
                            result = await loop.run_in_executor(None, callback, body)
                        
                        logger.debug(f"Message processed successfully from {queue_name}")
                        
                    except Exception as e:
                        logger.error(f"Error processing message from {queue_name}: {str(e)}")
                        logger.error(traceback.format_exc())
                        # 消息会自动重新排队（因为没有 ack）
                        raise
            
            # 开始消费
            await queue.consume(message_handler)
            logger.info(f"Started consuming from queue: {queue_name}")
            
        except Exception as e:
            logger.error(f"Failed to start consuming from {queue_name}: {str(e)}")
            raise
    
    async def start_all_consumers(self):
        """启动所有消费者"""
        try:
            if not self.consumers:
                logger.info("No consumers registered")
                return
            
            # 并发启动所有消费者
            tasks = []
            for queue_name in self.consumers.keys():
                task = asyncio.create_task(self.start_consuming(queue_name))
                tasks.append(task)
            
            # 等待所有消费者启动
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("All consumers started")
            
        except Exception as e:
            logger.error(f"Error starting consumers: {str(e)}")
            raise
    
    
    async def _stop_queue_consuming(self, queue_name: str):
        """停止特定队列的消费"""
        try:
            if queue_name in self.queues:
                queue = self.queues[queue_name]
                # aio-pika 的队列会在连接关闭时自动停止消费
                logger.info(f"Stopped consuming from queue: {queue_name}")
        except Exception as e:
            logger.error(f"Error stopping consumer for {queue_name}: {str(e)}")
    
    async def stop_consuming(self):
        """停止所有消费"""
        try:
            for queue_name in list(self.queues.keys()):
                await self._stop_queue_consuming(queue_name)
            logger.info("Stopped all consumers")
        except Exception as e:
            logger.error(f"Error stopping consumers: {str(e)}")
    
    async def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """获取队列信息"""
        try:
            if not self.is_connected:
                await self.connect()
            
            # 声明队列以获取信息（passive=True 表示不创建）
            queue = await self.channel.declare_queue(queue_name, passive=True)
            
            return {
                "queue": queue_name,
                "message_count": queue.declaration_result.message_count,
                "consumer_count": queue.declaration_result.consumer_count
            }
        except Exception as e:
            logger.error(f"Failed to get queue info for {queue_name}: {str(e)}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self.is_connected:
                await self.connect()
            
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