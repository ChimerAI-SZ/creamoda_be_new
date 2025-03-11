import random
import string


def generate_verification_code(length: int = 6, digits_only: bool = True) -> str:
    """生成随机验证码
    :param length: 验证码长度
    :param digits_only: 是否仅使用数字
    :return: 验证码字符串
    """
    if digits_only:
        # 生成纯数字验证码
        return ''.join(random.choices(string.digits, k=length))
    else:
        # 生成字母+数字验证码
        chars = string.ascii_letters + string.digits
        return ''.join(random.choices(chars, k=length)) 