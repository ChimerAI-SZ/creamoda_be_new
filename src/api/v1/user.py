from datetime import datetime, timedelta
from typing import Dict, Optional

import jwt
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from src.config.config import settings
from src.config.log_config import logger
from src.db.redis import redis_client
from src.db.session import get_db
from src.dto.user import (LogoutResponse, UserLoginData, UserLoginRequest,
                         UserLoginResponse, UserRegisterRequest,
                         UserRegisterResponse, EmailVerifyRequest, EmailVerifyResponse,
                         ResendEmailRequest, ResendEmailResponse)
from src.exceptions.user import AuthenticationError, ValidationError
from src.models.models import UserInfo
from src.utils.email import email_sender
from src.utils.password import generate_salt, hash_password, verify_password
from src.utils.security import create_access_token
from src.utils.uid import generate_uid
from src.utils.username import generate_username
from src.utils.verification import generate_verification_code
from src.validators.user import UserValidator
from src.core.context import get_current_user_context
from src.dto.common import CommonResponse
from src.exceptions.user import EmailVerifiedError
import asyncio

router = APIRouter()

async def generate_and_send_verification_code(db: Session, user_id: int, email: str) -> bool:
    """
    生成验证码并发送验证邮件
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        email: 用户邮箱
        
    Returns:
        bool: 是否成功发送验证码
    """
    try:
        # 生成6位数字验证码
        verification_code = generate_verification_code(6, True)
        
        # 存储验证码到Redis，10分钟有效
        redis_key = f"email_verify:{user_id}"
        redis_client.setex(redis_key, 600, verification_code)
        
        # 记录验证码信息（仅在开发环境）
        logger.info(f"Generated verification code for user {user_id}: {verification_code}")
        
        # 异步发送验证邮件
        success = await email_sender.send_verification_email_async(
            email,
            verification_code,
            user_id
        )
        
        if not success:
            logger.error(f"Failed to send verification email to {email}")
            # 如果邮件发送失败，删除Redis中的验证码
            redis_client.delete(redis_key)
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error generating and sending verification code: {str(e)}")
        return False

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
            if existing_user.email_verified == 2:
                raise EmailVerifiedError()
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
        db.refresh(new_user)
        
        # 生成验证码并发送邮件
        success = await generate_and_send_verification_code(db, new_user.id, request.email)
        
        if not success:
            return UserRegisterResponse(
                code=500,
                msg="Registration successful but failed to send verification email. Please try resending the verification email."
            )
        
        return UserRegisterResponse(
            code=0,
            msg="Registration successful. Please check your email to verify your account."
        )
        
    except ValidationError as e:
        # 验证错误
        raise e
    except EmailVerifiedError as e:
        # 邮箱未验证错误
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
        # 验证邮箱格式
        UserValidator.validate_email(request.email)

        # 验证邮箱是否存在，不存在则返回错误
        user = db.query(UserInfo).filter(UserInfo.email == request.email).first()
        if not user:
            raise ValidationError("Email not found or already verified")
        
        if user.email_verified == 1:
            raise ValidationError("Email not found or already verified")

        # 从Redis获取验证码对应的用户ID
        redis_key = f"email_verify:{user.id}"
        verifyCode = redis_client.get(redis_key)
        
        if not verifyCode:
            raise ValidationError("Invalid or expired verification code")
            
        # 验证码比较
        if verifyCode != request.verifyCode:
            raise ValidationError("Invalid verification code")
            
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
    
@router.post("/email/resend", response_model=ResendEmailResponse)
async def resend_verification_email(
    request: ResendEmailRequest,
    db: Session = Depends(get_db)
):
    """重发验证邮件"""
    try:
        # 验证邮箱格式
        UserValidator.validate_email(request.email)

        # 验证邮箱是否存在，不存在则返回错误
        user = db.query(UserInfo).filter(UserInfo.email == request.email).first()
        if not user:
            raise ValidationError("Email not found or already verified")
        
        if user.email_verified == 1:
            raise ValidationError("Email not found or already verified")
        
        # 检查是否已有验证码
        redis_key = f"email_verify:{user.id}"
        existing_code = redis_client.get(redis_key)
        
        # 如果已有验证码且未过期，返回错误
        if existing_code:
            # 获取剩余过期时间
            ttl = redis_client.ttl(redis_key)
            if ttl > 0:
                # 转换为分钟，向上取整
                minutes_left = (ttl + 59) // 60
                raise ValidationError(f"Verification code already sent. Please wait {minutes_left} minutes before requesting a new one.")
        
        # 生成新的验证码并发送邮件
        success = await generate_and_send_verification_code(db, user.id, request.email)
        
        if not success:
            return ResendEmailResponse(
                code=500,
                msg="Failed to send verification email. Please try again later."
            )
        
        return ResendEmailResponse(
            code=0,
            msg="Verification email sent successfully. Please check your email."
        )
        
    except ValidationError as e:
        # 验证错误
        logger.error(f"Email resend failed: {str(e)}")
        raise e
    except Exception as e:
        # 其他错误
        logger.error(f"Unexpected error during email resend: {str(e)}")
        raise ValidationError("Failed to resend verification email")
