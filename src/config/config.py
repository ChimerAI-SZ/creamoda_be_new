import os
from functools import lru_cache
from dotenv import load_dotenv

import yaml
from pydantic import BaseModel


class DatabaseSettings(BaseModel):
    host: str
    port: int
    user: str
    password: str
    name: str

class GoogleOAuth2Settings(BaseModel):
    client_id: str
    client_secret: str
    redirect_uri: str


class SecuritySettings(BaseModel):
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int


class APISettings(BaseModel):
    v1_str: str
    project_name: str

class RedisSettings(BaseModel):
    host: str
    port: int
    username: str = ""
    password: str = ""
    db: int = 0

class SMTPSettings(BaseModel):
    host: str
    port: int
    username: str
    password: str
    from_name: str
    use_tls: bool = True

class AlgorithmSettings(BaseModel):
    thenewblack_email: str
    thenewblack_password: str
    openrouter_api_key: str
    infiniai_api_key: str

class JobDefaults(BaseModel):
    coalesce: bool = True
    max_instances: int = 1
    misfire_grace_time: int = 60

class SchedulerSettings(BaseModel):
    enabled: bool = True
    jobstores: dict = {"default": "redis"}
    job_defaults: JobDefaults

class OSSSettings(BaseModel):
    access_key_id: str = ""
    access_key_secret: str = ""
    endpoint: str = ""
    bucket_name: str = ""
    url_prefix: str = ""  # OSS对象URL前缀
    upload_dir: str = "uploads/"  # 上传目录

class ImageGenerationSettings(BaseModel):
    text_to_image_count: int = 2
    copy_style_count: int = 2
    change_clothes_count: int = 2
    copy_fabric_count: int = 2
    virtual_try_on_count: int = 2
    sketch_to_design_count: int = 2
    estimated_time_seconds: int = 20

class Settings(BaseModel):
    api: APISettings
    google_oauth2: GoogleOAuth2Settings
    security: SecuritySettings
    database: DatabaseSettings
    redis: RedisSettings
    smtp: SMTPSettings
    algorithm: AlgorithmSettings
    scheduler: SchedulerSettings
    oss: OSSSettings = OSSSettings()
    image_generation: ImageGenerationSettings

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"mysql+pymysql://{self.database.user}:{self.database.password}@{self.database.host}:{self.database.port}/{self.database.name}"

@lru_cache()
def get_settings() -> Settings:
    """
    根据环境变量加载配置文件
    
    环境变量 APP_ENV 可以设置为:
    - prod: 加载生产环境配置 (config.prod.yaml)
    - 默认或其他值: 加载测试环境配置 (config.test.yaml)
    """
    # 加载 .env 文件中的变量
    load_dotenv()
    # 获取环境变量，默认为test环境
    env = os.getenv("APP_ENV", "test").lower()
    
    # 根据环境变量选择配置文件
    if env == "prod":
        config_file = "config.prod.yaml"
        print(f"Loading production configuration from {config_file}")
    else:
        config_file = "config.test.yaml"
        print(f"Loading test configuration from {config_file}")
    
    # 检查配置文件是否存在
    if not os.path.exists(config_file):
        raise FileNotFoundError("No configuration file found")
    
    # 加载配置文件
    try:
        with open(config_file, 'r') as f:
            config_dict = yaml.safe_load(f)
        return Settings(**config_dict)
    except Exception as e:
        print(f"Error loading configuration from {config_file}: {str(e)}")
        raise

settings = get_settings() 