from enum import IntEnum

class OrderStatus(IntEnum):
    """订单状态枚举"""
    PAYMENT_SUCCESS = 1  # 支付成功
    PAYMENT_FAILED = 2   # 支付失败
    PAYMENT_PENDING = 3  # 支付中
    PAYMENT_CAPTURED = 4  # 捕获成功
