import re

from sqlalchemy.orm import Session

from ..exceptions.user import AuthenticationError, ValidationError
from ..models.models import UserInfo  # 使用生成的模型
from ..utils.password import verify_password


class UserValidator:
    @staticmethod
    def validate_email(email: str) -> None:
        """验证邮箱格式"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationError("Invalid email format")

    @staticmethod
    def validate_username(username: str) -> None:
        """验证用户名格式
        
        规则:
        - 长度: 3-20个字符
        - 允许: 字母(A-Z, a-z)、数字(0-9)、特殊字符(_, -, .)和Unicode字符(如中文、日文)
        - 不允许: 其他特殊字符和空格
        """
        # 检查长度
        if len(username) < 3:
            raise ValidationError("Username must be at least 3 characters")
        if len(username) > 20:
            raise ValidationError("Username cannot exceed 20 characters")
            
        # 检查字符
        # 使用更简单的方法检查无效字符
        invalid_chars = set()
        for char in username:
            # 允许字母、数字、下划线、连字符、点
            if not (char.isalnum() or char == '_' or char == '-' or char == '.'):
                invalid_chars.add(char)
        
        if invalid_chars:
            chars_str = ', '.join([f"'{c}'" for c in invalid_chars])
            raise ValidationError(f"Username contains invalid characters: {chars_str}. Only letters, numbers, underscores, hyphens, and dots are allowed.")

    @staticmethod
    def validate_password(password: str) -> None:
        """验证密码强度"""
        if len(password) < 6:
            raise ValidationError("Password must be at least 6 characters")
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter")
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one number")

    @staticmethod
    def validate_login(db: Session, email: str, password: str) -> UserInfo:
        """验证用户登录"""
        user = db.query(UserInfo).filter(UserInfo.email == email).first()
        if not user:
            raise AuthenticationError("User not found")
        
        # 验证用户状态
        if user.status != 1:
            raise AuthenticationError("Account is disabled")
            
        # 验证邮箱是否已验证
        if user.email_verified != 1:
            raise AuthenticationError("Email not verified")
        
        # 验证密码
        if not verify_password(password, user.pwd, user.salt):
            raise AuthenticationError("Invalid password")
        
        return user 