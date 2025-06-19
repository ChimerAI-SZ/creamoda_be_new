from datetime import datetime
from sqlalchemy.orm import Session

from src.models.models import CommunityImg, LikeImg
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.db.redis import redis_client
from src.config.log_config import logger
from src.models.models import LikeImg
from src.exceptions.base import CustomException


class LikeImgService:
    """图片点赞服务"""

    # Redis 缓存配置
    CACHE_PREFIX = "img_like_count"
    CACHE_EXPIRE = 3600  # 1小时过期
    
    @classmethod
    def _get_cache_key(cls, img_id: int) -> str:
        """获取缓存键"""
        return f"{cls.CACHE_PREFIX}:{img_id}"
    
    @classmethod
    async def get_like_count(cls, db: Session, img_id: int) -> int:
        """
        查询图片的点赞数量
        1. 先从 Redis 查询缓存
        2. 没有的话从数据库查询并缓存到 Redis
        """
        try:
            cache_key = cls._get_cache_key(img_id)
            
            # 1. 先从 Redis 查询缓存
            cached_count = redis_client.get(cache_key)
            if cached_count is not None:
                logger.debug(f"Cache hit for img {img_id}, count: {cached_count}")
                return int(cached_count)
            
            # 2. 从数据库查询
            like_count = db.query(func.count(LikeImg.id)).filter(
                LikeImg.gen_img_id == img_id
            ).scalar() or 0
            
            # 3. 缓存到 Redis
            redis_client.setex(cache_key, cls.CACHE_EXPIRE, like_count)
            
            return like_count
            
        except Exception as e:
            logger.error(f"Error getting like count for img {img_id}: {str(e)}")
            # 出错时从数据库查询
            return db.query(func.count(LikeImg.id)).filter(
                LikeImg.gen_img_id == img_id
            ).scalar() or 0
    
    @classmethod
    async def like_image(cls, db: Session, img_id: int, user_id: int):
        """
        点赞图片
        1. 查询是否有点赞记录
        2. 有的话直接返回
        3. 没有的话新增点赞记录，清空对应图片点赞统计缓存
        """
        try:
            # 1. 查询是否已经点赞
            existing_like = db.query(LikeImg).filter(
                LikeImg.gen_img_id == img_id,
                LikeImg.uid == user_id
            ).first()
            
            if existing_like:
                logger.info(f"User {user_id} already liked img {img_id}")
                return
            
            community_img = db.query(CommunityImg).filter(
                CommunityImg.gen_img_id == img_id
            ).first()

            if not community_img:
                raise CustomException(code=400, message=f"picture not found")
            
            # 2. 新增点赞记录
            new_like = LikeImg(
                gen_img_id=img_id,
                uid=user_id,
                create_time=datetime.now()
            )
            db.add(new_like)
            db.commit()
            db.refresh(new_like)
            
            # 3. 清空缓存
            cache_key = cls._get_cache_key(img_id)
            redis_client.delete(cache_key)
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error liking img {img_id} by user {user_id}: {str(e)}")
            raise CustomException(code=500, message=f"Failed to like image: {str(e)}")
    
    @classmethod
    async def unlike_image(cls, db: Session, img_id: int, user_id: int):
        """
        取消点赞图片
        1. 查询是否有点赞记录
        2. 没有的话直接返回
        3. 有的话删除点赞记录，清空对应图片点赞统计缓存
        """
        try:
            # 1. 查询点赞记录
            existing_like = db.query(LikeImg).filter(
                LikeImg.gen_img_id == img_id,
                LikeImg.uid == user_id
            ).first()
            
            if not existing_like:
                logger.info(f"User {user_id} has not liked img {img_id}")
                return
            
            # 2. 删除点赞记录
            db.delete(existing_like)
            db.commit()
            
            # 3. 清空缓存
            cache_key = cls._get_cache_key(img_id)
            redis_client.delete(cache_key)
        except Exception as e:
            db.rollback()
            logger.error(f"Error unliking img {img_id} by user {user_id}: {str(e)}")
            raise CustomException(code=500, message=f"Failed to unlike image: {str(e)}")
    
    @classmethod
    async def get_user_like_status(cls, db: Session, img_id: int, user_id: int) -> bool:
        """
        查询用户是否点赞了指定图片
        """
        try:
            like_record = db.query(LikeImg).filter(
                LikeImg.gen_img_id == img_id,
                LikeImg.uid == user_id
            ).first()
            
            return like_record is not None
            
        except Exception as e:
            logger.error(f"Error checking like status for img {img_id} by user {user_id}: {str(e)}")
            return False
    
    @classmethod
    async def clear_cache(cls, img_id: int) -> bool:
        """
        清空指定图片的点赞缓存
        """
        try:
            cache_key = cls._get_cache_key(img_id)
            result = redis_client.delete(cache_key)
            logger.debug(f"Cleared cache for img {img_id}")
            return bool(result)
        except Exception as e:
            logger.error(f"Error clearing cache for img {img_id}: {str(e)}")
            return False
    