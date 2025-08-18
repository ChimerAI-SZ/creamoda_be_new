from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import event
from sqlalchemy.engine import Engine
from ..config.log_config import logger

from ..config.config import settings

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI, 
    pool_pre_ping=True,
    pool_size=50,          # 进一步增加连接池大小到50
    max_overflow=100,      # 最大溢出连接数100  
    pool_timeout=120,      # 连接超时时间120秒
    pool_recycle=1800,     # 连接回收时间30分钟
    echo=False             # 关闭SQL日志以提高性能
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 事件监听器，记录SQL查询（生产环境建议关闭以提高性能）
# @event.listens_for(Engine, "before_cursor_execute")
# def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
#     logger.info(f"Executing SQL: {statement} | Parameters: {parameters}")

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 
