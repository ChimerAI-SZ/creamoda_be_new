from enum import IntEnum

class SubscribeAction(IntEnum):
    """订阅动作枚举"""
    LAUNCH = 1  # 启动订阅
    CANCEL = 2   # 取消订阅