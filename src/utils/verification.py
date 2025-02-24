import random
import string


def generate_verification_code(length: int = 32) -> str:
    """生成随机验证码
    :param length: 验证码长度
    :return: 验证码字符串
    """
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length)) 