from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import event
from sqlalchemy.engine import Engine
from ..config.log_config import logger

from ..config.config import settings

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async_engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI_ASYNC,
    pool_size=20,
    max_overflow=30,
    pool_timeout=60,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=True
)

async_session = sessionmaker(
    async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# 事件监听器，记录SQL查询
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    logger.info(f"Executing SQL: {statement} | Parameters: {parameters}")

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 

async def get_async_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()