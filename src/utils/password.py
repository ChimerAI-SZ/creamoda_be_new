import hashlib
import random
import string


def generate_salt(length: int = 16) -> str:
    """生成随机盐值"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def hash_password(password: str, salt: str) -> str:
    """使用MD5+salt加密密码"""
    return hashlib.md5(f"{password}{salt}".encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str, salt: str) -> bool:
    """验证密码"""
    hashed_input_pwd = hash_password(plain_password, salt)
    return hashed_input_pwd == hashed_password 