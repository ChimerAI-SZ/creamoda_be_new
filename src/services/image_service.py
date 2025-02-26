import uuid
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from ..models.models import GenImgRecord, GenImgResult  # 导入两个模型
from ..db.redis import redis_client
from ..db.session import SessionLocal
from ..config.log_config import logger
from ..config.config import settings
from ..alg.thenewblack import TheNewBlack  # 导入TheNewBlack服务

class ImageService:
    @staticmethod
    async def create_text_to_image_task(
        db: Session,
        uid: int,
        prompt: str,
        with_human_model: int,
        gender: int,
        age: int,
        country: str,
        model_size: int
    ) -> Dict[str, Any]:
        """创建文生图任务"""

        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=1,  # 1-文生图
            status=1,  # 1-待生成
            original_prompt=prompt,
            with_human_model=with_human_model,
            gender=gender,
            age=age,
            country=country,
            model_size=model_size,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 创建5个结果记录并存储它们的ID
            result_ids = []
            for i in range(1):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    result_pic="",
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动5个并行的图像生成任务，每个任务处理一个特定的结果ID
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_image_generation(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": 20  # 估计20秒完成
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create text-to-image task: {str(e)}")
            raise e
    
    @staticmethod
    async def call_generation_api(task: GenImgRecord, result: GenImgResult) -> str:
        """调用图像生成API"""
        try:
            # 初始化TheNewBlack服务
            thenewblack = TheNewBlack()
            
            # 调用create_clothing方法生成图片
            result_pic = await thenewblack.create_clothing(
                prompt=task.original_prompt,
                with_human_model=task.with_human_model,
                gender=task.gender,
                age=task.age,
                country=task.country,
                model_size=task.model_size,
                result_id=result.id
            )
            
            # 从结果中获取图片URL
            if not result_pic:
                raise Exception("Failed to generate image: invalid response")
                
            return result_pic
            
        except Exception as e:
            logger.error(f"Failed to call generation API: {str(e)}")
            raise e

    @staticmethod
    async def process_image_generation(result_id: int):
        """通过结果ID处理单个图像生成任务
        
        Args:
            result_id: GenImgResult的ID
        """
        db = SessionLocal()
        try:
            # 获取结果记录
            result = db.query(GenImgResult).filter(GenImgResult.id == result_id).first()
            
            if not result:
                logger.error(f"Result record {result_id} not found")
                return
            
            # 获取关联的任务记录
            task = db.query(GenImgRecord).filter(GenImgRecord.id == result.gen_id).first()
            
            if not task:
                logger.error(f"Task {result.gen_id} not found for result {result_id}")
                return
            
            # 更新任务状态为生成中(如果尚未更新)
            if task.status == 1:
                task.status = 2  # 生成中
                task.update_time = datetime.utcnow()
            
            # 更新结果状态为生成中
            result.status = 2  # 生成中
            result.update_time = datetime.utcnow()
            db.commit()
            
            try:
                # 调用生成API
                result_pic = await ImageService.call_generation_api(task, result)
                
                # 更新结果记录状态为成功
                result.status = 3  # 已生成
                result.result_pic = result_pic
                result.update_time = datetime.utcnow()
                # 重置失败次数
                result.fail_count = 0
                db.commit()
                
                # 检查该任务的所有结果记录是否都成功
                all_results = db.query(GenImgResult).filter(GenImgResult.gen_id == task.id).all()
                all_successful = all(r.status == 3 for r in all_results)
                
                # 只有当所有结果都成功时，才更新任务状态为成功
                if all_successful:
                    task.status = 3  # 已生成
                    task.update_time = datetime.utcnow()
                    logger.info(f"All results for task {task.id} are successful, task marked as complete")
                
                db.commit()
                
                logger.info(f"Image generation completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                logger.error(f"Failed to generate image for result {result_id}, task {task.id}: {str(e)}")
                
                # 更新结果记录为失败，并累加失败次数
                result.status = 4  # 生成失败
                result.update_time = datetime.utcnow()
                
                # 累加失败次数
                if result.fail_count is None:
                    result.fail_count = 1
                else:
                    result.fail_count += 1
                
                logger.info(f"Result {result_id} failure count increased to {result.fail_count}")
                
                db.commit()
        
        except Exception as e:
            logger.error(f"Error processing image generation for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    async def create_copy_style_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        fidelity: float,
        prompt: str
    ) -> Dict[str, Any]:
        """创建洗图任务 (图片风格转换)"""

        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=2,  # 2-图转图(洗图)
            variation_type = 1, # 1-洗图
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            original_prompt=prompt,
            fidelity=int(fidelity * 100),  # 将0-1的保真度转为0-100的整数存储
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)

            # 创建5个结果记录并存储它们的ID
            result_ids = []
            for i in range(1):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    result_pic="",
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()

            # 启动5个并行的图像生成任务，每个任务处理一个特定的结果ID
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_copy_style_generation(result_id)
                )
            
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": 20  # 估计20秒完成
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create copy style task: {str(e)}")
            raise e

    @staticmethod
    async def process_copy_style_generation(result_id: int):
        """处理洗图任务"""
        db = SessionLocal()
        try:
            # 获取结果记录
            result = db.query(GenImgResult).filter(GenImgResult.id == result_id).first()
            
            if not result:
                logger.error(f"Result record {result_id} not found")
                return
            
            # 获取关联的任务记录
            task = db.query(GenImgRecord).filter(GenImgRecord.id == result.gen_id).first()
            
            if not task:
                logger.error(f"Task {result.gen_id} not found for result {result_id}")
                return
            
            # 更新任务和结果状态为生成中
            if task.status == 1:
                task.status = 2  # 生成中
                task.update_time = datetime.utcnow()
            
            result.status = 2  # 生成中
            result.update_time = datetime.utcnow()
            db.commit()
            
            try:
                # 调用TheNewBlack API创建变体
                thenewblack = TheNewBlack()
                
                # 将保真度从数据库存储的整数(0-100)转回浮点数(0-1)
                fidelity = task.fidelity / 100.0
                
                # 确保保真度在有效范围内
                fidelity = min(max(fidelity, 0.0), 1.0)
                
                # 使用create_variation方法
                result_pic = await thenewblack.create_image_variation(
                    image_url=task.original_pic_url,
                    prompt=task.original_prompt,
                    fidelity=fidelity,
                    result_id=result.id
                )
                
                # 更新结果记录状态为成功
                result.status = 3  # 已生成
                result.result_pic = result_pic
                result.update_time = datetime.utcnow()
                result.fail_count = 0
                
                # 检查该任务的所有结果记录是否都成功
                all_results = db.query(GenImgResult).filter(GenImgResult.gen_id == task.id).all()
                all_successful = all(r.status == 3 for r in all_results)
                
                # 只有当所有结果都成功时，才更新任务状态为成功
                if all_successful:
                    task.status = 3  # 已生成
                    task.update_time = datetime.utcnow()
                    logger.info(f"All results for task {task.id} are successful, task marked as complete")
                
                db.commit()
                
                logger.info(f"Image copy style completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                logger.error(f"Failed to generate copy style image for result {result_id}, task {task.id}: {str(e)}")
                
                # 更新结果记录为失败，并累加失败次数
                result.status = 4  # 生成失败
                result.update_time = datetime.utcnow()
                
                # 累加失败次数
                if result.fail_count is None:
                    result.fail_count = 1
                else:
                    result.fail_count += 1
                
                logger.info(f"Result {result_id} failure count increased to {result.fail_count}")
                
                db.commit()
        
        except Exception as e:
            logger.error(f"Error processing copy style generation for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 

    @staticmethod
    async def create_change_clothes_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        remove: str = "None",
        replace: str = "None",
        negative: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建更换服装任务"""

        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=2,  # 2-图转图
            variation_type=2,  # 2-更换服装
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            original_prompt=replace,  # 使用replace作为prompt
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 创建结果记录
            result_ids = []
            for i in range(1):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    result_pic="",
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动并行的图像生成任务
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_change_clothes_generation(
                        result_id, 
                        remove=remove, 
                        replace=replace, 
                        negative=negative
                    )
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": 20  # 估计20秒完成
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create change clothes task: {str(e)}")
            raise e

    @staticmethod
    async def process_change_clothes_generation(
        result_id: int,
        remove: str = "None",
        replace: str = "None",
        negative: Optional[str] = None
    ):
        """处理更换服装任务"""
        db = SessionLocal()
        try:
            # 获取结果记录
            result = db.query(GenImgResult).filter(GenImgResult.id == result_id).first()
            
            if not result:
                logger.error(f"Result record {result_id} not found")
                return
            
            # 获取关联的任务记录
            task = db.query(GenImgRecord).filter(GenImgRecord.id == result.gen_id).first()
            
            if not task:
                logger.error(f"Task {result.gen_id} not found for result {result_id}")
                return
            
            # 更新任务和结果状态为生成中
            if task.status == 1:
                task.status = 2  # 生成中
                task.update_time = datetime.utcnow()
            
            result.status = 2  # 生成中
            result.update_time = datetime.utcnow()
            db.commit()
            
            try:
                # 调用TheNewBlack API更换服装
                thenewblack = TheNewBlack()
                
                # 调用change_clothes方法
                result_pic = await thenewblack.change_clothes(
                    image_url=task.original_pic_url,
                    remove=remove,
                    replace=replace,
                    negative=negative,
                    result_id=result.id
                )
                
                # 更新结果记录状态为成功
                result.status = 3  # 已生成
                result.result_pic = result_pic
                result.update_time = datetime.utcnow()
                result.fail_count = 0
                
                # 检查该任务的所有结果记录是否都成功
                all_results = db.query(GenImgResult).filter(GenImgResult.gen_id == task.id).all()
                all_successful = all(r.status == 3 for r in all_results)
                
                # 只有当所有结果都成功时，才更新任务状态为成功
                if all_successful:
                    task.status = 3  # 已生成
                    task.update_time = datetime.utcnow()
                    logger.info(f"All results for task {task.id} are successful, task marked as complete")
                
                db.commit()
                
                logger.info(f"Change clothes completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                logger.error(f"Failed to change clothes for result {result_id}, task {task.id}: {str(e)}")
                
                # 更新结果记录为失败，并累加失败次数
                result.status = 4  # 生成失败
                result.update_time = datetime.utcnow()
                
                # 累加失败次数
                if result.fail_count is None:
                    result.fail_count = 1
                else:
                    result.fail_count += 1
                
                logger.info(f"Result {result_id} failure count increased to {result.fail_count}")
                
                db.commit()
        
        except Exception as e:
            logger.error(f"Error processing change clothes for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 