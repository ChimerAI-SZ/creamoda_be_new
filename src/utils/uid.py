import random
import time


def generate_uid() -> str:
    """生成用户唯一ID
    格式: 时间戳(10位) + 随机数(6位)
    """
    timestamp = str(int(time.time()))
    random_num = str(random.randint(100000, 999999))
    return f"{timestamp}{random_num}" 