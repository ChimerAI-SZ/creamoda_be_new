import random
import string


def generate_username() -> str:
    """生成随机用户名
    格式: user_ + 12位随机字符(字母+数字)
    示例: user_a1b2c3d4
    """
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"user_{random_chars}" 