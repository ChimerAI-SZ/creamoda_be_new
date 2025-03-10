import pytest
from src.validators.user import UserValidator
from src.exceptions.user import ValidationError

def test_validate_username_valid():
    # 测试有效的用户名
    valid_usernames = [
        "user123",
        "john_doe",
        "jane-doe",
        "user.name",
        "用户名123",
        "ユーザー名",
        "abc"  # 最小长度
    ]
    
    for username in valid_usernames:
        UserValidator.validate_username(username)  # 不应抛出异常

def test_validate_username_invalid_length():
    # 测试无效长度
    with pytest.raises(ValidationError, match="at least 3 characters"):
        UserValidator.validate_username("ab")
    
    with pytest.raises(ValidationError, match="cannot exceed 20 characters"):
        UserValidator.validate_username("a" * 21)

def test_validate_username_invalid_chars():
    # 测试无效字符
    invalid_usernames = [
        "user name",  # 包含空格
        "user@name",  # 包含@
        "user#name",  # 包含#
        "user$name",  # 包含$
        "user%name",  # 包含%
    ]
    
    for username in invalid_usernames:
        with pytest.raises(ValidationError, match="contains invalid characters"):
            UserValidator.validate_username(username) 