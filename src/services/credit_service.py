

from datetime import datetime
from pymysql import OperationalError
from requests import Session

from src.constants.credit_point_value import PointValue
from src.constants.gen_img_type import GenImgType, GenImgTypeConstant
from src.constants.order_status import OrderStatus
from src.constants.order_type import OrderType
from src.exceptions.base import CustomException
from src.exceptions.pay import CreditError
from src.models.models import BillingHistory, Credit, CreditHistory
from src.services.order_service import OrderService
from src.config.log_config import logger
from src.config.config import settings
class CreditService:
    @staticmethod
    async def create_credit_order(db: Session, uid: int, amount: int):
        # 创建订单
        if amount == PointValue.POINT_40:
            order_type = OrderType.POINTS_40
        elif amount == PointValue.POINT_100:
            order_type = OrderType.POINTS_100
        elif amount == PointValue.POINT_200:
            order_type = OrderType.POINTS_200
        else:
            raise CustomException(code=400, message="Invalid amount")
        
        order_res = await OrderService.create_order(db, uid, order_type)
        
        return order_res
    
    @staticmethod
    async def launch_credit(db: Session, uid: int, orderId: str, amount: int):
        try:
            # 更新积分
            credit = db.query(Credit).filter(Credit.uid == uid).first()
            if credit:
                credit.credit += amount
                credit.update_time = datetime.now()
            else:
                credit = Credit(
                    uid=uid,
                    credit=amount,
                    lock_credit=0,
                    create_time=datetime.now(),
                    update_time = datetime.now()
                    )
                db.add(credit)

            # 新增积分记录
            credit_history = CreditHistory(
                uid=uid,
                credit_change=amount,
                source="purchase credit",
                create_time=datetime.now()
            )
            db.add(credit_history)

            # 更新订单状态
            billing_history = db.query(BillingHistory).filter(BillingHistory.uid == uid, BillingHistory.order_id == orderId).first()
            if not billing_history:
                raise CustomException(code=400, message="Billing history not found")
            billing_history.status = OrderStatus.PAYMENT_SUCCESS
            billing_history.update_time = datetime.now()
            db.commit()
        except Exception as e:
            logger.error(f"Launch credit failed: {e}")
            db.rollback()
            raise CustomException(code=400, message="Launch credit failed")

    @staticmethod
    async def lock_credit(db: Session, uid: int, amount: int):
        """锁定积分"""
        try:
            credit = db.query(Credit).filter(Credit.uid == uid).with_for_update(nowait=True).first()
            if not credit or credit.credit < amount:
                raise CustomException(code=400, message="Insufficient credit")
            
            credit.credit -= amount
            credit.lock_credit += amount
            credit.update_time = datetime.now()

            credit_history = CreditHistory(
                uid=uid,
                credit_change=-amount,
                source="lock credit",
                create_time=datetime.now()
            )
            db.add(credit_history)
            db.commit()
        except OperationalError as e:
            logger.warning(f"Failed to acquire lock for user {uid}: {str(e)}")
            raise CustomException(code=409, message="Resource is locked, please try again later")
        except Exception as e:
            logger.error(f"Lock credit failed: {e}")
            db.rollback()
            raise CustomException(code=400, message="credit not enough")
        
    @staticmethod
    async def unlock_credit(db: Session, uid: int, amount: int):
        """解锁积分"""
        try:
            credit = db.query(Credit).filter(Credit.uid == uid).with_for_update(nowait=True).first()
            if not credit or credit.lock_credit < amount:
                raise CustomException(code=400, message="Insufficient lock credit")
            
            credit.credit += amount
            credit.lock_credit -= amount
            credit.update_time = datetime.now()

            credit_history = CreditHistory(
                uid=uid,
                credit_change=amount,
                source="unlock credit",
                create_time=datetime.now()
            )
            db.add(credit_history)
            db.commit()
        except OperationalError as e:
            logger.warning(f"Failed to acquire lock for user {uid}: {str(e)}")
            raise CustomException(code=409, message="Resource is locked, please try again later")
        except Exception as e:
            logger.error(f"Unlock credit failed: {e}")
            db.rollback()
            raise CustomException(code=400, message="Unlock credit failed")

    @staticmethod
    async def real_spend_credit(db: Session, uid: int, amount: int):
        """实际消费积分"""
        try:
            with db.begin_nested():
                credit = db.query(Credit).filter(Credit.uid == uid).with_for_update(nowait=True).first()
                if not credit or credit.lock_credit < amount:
                    raise CustomException(code=400, message="Insufficient lock credit")

                credit.lock_credit -= amount
                credit.update_time = datetime.now()

                credit_history = CreditHistory(
                    uid=uid,
                    credit_change=-amount,
                    source="real spend credit",
                    create_time=datetime.now()
                )
                db.add(credit_history)
        except OperationalError as e:
            logger.warning(f"Failed to acquire lock for user {uid}: {str(e)}")
            raise CustomException(code=409, message="Resource is locked, please try again later")
        except Exception as e:
            logger.error(f"Real spend credit failed: {e}")
            raise CreditError(message="Real spend credit failed")
        
    @staticmethod
    def get_credit_value_by_type(type: GenImgTypeConstant):
        if type == GenImgType.TEXT_TO_IMAGE.value:
            return settings.image_generation.text_to_image.use_credit
        elif type == GenImgType.COPY_STYLE.value:
            return settings.image_generation.copy_style.use_credit
        elif type == GenImgType.CHANGE_CLOTHES.value:
            return settings.image_generation.change_clothes.use_credit
        elif type == GenImgType.FABRIC_TO_DESIGN.value:
            return settings.image_generation.fabric_to_design.use_credit
        elif type == GenImgType.SKETCH_TO_DESIGN.value:
            return settings.image_generation.sketch_to_design.use_credit
        elif type == GenImgType.MIX_IMAGE.value:
            return settings.image_generation.mix_image.use_credit
        elif type == GenImgType.STYLE_TRANSFER.value:
            return settings.image_generation.style_transfer.use_credit
        elif type == GenImgType.VIRTUAL_TRY_ON.value:
            return settings.image_generation.virtual_try_on.use_credit
        elif type == GenImgType.CHANGE_COLOR.value:
            return settings.image_generation.change_color.use_credit
        elif type == GenImgType.CHANGE_BACKGROUND.value:
            return settings.image_generation.change_background.use_credit
        elif type == GenImgType.REMOVE_BACKGROUND.value:
            return settings.image_generation.remove_background.use_credit
        elif type == GenImgType.PARTICIAL_MODIFICATION.value:
            return settings.image_generation.particial_modification.use_credit
        elif type == GenImgType.UPSCALE.value:
            return settings.image_generation.upscale.use_credit
        elif type == GenImgType.FABRIC_TRANSFER.value:
            return settings.image_generation.fabric_transfer.use_credit
        else:
            raise CustomException(code=400, message="Invalid type")