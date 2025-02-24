from src.config.config import settings

print(f"sqlacodegen_v2 mysql+pymysql://{settings.database.user}:{settings.database.password}@{settings.database.host}:{settings.database.port}/{settings.database.name} --outfile src/models/models.py") 