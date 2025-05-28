from typing import Dict, List, Optional, Union
from pydantic import BaseModel

class RateLimitRule(BaseModel):
    """限流规则配置"""
    # 时间窗口大小（秒）
    window_seconds: int
    # 窗口内允许的最大请求数
    max_requests: int
    # 是否对匿名用户应用此规则
    apply_to_anonymous: bool = True

class RateLimitConfig(BaseModel):
    """限流配置"""
    # 默认规则
    default: RateLimitRule = RateLimitRule(
        window_seconds=60,
        max_requests=60,
        apply_to_anonymous=True
    )
    
    # 按路径匹配的规则，键为路径前缀
    path_rules: Dict[str, RateLimitRule] = {
        # 登陆接口限流
        "/api/v1/user/login": RateLimitRule(
            window_seconds=300,
            max_requests=10,
            apply_to_anonymous=True
        ),
        # 邮箱验证接口限流
        "/api/v1/user/email/verify": RateLimitRule(
            window_seconds=300,
            max_requests=10,
            apply_to_anonymous=True
        ),
    }
    
    # 白名单路径（不进行限流）
    whitelist_paths: List[str] = [
        "/api/v1/user/register",
        "/api/v1/auth/google",
        "/api/v1/auth/callback",
    ]
    
    # IP黑名单
    ip_blacklist: List[str] = []
    
    # 是否启用限流
    enabled: bool = True

# 创建默认配置实例
rate_limit_settings = RateLimitConfig() 