from typing import List, Dict
from sqlalchemy.orm import Session
from ..models.models import Constant
from ..config.log_config import logger

class ConstantService:
    @staticmethod
    def get_enum_by_type(db: Session, enum_type: str) -> List[Dict]:
        """根据类型获取枚举值
        
        Args:
            db: 数据库会话
            enum_type: 枚举类型
            
        Returns:
            包含枚举项的列表
        """
        try:
            # 查询指定类型的所有枚举值，按排序字段升序排列
            constants = db.query(Constant).filter(
                Constant.type == enum_type
            ).order_by(
                Constant.id.asc()
            ).all()
            
            # 转换为字典列表
            result = []
            for item in constants:
                enum_item = {
                    "code": item.code,
                    "name": item.name
                }
                result.append(enum_item)
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to get enum values for type {enum_type}: {str(e)}")
            raise 