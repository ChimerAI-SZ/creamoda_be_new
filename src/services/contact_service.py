from datetime import datetime
from sqlalchemy.orm import Session
from ..models.models import ContactRecord, GenImgResult
from ..config.log_config import logger
from typing import Optional

class ContactService:
    @staticmethod
    def create_contact_record(
        db: Session,
        uid: int,
        contactEmail: str,
        source: str,
        genImgId: int,
    ) -> bool:
        """创建联系商务记录
        
        Args:
            db: 数据库会话
            uid: 用户ID
            contactEmail: 联系邮箱
            source: 来源场景
            genImgId: 生成图片id
            
        Returns:
            是否成功创建记录
        """

        if genImgId:
            gen_img_result = db.query(GenImgResult).filter(GenImgResult.id == genImgId).first()
            if not gen_img_result:
                logger.error(f"Gen img result not found: {genImgId}")

        try:
            # 创建记录
            now = datetime.utcnow()
            contact_record = ContactRecord(
                gen_id=gen_img_result.gen_id if gen_img_result else None,
                img_id=gen_img_result.id if gen_img_result else genImgId,
                contactEmail=contactEmail,
                uid=uid,
                source=source,
                create_time=now
            )
            
            # 保存到数据库
            db.add(contact_record)
            db.commit()
            
            logger.info(f"Contact business record created: user ID {uid}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create contact record: {str(e)}")
            return False 