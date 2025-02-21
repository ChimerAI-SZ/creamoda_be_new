import yaml
from functools import lru_cache
from typing import Optional
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

class Settings(BaseModel):
    api: APISettings
    google_oauth2: GoogleOAuth2Settings
    security: SecuritySettings
    database: DatabaseSettings

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"mysql+pymysql://{self.database.user}:{self.database.password}@{self.database.host}:{self.database.port}/{self.database.name}"

@lru_cache()
def get_settings() -> Settings:
    with open("config.yaml", 'r') as f:
        config_dict = yaml.safe_load(f)
    return Settings(**config_dict)

settings = get_settings() 