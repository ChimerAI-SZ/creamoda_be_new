"""
密码加密和验证模块
- 新用户/密码重置：使用 bcrypt 加密（业界标准）
- 旧用户兼容：支持 MD5+salt 验证并自动升级为 bcrypt
- 渐进式迁移：用户下次登录时自动升级密码
"""
import hashlib
import random
import string
import bcrypt
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from src.config.log_config import logger


def generate_salt(length: int = 16) -> str:
    """
    生成随机盐值（已废弃，仅用于向后兼容）
    
    Warning:
        此方法仅用于兼容旧的 MD5 加密方式
        新代码不应使用此方法，bcrypt 会自动管理 salt
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def hash_password_md5(password: str, salt: str) -> str:
    """
    使用MD5+salt加密密码（已废弃，仅用于验证旧密码）
    
    Warning:
        此方法已废弃，仅用于验证历史遗留的 MD5 密码
        不应用于新用户注册或密码重置
    """
    return hashlib.md5(f"{password}{salt}".encode()).hexdigest()


def hash_password(password: str) -> str:
    """
    使用 bcrypt 加密密码（推荐方式）
    
    Args:
        password: 明文密码
        
    Returns:
        bcrypt 加密后的密码哈希值
        
    Note:
        - bcrypt 自动生成 salt，无需手动管理
        - 返回的哈希值包含算法标识、cost、salt 和 hash
        - 格式：$2b$12$salt22characters.hash31characters
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str, salt: Optional[str] = None) -> bool:
    """
    验证密码是否正确（支持 bcrypt 和 MD5 双模式）
    
    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的密码哈希值
        salt: 可选的 salt（仅用于 MD5 验证）
        
    Returns:
        True if 密码正确, False otherwise
        
    Note:
        验证策略：
        1. 优先尝试 bcrypt 验证（以 $2b$ 或 $2a$ 开头）
        2. 如果不是 bcrypt 格式且提供了 salt，则尝试 MD5 验证
        3. 其他情况返回 False
    """
    try:
        # 策略1: bcrypt 格式验证
        if hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$'):
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        
        # 策略2: MD5 降级验证（兼容旧密码）
        if salt:
            logger.info(f"使用 MD5 验证旧密码格式（将在验证成功后自动升级）")
            hashed_input_pwd = hash_password_md5(plain_password, salt)
            return hashed_input_pwd == hashed_password
        
        # 策略3: 无法识别的格式
        logger.warning(f"无法识别的密码哈希格式且未提供 salt")
        return False
        
    except Exception as e:
        logger.error(f"密码验证失败: {str(e)}")
        return False


def should_upgrade_password(hashed_password: str) -> bool:
    """
    检查密码是否需要升级为 bcrypt
    
    Args:
        hashed_password: 数据库中存储的密码哈希值
        
    Returns:
        True if 需要升级（MD5格式）, False if 已经是 bcrypt 格式
    """
    return not (hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$'))


def upgrade_user_password(db: Session, user, plain_password: str) -> bool:
    """
    将用户的 MD5 密码升级为 bcrypt（在登录验证成功后调用）
    
    Args:
        db: 数据库会话
        user: 用户对象（需要有 pwd 和 salt 属性）
        plain_password: 用户刚刚验证成功的明文密码
        
    Returns:
        True if 升级成功, False otherwise
        
    Note:
        此函数应在密码验证成功后立即调用
        升级后 salt 字段将被清空（bcrypt 不需要单独的 salt）
    """
    try:
        # 生成新的 bcrypt 哈希
        new_hashed_password = hash_password(plain_password)
        
        # 更新数据库
        user.pwd = new_hashed_password
        user.salt = None  # 清空 salt，bcrypt 不需要
        db.commit()
        
        logger.info(f"成功将用户 {user.email} 的密码升级为 bcrypt 格式")
        return True
        
    except Exception as e:
        logger.error(f"升级用户 {user.email} 密码失败: {str(e)}")
        db.rollback()
        return False 