from datetime import datetime
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from src.config.config import settings
from src.config.log_config import logger
from src.db.redis import redis_client
from src.db.session import get_db
from src.dto.user import (LogoutResponse, UserLoginData, UserLoginRequest,
                         UserLoginResponse, UserRegisterRequest,
                         UserRegisterResponse, EmailVerifyRequest, EmailVerifyResponse)
from src.exceptions.user import AuthenticationError, ValidationError
from src.models.models import UserInfo
from src.utils.email import email_sender
from src.utils.password import generate_salt, hash_password
from src.utils.security import create_access_token
from src.utils.uid import generate_uid
from src.utils.username import generate_username
from src.utils.verification import generate_verification_code
from src.validators.user import UserValidator
from src.core.context import get_current_user_context
from src.dto.common import CommonResponse
import asyncio

router = APIRouter()

@router.post("/register", response_model=UserRegisterResponse)
async def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """用户注册"""
    try:
        # 验证邮箱格式
        UserValidator.validate_email(request.email)
        
        # 验证用户名格式
        UserValidator.validate_username(request.username)
        
        # 验证密码强度
        UserValidator.validate_password(request.pwd)
        
        # 检查邮箱是否已存在
        existing_user = db.query(UserInfo).filter(UserInfo.email == request.email).first()
        if existing_user:
            raise ValidationError("Email already registered")
        
        # 生成盐值和密码哈希
        salt = generate_salt()
        hashed_password = hash_password(request.pwd, salt)
        
        # 生成用户ID
        uid = generate_uid()
        
        # 创建用户
        new_user = UserInfo(
            email=request.email,
            pwd=hashed_password,
            salt=salt,
            uid=uid,
            username=request.username,  # 使用请求中的用户名
            status=1,  # 正常状态
            email_verified=2,  # 邮箱未验证
            create_time=datetime.utcnow(),
            update_time=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        
        # 生成验证码并发送验证邮件
        verification_code = generate_verification_code()
        
        # 存储验证码到Redis，24小时有效
        redis_client.setex(f"email_verify:{new_user.id}", 86400, verification_code)
        
        # 异步发送验证邮件
        asyncio.create_task(
            email_sender.send_verification_email_async(
                request.email,
                verification_code,
                new_user.id
            )
        )
        
        return UserRegisterResponse(
            code=0,
            msg="Registration successful. Please check your email to verify your account."
        )
        
    except ValidationError as e:
        # 验证错误
        raise e
    except Exception as e:
        # 其他错误
        logger.error(f"Registration error: {str(e)}")
        raise ValidationError(f"Registration failed: {str(e)}")

@router.post("/login", response_model=UserLoginResponse)
async def login(
    request: UserLoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """用户登录接口"""
    try:
        # 验证邮箱格式
        UserValidator.validate_email(request.email)
        
        # 验证用户密码
        user = UserValidator.validate_login(db, request.email, request.pwd)
        
        # 更新登录时间
        now = datetime.utcnow()
        user.last_login_time = now
        user.update_time = now
        db.commit()
        
        # 生成访问令牌
        access_token = create_access_token({"sub": user.email})
        bearer_token = f"Bearer {access_token}"
        
        # 使用Redis存储用户会话信息
        redis_client.setex(
            f"user_session:{user.email}",
            settings.security.access_token_expire_minutes * 60,  # 转换为秒
            access_token
        )
        
        # 设置Authorization header
        response.headers["Authorization"] = bearer_token
        
        return UserLoginResponse(
            code=0,
            msg="Login successful",
            data=UserLoginData(
                authorization=bearer_token.replace("+", "%2B")  # 转义 + 字符
            )
        )
        
    except (ValidationError, AuthenticationError) as e:
        logger.error(f"Login validation failed: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise AuthenticationError()

@router.post("/logout", response_model=LogoutResponse)
async def logout(
    authorization: Optional[str] = Header(None)
):
    """用户登出接口"""
    try:
        if not authorization:
            return LogoutResponse(
                code=0,
                msg="Logout successful"
            )

        # 从 header 中提取 token
        token_parts = authorization.split()
        if len(token_parts) != 2 or token_parts[0].lower() != "bearer":
            return LogoutResponse(
                code=0,
                msg="Logout successful"
            )
            
        access_token = token_parts[1]
        
        try:
            # 解析 token 获取用户信息
            payload = jwt.decode(
                access_token,
                settings.security.jwt_secret_key,
                algorithms=[settings.security.jwt_algorithm]
            )
            email = payload.get("sub")
            
            if email:
                # 从 Redis 中删除会话信息
                redis_client.delete(f"user_session:{email}")
                logger.info(f"User {email} logged out successfully")
                
        except jwt.JWTError:
            logger.warning("Invalid token during logout")
            
        return LogoutResponse(
            code=0,
            msg="Logout successful"
        )
        
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        return LogoutResponse(
            code=0,
            msg="Logout successful"
        )

@router.get("/info")
async def get_user_info():
    """获取用户信息"""
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
        
    return CommonResponse(
        code=0,
        msg="success",
        data={
            "username": user.username,
            "email": user.email,
            "status": user.status,
            "emailVerified": user.email_verified
        }
    )

@router.post("/email/verify", response_model=EmailVerifyResponse)
async def verify_email(
    request: EmailVerifyRequest,
    db: Session = Depends(get_db)
):
    """验证用户邮箱接口"""
    try:
        # 从Redis获取验证码对应的用户ID
        redis_key = f"email_verification:{request.verifyCode}"
        user_id = redis_client.get(redis_key)
        
        if not user_id:
            raise ValidationError("Invalid or expired verification code")
            
        # 查询用户
        user = db.query(UserInfo).filter(UserInfo.id == int(user_id)).first()
        if not user:
            raise ValidationError("User not found")
            
        # 更新用户邮箱验证状态
        user.email_verified = 1
        user.update_time = datetime.utcnow()
        
        try:
            db.commit()
            # 验证成功后删除Redis中的验证码
            redis_client.delete(redis_key)
            logger.info(f"Email verified successfully for user {user.email}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Database error during email verification: {str(e)}")
            raise ValidationError("Failed to verify email")
            
        return EmailVerifyResponse(
            code=0,
            msg="Email verified successfully"
        )
        
    except ValidationError as e:
        logger.error(f"Email verification failed: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during email verification: {str(e)}")
        raise ValidationError("Failed to verify email")