from src.config.config import settings

print(f"sqlacodegen_v2 mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME} --outfile app/models/models.py") 