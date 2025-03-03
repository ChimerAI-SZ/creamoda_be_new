from functools import lru_cache

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

class JobDefaults(BaseModel):
    coalesce: bool = True
    max_instances: int = 1
    misfire_grace_time: int = 60

class SchedulerSettings(BaseModel):
    jobstores: dict = {"default": "redis"}
    job_defaults: JobDefaults

class OSSSettings(BaseModel):
    access_key_id: str = ""
    access_key_secret: str = ""
    endpoint: str = ""
    bucket_name: str = ""
    url_prefix: str = ""  # OSS对象URL前缀
    upload_dir: str = "uploads/"  # 上传目录

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

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"mysql+pymysql://{self.database.user}:{self.database.password}@{self.database.host}:{self.database.port}/{self.database.name}"

@lru_cache()
def get_settings() -> Settings:
    with open("config.yaml", 'r') as f:
        config_dict = yaml.safe_load(f)
    return Settings(**config_dict)

settings = get_settings() 