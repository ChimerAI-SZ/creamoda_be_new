import hashlib
import random
import string
import bcrypt


def generate_salt(length: int = 16) -> str:
    """生成随机盐值"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def hash_password(password: str, salt: str) -> str:
    """使用MD5+salt加密密码"""
    return hashlib.md5(f"{password}{salt}".encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str, salt: str = None) -> bool:
    """
    验证密码 - 支持两种加密方式：
    1. bcrypt (旧版本，用于兼容历史用户)
    2. MD5+Salt (当前版本)
    """
    # 检查是否是 bcrypt 加密的密码
    if hashed_password and hashed_password.startswith('$2b$'):
        try:
            # bcrypt 验证
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            print(f"bcrypt verification failed: {e}")
            return False
    
    # MD5+Salt 验证
    if salt:
        hashed_input_pwd = hash_password(plain_password, salt)
        return hashed_input_pwd == hashed_password
    
    return False 