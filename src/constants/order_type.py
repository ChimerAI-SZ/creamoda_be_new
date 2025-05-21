from enum import IntEnum
from typing import NamedTuple

class OrderType(IntEnum):
    # 会员订阅类型 (100系列)
    BASIC_MEMBERSHIP = 101  # 普通会员订阅
    PRO_MEMBERSHIP = 102    # 专业会员订阅
    ENTERPRISE_MEMBERSHIP = 103  # 企业会员订阅
    
    # 积分购买类型 (200系列)
    POINTS_40 = 201   # 40积分购买
    POINTS_100 = 202  # 100积分购买
    POINTS_200 = 203  # 200积分购买

class OrderInfo(NamedTuple):
    type: OrderType
    name: str
    price: float  # 单位：美元

# 订单类型与价格映射
ORDER_TYPE_MAPPING = {
    OrderType.BASIC_MEMBERSHIP: OrderInfo(
        OrderType.BASIC_MEMBERSHIP, 
        "Basic Membership", 
        19.9, 
    ),
    OrderType.PRO_MEMBERSHIP: OrderInfo(
        OrderType.PRO_MEMBERSHIP, 
        "Pro Membership", 
        39.9, 
    ),
    OrderType.ENTERPRISE_MEMBERSHIP: OrderInfo(
        OrderType.ENTERPRISE_MEMBERSHIP, 
        "Enterprise Membership", 
        59.9, 
    ),
    OrderType.POINTS_40: OrderInfo(
        OrderType.POINTS_40, 
        "40 Points Package", 
        5, 
    ),
    OrderType.POINTS_100: OrderInfo(
        OrderType.POINTS_100, 
        "100 Points Package", 
        10, 
    ),
    OrderType.POINTS_200: OrderInfo(
        OrderType.POINTS_200, 
        "200 Points Package", 
        19, 
    ),
}

# 获取订单价格的辅助函数
def get_order_price(order_type: OrderType) -> float:
    """根据订单类型获取价格"""
    return ORDER_TYPE_MAPPING[order_type].price

# 获取订单信息的辅助函数
def get_order_info(order_type: OrderType) -> OrderInfo:
    """根据订单类型获取完整订单信息"""
    return ORDER_TYPE_MAPPING[order_type]