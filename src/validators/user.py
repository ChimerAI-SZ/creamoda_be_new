import re

from sqlalchemy.orm import Session

from ..exceptions.user import AuthenticationError, EmailVerifiedError, ValidationError, UserInfoError
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
        """验证密码强度
        
        规则:
        - 最小长度：密码至少包含8个字符
        - 最大长度：密码最多包含50个字符
        - 大写字母（A-Z）：至少包含一个大写字母
        - 小写字母（a-z）：至少包含一个小写字母
        - 数字（0-9）：至少包含一个数字
        - 特殊字符：至少包含一个特殊字符 (!, @, #, $, %, ^, &, *, (, ), -, _, +, =)
        - 不允许使用除上述字符之外的其他字符
        """
        # 检查长度
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters")
        if len(password) > 50:
            raise ValidationError("Password cannot exceed 50 characters")
            
        # 检查必需字符
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter")
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one number")
        if not re.search(r'[!@#$%^&*()\-_+=]', password):
            raise ValidationError("Password must contain at least one special character: !, @, #, $, %, ^, &, *, (, ), -, _, +, =")
            
        # 检查是否包含不允许的字符
        allowed_pattern = r'^[A-Za-z0-9!@#$%^&*()\-_+=]+$'
        if not re.match(allowed_pattern, password):
            raise ValidationError("Password contains invalid characters. Only letters, numbers, and the following special characters are allowed: !, @, #, $, %, ^, &, *, (, ), -, _, +, =")

    @staticmethod
    def validate_login(db: Session, email: str, password: str) -> UserInfo:
        """验证用户登录"""
        user = db.query(UserInfo).filter(UserInfo.email == email).first()
        if not user:
            raise UserInfoError("User not found")
        
        # 验证用户状态
        if user.status != 1:
            raise UserInfoError("Account is disabled")
            
        # 验证邮箱是否已验证
        if user.email_verified != 1:
            raise EmailVerifiedError("Email not verified")
        
        # 验证密码
        if not verify_password(password, user.pwd, user.salt):
            raise UserInfoError("Invalid password")
        
        return user 