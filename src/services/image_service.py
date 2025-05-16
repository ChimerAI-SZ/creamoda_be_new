from concurrent.futures import ThreadPoolExecutor
import uuid
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from src.alg.ideogram_adapter import IdeogramAdapter
from src.alg.replicate_adapter import ReplicateAdapter

from ..models.models import GenImgRecord, GenImgResult  # 导入两个模型
from ..db.redis import redis_client
from ..db.session import SessionLocal
from ..config.log_config import logger
from ..config.config import settings
from ..alg.thenewblack import TheNewBlack  # 导入TheNewBlack服务
from ..utils.style_prompts import get_random_style_prompt
from ..alg.intention_detector import IntentionDetector
from ..alg.infiniai_adapter import InfiniAIAdapter
from ..alg.thenewblack import Gender

class ImageService:
    @staticmethod
    async def create_text_to_image_task(
        db: Session,
        uid: int,
        prompt: str,
        width: int,
        height: int,
        with_human_model: int,
        gender: int,
        age: int,
        country: str,
        model_size: int,
        format: str
    ) -> Dict[str, Any]:
        """创建文生图任务"""

        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=1,  # 1-文生图
            format=format,
            width=width,
            height=height,
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
            
            # 从配置中获取要创建的结果记录数量
            image_count = settings.image_generation.text_to_image_count
            
            # 获取所有可用风格，确保不重复
            used_styles = set()
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                # 选择一个未使用的风格
                style_name, style_prompt = ImageService._get_unique_style(used_styles)
                used_styles.add(style_name)

                # 合并原始提示词和风格提示词
                enhanced_prompt = f"{task.original_prompt}{style_prompt}"
                logger.info(f"Enhanced prompt with style '{style_name}': {enhanced_prompt}")
                
                # 创建结果记录，包含风格信息
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    style=style_name,  # 保存风格名称
                    prompt=enhanced_prompt,
                    result_pic="",
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动并行的图像生成任务，每个任务处理一个特定的结果ID
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_image_generation(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create text-to-image task: {str(e)}")
            raise e
    
    @staticmethod
    async def create_fabric_to_design_task(
        db: Session,
        uid: int,
        fabric_pic_url: str,
        prompt: str
    ) -> Dict[str, Any]:
        """创建面料转设计任务"""

        # 调用ai获取模特信息
        intention_detector = IntentionDetector()
        intention_result = intention_detector.copy_fabric(fabric_pic_url, prompt)
        gender_enum = intention_result['gender']
        gender = 2
        if gender_enum.value == Gender.MAN.value:
            gender = 1
        clothing_prompt = intention_result['clothing_prompt']
        country = intention_result['country']
        age = intention_result['age']

        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=2,  # 2-图生图
            variation_type=3, # 2-Fabric to Design
            status=1,  # 1-待生成
            original_pic_url=fabric_pic_url,
            original_prompt=prompt,
            gender=gender,
            age=age,
            country=country,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量
            image_count = settings.image_generation.fabric_to_design_count
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                
                # 创建结果记录，包含风格信息
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    prompt=clothing_prompt,
                    result_pic="",
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动并行的图像生成任务，每个任务处理一个特定的结果ID
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_fabric_to_design_generation(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create copy fabric task: {str(e)}")
            raise e

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
            
            # 从配置中获取要创建的结果记录数量
            image_count = settings.image_generation.copy_style_count
            
            # 获取所有可用风格，确保不重复
            used_styles = set()
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                # 选择一个未使用的风格
                style_name, style_prompt = ImageService._get_unique_style(used_styles)
                used_styles.add(style_name)

                # 合并原始提示词和风格提示词
                enhanced_prompt = f"{task.original_prompt}{style_prompt}"
                logger.info(f"Enhanced prompt with style '{style_name}': {enhanced_prompt}")
                
                # 创建结果记录，包含风格信息
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    style=style_name,  # 保存风格名称
                    prompt=enhanced_prompt,
                    result_pic="",
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()

            # 启动并行的图像生成任务，每个任务处理一个特定的结果ID
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_copy_style_generation(result_id)
                )
            
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create copy style task: {str(e)}")
            raise e


    @staticmethod
    async def create_sketch_to_design_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        prompt: str
    ) -> Dict[str, Any]:
        """创建草图转设计任务"""

        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=2,  # 2-图生图
            variation_type=4, # Sketch to Design
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            original_prompt=prompt,
            create_time=now,
            update_time=now
        )

        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量
            image_count = settings.image_generation.sketch_to_design_count
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                
                # 创建结果记录，包含风格信息
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
            
            # 启动并行的图像生成任务，每个任务处理一个特定的结果ID
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_sketch_to_design_generation(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create sketch to design task: {str(e)}")
            raise e

    @staticmethod
    async def create_mix_image_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        refer_pic_url: str,
        prompt: str,
        fidelity: float
    ) -> Dict[str, Any]:
        """创建草图转设计任务"""

        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=2,  # 2-图生图
            variation_type=5, # 5-混合图片
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            original_prompt=prompt,
            refer_pic_url=refer_pic_url,
            fidelity=fidelity,
            create_time=now,
            update_time=now
        )

        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量
            image_count = settings.image_generation.mix_image_count
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                
                # 创建结果记录，包含风格信息
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
            
            # 启动并行的图像生成任务，每个任务处理一个特定的结果ID
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_mix_image_generation(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create mix image task: {str(e)}")
            raise e


    @staticmethod
    async def create_virtual_try_on_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        clothing_photo: str,
        cloth_type: str,
    ) -> Dict[str, Any]:
        """创建虚拟试穿任务"""

        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=3,  # 3-虚拟试穿
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            clothing_photo=clothing_photo,
            cloth_type=cloth_type,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量
            image_count = settings.image_generation.virtual_try_on_count
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                
                # 创建结果记录，包含风格信息
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
            
            # 启动并行的图像生成任务，每个任务处理一个特定的结果ID
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_virtual_try_on_generation(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create virtual try on task: {str(e)}")
            raise e

    @staticmethod
    def _get_unique_style(used_styles: set) -> tuple:
        """获取一个未使用的风格
        
        Args:
            used_styles: 已使用的风格名称集合
            
        Returns:
            tuple: (风格名称, 风格提示词)
        """
        from ..utils.style_prompts import STYLE_PROMPTS
        
        # 如果所有风格都已使用，则重新开始
        if len(used_styles) >= len(STYLE_PROMPTS):
            return get_random_style_prompt()
        
        # 尝试获取未使用的风格
        for _ in range(20):  # 最多尝试20次
            style_name, style_prompt = get_random_style_prompt()
            if style_name not in used_styles:
                return style_name, style_prompt
        
        # 如果无法找到未使用的风格，返回随机风格
        return get_random_style_prompt()
    
    @staticmethod
    async def call_generation_api(task: GenImgRecord, result: GenImgResult, enhanced_prompt: str) -> str:
        """调用图像生成API"""
        try:
            # 初始化TheNewBlack服务
            thenewblack = TheNewBlack()
            
            # 调用create_clothing方法生成图片
            result_pic = await thenewblack.create_clothing(
                prompt=enhanced_prompt,
                with_human_model=task.with_human_model,
                gender=task.gender,
                age=task.age,
                country=task.country,
                model_size=task.model_size,
                width=task.width,
                height=task.height,
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
                result_pic = await ImageService.call_generation_api(task, result, result.prompt)
                
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
    async def process_fabric_to_design_generation(result_id: int):
        """处理面料转设计任务"""
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
                
                # 使用create_variation方法
                result_pic = await thenewblack.create_clothing_with_fabric(
                    fabric_image_url=task.original_pic_url,
                    prompt=result.prompt,
                    gender=task.gender,
                    country=task.country,
                    age=task.age,
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
                
                logger.info(f"Image fabric to design completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                logger.error(f"Failed to generate fabric to design image for result {result_id}, task {task.id}: {str(e)}")
                
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
            logger.error(f"Error processing fabric to design generation for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    async def process_virtual_try_on_generation(result_id: int):
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
                
                # 使用create_variation方法
                result_pic = await thenewblack.create_virtual_try_on(
                    model_image_url=task.original_pic_url,
                    clothing_image_url=task.clothing_photo,
                    clothing_type=task.cloth_type,
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
            logger.error(f"Error processing copy fabric generation for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()
    
    @staticmethod
    async def process_sketch_to_design_generation(result_id: int):
        """处理草图转设计任务"""
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

                # 使用create_variation方法
                result_pic = await thenewblack.create_sketch_to_design(
                    original_pic_url=task.original_pic_url,
                    prompt=task.original_prompt,
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
                
                logger.info(f"Image sketch to design completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                logger.error(f"Failed to generate sketch to design image for result {result_id}, task {task.id}: {str(e)}")
                
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
            logger.error(f"Error processing sketch to design generation for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    async def process_mix_image_generation(result_id: int):
        """处理混合图片任务"""
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
                # 将保真度从数据库存储的整数(0-100)转回浮点数(0-1)
                fidelity = task.fidelity / 100.0
                
                # 确保保真度在有效范围内
                fidelity = min(max(fidelity, 0.0), 1.0)

                # 创建线程池执行器
                result_pic = await InfiniAIAdapter.get_adapter().transfer_style(
                    image_a_url=task.original_pic_url, 
                    image_b_url=task.refer_pic_url, 
                    prompt=task.original_prompt, 
                    strength=fidelity
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
                
                logger.info(f"Image mix image completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                logger.error(f"Failed to generate mix image for result {result_id}, task {task.id}: {str(e)}")
                
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
            logger.error(f"Error processing mix image generation for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    def _get_style_by_name(style_name: str) -> tuple:
        """根据风格名称获取风格提示词
        
        Args:
            style_name: 风格名称
            
        Returns:
            tuple: (风格名称, 风格提示词)
        """
        from ..utils.style_prompts import STYLE_PROMPTS
        
        # 查找匹配的风格
        for name, prompt in STYLE_PROMPTS:
            if name == style_name:
                return name, prompt
        
        # 如果找不到，返回默认风格
        return STYLE_PROMPTS[0]


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
                    prompt=result.prompt,
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
            
            # 从配置中获取要创建的结果记录数量
            image_count = settings.image_generation.change_clothes_count
            
            # 获取所有可用风格，确保不重复
            used_styles = set()

            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                # 选择一个未使用的风格
                style_name, style_prompt = ImageService._get_unique_style(used_styles)
                used_styles.add(style_name)

                # 合并原始提示词和风格提示词
                enhanced_prompt = f"{task.original_prompt}{style_prompt}"
                logger.info(f"Enhanced prompt with style '{style_name}': {enhanced_prompt}")
                

                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    style=style_name,  # 保存风格名称
                    prompt=enhanced_prompt,
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
                "estimatedTime": settings.image_generation.estimated_time_seconds
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
                    replace=result.prompt,
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

    @staticmethod
    def get_image_history(
        db: Session,
        uid: int,
        page: int = 1,
        page_size: int = 10,
        record_type: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取用户图片生成历史记录
        
        Args:
            db: 数据库会话
            uid: 用户ID
            page_num: 页码，从1开始
            page_size: 每页记录数
            record_type: 记录类型筛选，可选 1-文生图 2-图生图
            
        Returns:
            包含分页数据的字典
        """
        # 构建JOIN查询，把GenImgResult和GenImgRecord关联起来
        query = db.query(
            GenImgResult,
            GenImgRecord
        ).join(
            GenImgRecord,
            GenImgResult.gen_id == GenImgRecord.id
        ).filter(
            GenImgResult.uid == uid
        )
        
        # 如果指定了type，则添加type筛选条件
        if record_type is not None and record_type != 0:
            query = query.filter(GenImgRecord.type == record_type)
        
        # 计算总记录数
        total_count = query.count()
        
        # 分页并按创建时间倒序排序
        paginated_results = query.order_by(GenImgResult.id.desc())\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
        
        # 构建结果列表
        result_list = []
        for result, record in paginated_results:
            # 格式化时间为字符串
            create_time = result.create_time.strftime("%Y-%m-%d %H:%M:%S") if result.create_time else ""
            
            # 构建单条记录
            history_item = {
                "genImgId": result.id,  # GenImgResult的ID
                "genId": result.gen_id,  # 对应的GenImgRecord的ID
                "type": record.type,     # 生成类型
                "variationType": record.variation_type,  # 变化类型
                "status": result.status,  # 状态
                "resultPic": result.result_pic,  # 生成结果图片URL
                "createTime": create_time  # 创建时间
            }
            
            result_list.append(history_item)
        
        # 返回分页结果
        return {
            "total": total_count,
            "list": result_list
        } 

    @staticmethod
    def get_image_detail(
        db: Session,
        uid: int,
        gen_img_id: int
    ) -> Dict[str, Any]:
        """获取图片生成详情
        
        Args:
            db: 数据库会话
            uid: 用户ID
            gen_img_id: 图片ID(GenImgResult表的ID)
            
        Returns:
            包含图片详情的字典
        """
        # 查询结果记录
        result = db.query(GenImgResult).filter(
            GenImgResult.id == gen_img_id,
            GenImgResult.uid == uid
        ).first()
        
        if not result:
            raise ValueError(f"Image with ID {gen_img_id} not found or not owned by user")
        
        # 查询关联的任务记录
        record = db.query(GenImgRecord).filter(
            GenImgRecord.id == result.gen_id
        ).first()
        
        if not record:
            raise ValueError(f"Task record with ID {result.gen_id} not found")
        
        # 格式化时间为字符串
        create_time = result.create_time.strftime("%Y-%m-%d %H:%M:%S") if result.create_time else ""
        
        # 如果是洗图类型，将保真度从整数(0-100)转回浮点数(0-1)
        fidelity = None
        if record.type == 2 and record.variation_type == 1 and record.fidelity is not None:
            fidelity = record.fidelity / 100.0
        
        # 构建详情信息
        detail = {
            "genImgId": result.id,
            "genId": result.gen_id,
            "type": record.type,
            "variationType": record.variation_type,
            "originalPrompt": record.original_prompt,
            "originalPicUrl": record.original_pic_url,
            "resultPic": result.result_pic,
            "status": result.status,
            "createTime": create_time,
            "withHumanModel": record.with_human_model,
            "gender": record.gender,
            "age": record.age,
            "country": record.country,
            "modelSize": record.model_size,
            "fidelity": fidelity
        }
        
        return detail 

    @staticmethod
    def refresh_image_status(
        db: Session,
        uid: int,
        gen_img_id_list: List[int]
    ) -> List[Dict[str, Any]]:
        """批量获取图片状态信息
        
        Args:
            db: 数据库会话
            uid: 用户ID
            gen_img_id_list: 图片ID列表(GenImgResult表的ID列表)
            
        Returns:
            包含图片状态信息的列表
        """
        # 如果列表为空，直接返回空列表
        if not gen_img_id_list:
            return []
        
        # 构建JOIN查询，把GenImgResult和GenImgRecord关联起来
        query = db.query(
            GenImgResult,
            GenImgRecord
        ).join(
            GenImgRecord,
            GenImgResult.gen_id == GenImgRecord.id
        ).filter(
            GenImgResult.uid == uid,
            GenImgResult.id.in_(gen_img_id_list)  # 使用IN查询指定的图片ID列表
        )
        
        # 执行查询
        results = query.all()
        
        # 构建结果列表
        result_list = []
        for result, record in results:
            # 格式化时间为字符串
            create_time = result.create_time.strftime("%Y-%m-%d %H:%M:%S") if result.create_time else ""
            
            # 构建单条记录
            status_item = {
                "genImgId": result.id,           # GenImgResult的ID
                "genId": result.gen_id,          # 对应的GenImgRecord的ID
                "type": record.type,             # 生成类型
                "variationType": record.variation_type,  # 变化类型
                "resultPic": result.result_pic,  # 生成结果图片URL
                "status": result.status,         # 状态
                "createTime": create_time        # 创建时间
            }
            
            result_list.append(status_item)
        
        return result_list 

    @staticmethod
    async def create_style_transfer_task(
        db: Session,
        uid: int,
        image_a_url: str,
        image_b_url: str,
        strength: float = 0.5
    ) -> Dict[str, Any]:
        """创建风格转换任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            image_a_url: 内容图片URL
            image_b_url: 风格图片URL
            strength: 风格应用强度，0-1之间
            
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=2,  # 2-图生图
            variation_type=6,  # 5-风格转换
            status=1,  # 1-待生成
            original_pic_url=image_a_url,
            style_pic_url=image_b_url,
            strength=int(strength * 100),  # 将0-1的强度转为0-100的整数存储
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为2
            image_count = settings.image_generation.style_transfer_count if hasattr(settings.image_generation, "style_transfer_count") else 1
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动异步任务处理风格转换
            first_result_id = result_ids[0] if result_ids else None
            if first_result_id:
                asyncio.create_task(
                    ImageService.process_style_transfer(first_result_id, strength)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create style transfer task: {str(e)}")
            raise e

    @staticmethod
    async def process_style_transfer(result_id: int, strength: float = 0.5):
        """处理风格转换任务
        
        Args:
            result_id: 结果记录ID
            strength: 风格应用强度，0-1之间
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
            
            # 更新任务和结果状态为生成中
            if task.status == 1:
                task.status = 2  # 生成中
                task.update_time = datetime.utcnow()
            
            result.status = 2  # 生成中
            result.update_time = datetime.utcnow()
            db.commit()
            
            try:
                # 创建InfiniAI适配器
                adapter = InfiniAIAdapter()
                
                # 调用风格转换
                generated_urls = adapter.transfer_style(
                    image_a_url=task.original_pic_url,
                    image_b_url=task.style_pic_url,
                    strength=strength or 0.5
                )
                
                if not generated_urls:
                    raise Exception("No images generated from InfiniAI")
                
                # 获取第一个生成的图片URL
                result_pic = generated_urls[0]
                
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
                
                logger.info(f"Style transfer completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                # 更新失败计数
                result.fail_count = (result.fail_count or 0) + 1
                
                # 如果失败次数超过3次，标记为失败
                if result.fail_count > 3:
                    result.status = 4  # 生成失败
                    logger.error(f"Style transfer failed after 3 attempts for result {result_id}")
                else:
                    result.status = 1  # 重置为待生成，等待补偿任务重试
                    logger.warning(f"Style transfer failed for result {result_id}, will retry later. Fail count: {result.fail_count}")
                
                result.update_time = datetime.utcnow()
                db.commit()
                
                logger.error(f"Error in style transfer for result {result_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing style transfer for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    async def create_fabric_transfer_task(
        db: Session,
        uid: int,
        fabric_image_url: str,
        model_image_url: str,
        model_mask_url: str = None
    ) -> Dict[str, Any]:
        """创建面料转换任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            fabric_image_url: 面料图片URL
            model_image_url: 模特图片URL
            model_mask_url: 模特蒙版URL，可选
            
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=5,  # 5-面料转换
            status=1,  # 1-待生成
            original_pic_url=fabric_image_url,
            model_pic_url=model_image_url,
            mask_pic_url=model_mask_url,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为2
            image_count = settings.image_generation.fabric_transfer_count if hasattr(settings.image_generation, "fabric_transfer_count") else 1
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动异步任务处理面料转换
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_fabric_transfer(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create fabric transfer task: {str(e)}")
            raise e

    @staticmethod
    async def create_change_color_task(
        db: Session,
        uid: int,
        image_url: str,
        clothing_text: str,
        hex_color: str
    ) -> Dict[str, Any]:
        """创建改变颜色任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            image_url: 图片URL
            clothing_text: 服装描述
            hex_color: 十六进制颜色代码
            
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=4,  # 4-magic kit
            variation_type=1,  # 1-change color
            status=1,  # 1-待生成
            original_pic_url=image_url,
            original_prompt=clothing_text,
            hex_color=hex_color,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为2
            image_count = settings.image_generation.change_color_count if hasattr(settings.image_generation, "change_color_count") else 1
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动异步任务处理变更颜色
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_change_color(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create change color task: {str(e)}")
            raise e


    @staticmethod
    async def process_fabric_transfer(result_id: int):
        """处理面料转换任务
        
        Args:
            result_id: 结果记录ID
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
            
            # 更新任务和结果状态为生成中
            if task.status == 1:
                task.status = 2  # 生成中
                task.update_time = datetime.utcnow()
            
            result.status = 2  # 生成中
            result.update_time = datetime.utcnow()
            db.commit()
            
            try:
                # 创建InfiniAI适配器
                adapter = InfiniAIAdapter()
                
                # 调用面料转换
                generated_urls = adapter.transfer_fabric(
                    fabric_image_url=task.original_pic_url,
                    model_image_url=task.model_pic_url,
                    model_mask_url=task.mask_pic_url
                )
                
                if not generated_urls:
                    raise Exception("No images generated from InfiniAI")
                
                # 获取第一个生成的图片URL
                result_pic = generated_urls[0]
                
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
                
                logger.info(f"Fabric transfer completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                # 更新失败计数
                result.fail_count = (result.fail_count or 0) + 1
                
                # 如果失败次数超过3次，标记为失败
                if result.fail_count > 3:
                    result.status = 4  # 生成失败
                    logger.error(f"Fabric transfer failed after 3 attempts for result {result_id}")
                else:
                    result.status = 1  # 重置为待生成，等待补偿任务重试
                    logger.warning(f"Fabric transfer failed for result {result_id}, will retry later. Fail count: {result.fail_count}")
                
                result.update_time = datetime.utcnow()
                db.commit()
                
                logger.error(f"Error in fabric transfer for result {result_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing fabric transfer for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 
            
    @staticmethod
    async def process_change_color(result_id: int):
        """处理改变颜色任务
        
        Args:
            result_id: 结果记录ID
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
                result_pic = await thenewblack.create_change_color(
                    image_url=task.original_pic_url,
                    clothing_text=task.original_prompt,
                    hex_color=task.hex_color,
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
                
                logger.info(f"Change color completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                # 更新失败计数
                result.fail_count = (result.fail_count or 0) + 1
                
                # 如果失败次数超过3次，标记为失败
                if result.fail_count > 3:
                    result.status = 4  # 生成失败
                    logger.error(f"Change color failed after 3 attempts for result {result_id}")
                else:
                    result.status = 1  # 重置为待生成，等待补偿任务重试
                    logger.warning(f"Change color failed for result {result_id}, will retry later. Fail count: {result.fail_count}")
                
                result.update_time = datetime.utcnow()
                db.commit()
                
                logger.error(f"Error in change color for result {result_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing change color for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 


    @staticmethod
    async def create_change_background_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        refer_pic_url: str,
        background_prompt: str
    ) -> Dict[str, Any]:
        """创建改变背景任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            original_pic_url: 图片URL
            refer_pic_url: 参考图片URL
            background_prompt: 背景描述
            
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=4,  # 4-magic kit
            variation_type=2,  # 2-change background
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            original_prompt=background_prompt,
            refer_pic_url=refer_pic_url,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为2
            image_count = settings.image_generation.change_background_count if hasattr(settings.image_generation, "change_background_count") else 1
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动异步任务处理改变背景
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_change_background(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create change background task: {str(e)}")
            raise e


    @staticmethod
    async def process_change_background(result_id: int):
        """处理改变背景任务
        
        Args:
            result_id: 结果记录ID
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
            
            # 更新任务和结果状态为生成中
            if task.status == 1:
                task.status = 2  # 生成中
                task.update_time = datetime.utcnow()
            
            result.status = 2  # 生成中
            result.update_time = datetime.utcnow()
            db.commit()
            
            try:
                # 创建InfiniAI适配器
                adapter = InfiniAIAdapter()
                
                # 调用面料转换
                generated_urls = await adapter.comfy_request_change_background(
                    original_image_url=task.original_pic_url,
                    reference_image_url=task.refer_pic_url,
                    background_prompt=task.original_prompt
                )
                
                if not generated_urls:
                    raise Exception("No images generated from InfiniAI")
                
                # 获取第一个生成的图片URL
                result_pic = generated_urls[0]
                
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
                
                logger.info(f"change_background completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                # 更新失败计数
                result.fail_count = (result.fail_count or 0) + 1
                
                # 如果失败次数超过3次，标记为失败
                if result.fail_count > 3:
                    result.status = 4  # 生成失败
                    logger.error(f"change_background failed after 3 attempts for result {result_id}")
                else:
                    result.status = 1  # 重置为待生成，等待补偿任务重试
                    logger.warning(f"change_background failed for result {result_id}, will retry later. Fail count: {result.fail_count}")
                
                result.update_time = datetime.utcnow()
                db.commit()
                
                logger.error(f"Error in change_background for result {result_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing change_background for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 
       

    @staticmethod
    async def create_remove_background_task(
        db: Session,
        uid: int,
        original_pic_url: str
    ) -> Dict[str, Any]:
        """创建去除背景任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            original_pic_url: 图片URL
            
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=4,  # 4-magic kit
            variation_type=3,  # 3-remove background
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为2
            image_count = settings.image_generation.remove_background_count if hasattr(settings.image_generation, "remove_background_count") else 1
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动异步任务处理移除背景
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_remove_background(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create remove background task: {str(e)}")
            raise e


    @staticmethod
    async def process_remove_background(result_id: int):
        """处理去除背景任务
        
        Args:
            result_id: 结果记录ID
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
            
            # 更新任务和结果状态为生成中
            if task.status == 1:
                task.status = 2  # 生成中
                task.update_time = datetime.utcnow()
            
            result.status = 2  # 生成中
            result.update_time = datetime.utcnow()
            db.commit()
            
            try:
                # 创建Replicate适配器
                adapter = ReplicateAdapter()
                
                # 调用面料转换
                result_pic = await adapter.remove_background(
                    image_url=task.original_pic_url,
                )
                
                if not result_pic:
                    raise Exception("No images generated from Replicate")
                
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
                
                logger.info(f"Remove background completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                # 更新失败计数
                result.fail_count = (result.fail_count or 0) + 1
                
                # 如果失败次数超过3次，标记为失败
                if result.fail_count > 3:
                    result.status = 4  # 生成失败
                    logger.error(f"Remove background failed after 3 attempts for result {result_id}")
                else:
                    result.status = 1  # 重置为待生成，等待补偿任务重试
                    logger.warning(f"Remove background failed for result {result_id}, will retry later. Fail count: {result.fail_count}")
                
                result.update_time = datetime.utcnow()
                db.commit()
                
                logger.error(f"Error in remove background for result {result_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing remove background for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 
       


    @staticmethod
    async def create_particial_modification_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        mask_pic_url: str,
        prompt: str
    ) -> Dict[str, Any]:
        """创建局部修改任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            original_pic_url: 图片URL
            mask_pic_url: 蒙版图片URL
            prompt: 修改描述
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=4,  # 4-magic kit
            variation_type=4,  # 4-particial modification
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            refer_pic_url=mask_pic_url,
            original_prompt=prompt,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为2
            image_count = settings.image_generation.particial_modification_count if hasattr(settings.image_generation, "particial_modification_count") else 1
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动异步任务处理局部修改
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_particial_modification(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create particial modification task: {str(e)}")
            raise e


    @staticmethod
    async def process_particial_modification(result_id: int):
        """处理局部修改任务
        
        Args:
            result_id: 结果记录ID
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
            
            # 更新任务和结果状态为生成中
            if task.status == 1:
                task.status = 2  # 生成中
                task.update_time = datetime.utcnow()
            
            result.status = 2  # 生成中
            result.update_time = datetime.utcnow()
            db.commit()
            
            try:
                # 创建ideogram适配器
                adapter = IdeogramAdapter()
                
                # 调用面料转换
                result_pic = adapter.edit(
                    image=task.original_pic_url,
                    mask=task.refer_pic_url,
                    prompt=task.original_prompt
                )
                
                if not result_pic:
                    raise Exception("No images generated from Ideogram")
                
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
                
                logger.info(f"Particial modification completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                # 更新失败计数
                result.fail_count = (result.fail_count or 0) + 1
                
                # 如果失败次数超过3次，标记为失败
                if result.fail_count > 3:
                    result.status = 4  # 生成失败
                    logger.error(f"Particial modification failed after 3 attempts for result {result_id}")
                else:
                    result.status = 1  # 重置为待生成，等待补偿任务重试
                    logger.warning(f"Particial modification failed for result {result_id}, will retry later. Fail count: {result.fail_count}")
                
                result.update_time = datetime.utcnow()
                db.commit()
                
                logger.error(f"Error in particial modification for result {result_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing particial modification for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 
       

    @staticmethod
    async def create_upscale_task(
        db: Session,
        uid: int,
        original_pic_url: str
    ) -> Dict[str, Any]:
        """创建局部修改任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            original_pic_url: 图片URL
            mask_pic_url: 蒙版图片URL
            prompt: 修改描述
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=4,  # 4-magic kit
            variation_type=5,  # 5-upscale
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为2
            image_count = settings.image_generation.upscale_count if hasattr(settings.image_generation, "upscale_count") else 1
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()  # 刷新以获取ID，但不提交事务
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动异步任务处理高清化
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_upscale(result_id)
                )
                
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create particial modification task: {str(e)}")
            raise e


    @staticmethod
    async def process_upscale(result_id: int):
        """处理高清化任务
        
        Args:
            result_id: 结果记录ID
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
            
            # 更新任务和结果状态为生成中
            if task.status == 1:
                task.status = 2  # 生成中
                task.update_time = datetime.utcnow()
            
            result.status = 2  # 生成中
            result.update_time = datetime.utcnow()
            db.commit()
            
            try:
                # 创建Replicate适配器
                adapter = ReplicateAdapter()
                
                # 调用面料转换
                result_pic = await adapter.upscale(
                    image_url=task.original_pic_url,
                )
                
                if not result_pic:
                    raise Exception("No images generated from Replicate")
                
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
                
                logger.info(f"Upscale completed for result {result_id}, task {task.id}")
                
            except Exception as e:
                # 更新失败计数
                result.fail_count = (result.fail_count or 0) + 1
                
                # 如果失败次数超过3次，标记为失败
                if result.fail_count > 3:
                    result.status = 4  # 生成失败
                    logger.error(f"Upscale failed after 3 attempts for result {result_id}")
                else:
                    result.status = 1  # 重置为待生成，等待补偿任务重试
                    logger.warning(f"Upscale failed for result {result_id}, will retry later. Fail count: {result.fail_count}")
                
                result.update_time = datetime.utcnow()
                db.commit()
                
                logger.error(f"Error in upscale for result {result_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing upscale for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 
       