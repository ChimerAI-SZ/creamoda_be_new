import json
import asyncio
from ..db.redis import redis_client
from ..db.session import SessionLocal
from ..services.image_service import ImageService
from ..config.log_config import logger
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models.models import GenImgRecord, GenImgResult
from sqlalchemy import or_

async def process_image_generation_compensate():
    """补偿处理未完成的图像生成任务"""
    db = SessionLocal()
    try:
        # 获取当前时间
        now = datetime.utcnow()
        
        # 查询所有满足条件的记录：
        # 1.status为1或4，更新时间超过10秒且失败次数小于3次的结果记录 
        # 2.status为2，更新时间超过600秒的记录且失败次数小于3次的结果记录
        short_timeout_threshold = now - timedelta(seconds=10)
        long_timeout_threshold = now - timedelta(seconds=600)
        
        timeout_results = db.query(GenImgResult).filter(
            or_(
                # 条件1：状态为待生成(1)或生成失败(4)，更新时间超过10秒，且失败次数小于3次
                ((GenImgResult.status == 1) | (GenImgResult.status == 4)) &
                (GenImgResult.update_time < short_timeout_threshold) &
                ((GenImgResult.fail_count == None) | (GenImgResult.fail_count < 3)),
                
                # 条件2：状态为生成中(2)，更新时间超过600秒，且失败次数小于3次
                (GenImgResult.status == 2) &
                (GenImgResult.update_time < long_timeout_threshold) &
                ((GenImgResult.fail_count == None) | (GenImgResult.fail_count < 3))
            )
        ).all()
        
        if not timeout_results:
            logger.info("No pending or failed image generation tasks to compensate.")
            return
            
        logger.info(f"Found {len(timeout_results)} pending or failed image generation tasks to compensate.")
        
        # 逐个处理任务，复用 process_image_generation 方法
        for result in timeout_results:
            logger.info(f"Scheduling compensation for result ID {result.id} (fail count: {result.fail_count})...")
            # 直接调用 ImageService.process_image_generation 方法处理此结果记录

            # 获取关联的任务记录
            task = db.query(GenImgRecord).filter(GenImgRecord.id == result.gen_id).first()
            
            if not task:
                logger.error(f"Task {result.gen_id} not found for result {result.id}")
                continue

            # 如果失败次数大于3，更新状态为4
            if result.fail_count > 3:
                result.status = 4
                db.commit()
                db.refresh(result)
                continue

            if task.type == 1:
                await ImageService.process_image_generation(result.id)
            elif task.type == 2 and task.variation_type == 1:
                await ImageService.process_copy_style_generation(result.id)
            elif task.type == 2 and task.variation_type == 2:
                await ImageService.process_change_clothes_generation(
                    result.id,
                    replace=task.original_prompt,   # 使用原始提示词作为替换内容
                    negative=None                   # 没有负面提示词
                )
            elif task.type == 2 and task.variation_type == 3:
                await ImageService.process_copy_fabric_generation(result.id)
            elif task.type == 3:
                await ImageService.process_virtual_try_on_generation(result.id)
            elif task.type == 4 and task.variation_type == 1:
                await ImageService.process_change_color(result.id)
            elif task.type == 4 and task.variation_type == 2:
                await ImageService.process_change_background(result.id)
            elif task.type == 4 and task.variation_type == 3:
                await ImageService.process_remove_background(result.id)
            elif task.type == 4 and task.variation_type == 4:
                await ImageService.process_particial_modification(result.id)
            elif task.type == 4 and task.variation_type == 4:
                await ImageService.process_upscale(result.id)
            else:

                logger.error(f"Unsupported task type: {task.type}, task variation_type: {task.variation_type} for result {result.id}")
                continue

    except Exception as e:
        logger.error(f"Error during compensation processing: {str(e)}")
        db.rollback()
    finally:
        db.close()

def img_generation_compensate_task():
    """图像生成补偿任务入口"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(process_image_generation_compensate()) 