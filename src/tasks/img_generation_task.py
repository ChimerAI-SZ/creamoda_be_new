import json
import asyncio

from src.constants.gen_img_type import GenImgType
from src.services.credit_service import CreditService
from ..db.redis import redis_client
from ..db.session import SessionLocal, get_async_db, get_db
from ..services.image_service import ImageService
from ..config.log_config import logger
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models.models import GenImgRecord, GenImgResult
from sqlalchemy import or_
from src.db.redis import redis_client
from redis.lock import Lock

async def process_image_generation_compensate():
    """补偿处理未完成的图像生成任务"""
    with get_db() as db:
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
                    # 条件1：状态为待生成(1)，更新时间超过10秒，且失败次数小于3次
                    (GenImgResult.status == 1) &
                    (GenImgResult.update_time < short_timeout_threshold) &
                    ((GenImgResult.fail_count == None) | (GenImgResult.fail_count <= 3)),
                    
                    # 条件2：状态为生成中(2)，更新时间超过600秒，且失败次数小于3次
                    (GenImgResult.status == 2) &
                    (GenImgResult.update_time < long_timeout_threshold) &
                    ((GenImgResult.fail_count == None) | (GenImgResult.fail_count <= 3)),

                    # 条件3：状态为生成失败(4)，更新时间超过10秒，且失败次数小于3次
                    (GenImgResult.status == 4) &
                    (GenImgResult.update_time < short_timeout_threshold) &
                    ((GenImgResult.fail_count == None) | (GenImgResult.fail_count < 3))
                )
            ).all()
            
            if not timeout_results:
                logger.info("No pending or failed image generation tasks to compensate.")
                return
                
            logger.info(f"Found {len(timeout_results)} pending or failed image generation tasks to compensate.")
            
            # 逐个处理任务，复用 process_image_generation 方法
            for result in timeout_results:
                try:
                    logger.info(f"Scheduling compensation for result ID {result.id} (fail count: {result.fail_count})...")
                    # 直接调用 ImageService.process_image_generation 方法处理此结果记录

                    # 获取关联的任务记录
                    task = db.query(GenImgRecord).filter(GenImgRecord.id == result.gen_id).first()
                    
                    if not task:
                        logger.error(f"Task {result.gen_id} not found for result {result.id}")
                        continue

                    # 如果失败次数大于等于3，更新状态为4
                    if result.fail_count >= 3:
                        result.status = 4
                        db.commit()
                        db.refresh(result)
                        continue

                    tasks = []
                    if task.type == GenImgType.TEXT_TO_IMAGE.value.type:
                        tasks.append(asyncio.create_task(ImageService.process_text_to_image_generation(result.id)))
                    elif task.type == GenImgType.COPY_STYLE.value.type and task.variation_type == GenImgType.COPY_STYLE.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_copy_style_generation(result.id)))
                    elif task.type == GenImgType.CHANGE_CLOTHES.value.type and task.variation_type == GenImgType.CHANGE_CLOTHES.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_change_clothes_generation(result.id, replace=task.original_prompt, negative=None)))
                    elif task.type == GenImgType.FABRIC_TO_DESIGN.value.type and task.variation_type == GenImgType.FABRIC_TO_DESIGN.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_fabric_to_design_generation(result.id)))
                    elif task.type == GenImgType.VIRTUAL_TRY_ON.value.type:
                        tasks.append(asyncio.create_task(ImageService.process_virtual_try_on_generation(result.id)))
                    elif task.type == GenImgType.CHANGE_COLOR.value.type and task.variation_type == GenImgType.CHANGE_COLOR.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_change_color(result.id)))
                    elif task.type == GenImgType.CHANGE_BACKGROUND.value.type and task.variation_type == GenImgType.CHANGE_BACKGROUND.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_change_background(result.id)))
                    elif task.type == GenImgType.REMOVE_BACKGROUND.value.type and task.variation_type == GenImgType.REMOVE_BACKGROUND.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_remove_background(result.id)))
                    elif task.type == GenImgType.PARTICIAL_MODIFICATION.value.type and task.variation_type == GenImgType.PARTICIAL_MODIFICATION.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_particial_modification(result.id)))
                    elif task.type == GenImgType.UPSCALE.value.type and task.variation_type == GenImgType.UPSCALE.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_upscale(result.id)))
                    elif task.type == GenImgType.CHANGE_PATTERN.value.type and task.variation_type == GenImgType.CHANGE_PATTERN.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_change_pattern(result.id)))
                    elif task.type == GenImgType.CHANGE_FABRIC.value.type and task.variation_type == GenImgType.CHANGE_FABRIC.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_change_fabric(result.id)))
                    elif task.type == GenImgType.CHANGE_PRINTING.value.type and task.variation_type == GenImgType.CHANGE_PRINTING.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_change_printing(result.id)))
                    elif task.type == GenImgType.CHANGE_POSE.value.type and task.variation_type == GenImgType.CHANGE_POSE.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_change_pose(result.id)))
                    elif task.type == GenImgType.STYLE_FUSION.value.type and task.variation_type == GenImgType.STYLE_FUSION.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_style_fusion(result.id)))
                    elif task.type == GenImgType.EXTRACT_PATTERN.value.type and task.variation_type == GenImgType.EXTRACT_PATTERN.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_extract_pattern(result.id)))
                    elif task.type == GenImgType.DRESS_PRINTING_TRYON.value.type and task.variation_type == GenImgType.DRESS_PRINTING_TRYON.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_dress_printing_tryon(result.id)))
                    elif task.type == GenImgType.PRINTING_REPLACEMENT.value.type and task.variation_type == GenImgType.PRINTING_REPLACEMENT.value.variationType:
                        tasks.append(asyncio.create_task(ImageService.process_printing_replacement(result.id)))
                    else:
                        logger.error(f"Unsupported task type: {task.type}, task variation_type: {task.variation_type} for result {result.id}")
                        continue

                    # 等待所有任务完成
                    if tasks:
                        logger.info(f"等待 {len(tasks)} 个子任务完成...")
                        try:
                            await asyncio.gather(*tasks, return_exceptions=True)
                            logger.info(f"所有子任务已完成")
                        except Exception as e:
                            logger.error(f"等待子任务时发生错误: {str(e)}")
                            
                except Exception as e:
                    logger.error(f"Error during compensation processing: {str(e)}")
        except Exception as e:
            logger.error(f"Error during compensation processing: {str(e)}")
            db.rollback()
        finally:
            db.close()

def img_generation_compensate_task():
    """图像生成补偿任务入口"""
    lock = Lock(redis_client, "img_generation_compensate_task_lock", timeout=300)
    
    if not lock.acquire(blocking=False):
        logger.info("Previous task is still running, skipping this execution")
        return
    
    try:
        # 检查是否已有事件循环在运行
        try:
            loop = asyncio.get_running_loop()
            # 如果有事件循环在运行，使用 create_task
            asyncio.create_task(process_image_generation_compensate())
        except RuntimeError:
            # 如果没有事件循环在运行，创建新的
            asyncio.run(process_image_generation_compensate())
    except Exception as e:
        logger.error(f"Error in process_subscprocess_image_generation_compensateribe_status_refresh: {str(e)}")
    finally:
        lock.release()