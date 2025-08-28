from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import uuid
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from src.alg.caption import FashionProductDescription
from src.alg.ideogram_adapter import IdeogramAdapter
from src.alg.replicate_adapter import ReplicateAdapter
from src.constants.gen_img_type import GenImgType
from src.exceptions.base import CustomException
from src.exceptions.pay import CreditError
from src.services.rabbitmq_service import rabbitmq_service
from src.services.credit_service import CreditService
from src.utils.uid import generate_uid

from ..models.models import CollectImg, GenImgRecord, GenImgResult, ImgMaterialTags, ImgStyleTags, Material, TrendStyle  # 导入两个模型
from ..db.redis import redis_client
from ..db.session import SessionLocal, get_db
from ..config.log_config import logger
from ..config.config import settings
from ..alg.ideogram_adapter import IdeogramAdapter  # 导入Ideogram适配器
from ..utils.style_prompts import get_random_style_prompt
from ..alg.intention_detector import IntentionDetector
from ..alg.infiniai_adapter import InfiniAIAdapter
from ..alg.thenewblack import Gender, TheNewBlack

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
            type=GenImgType.TEXT_TO_IMAGE.value.type,  # 1-文生图
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
            image_count = settings.image_generation.text_to_image.gen_count
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                # 创建结果记录，包含风格信息
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    prompt=prompt,
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
                    ImageService.process_text_to_image_generation(result_id)
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
            type=GenImgType.FABRIC_TO_DESIGN.value.type,  # 2-图生图
            variation_type=GenImgType.FABRIC_TO_DESIGN.value.variationType, # 2-Fabric to Design
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
            image_count = settings.image_generation.fabric_to_design.gen_count
            
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
            type=GenImgType.COPY_STYLE.value.type,  # 2-图转图(洗图)
            variation_type = GenImgType.COPY_STYLE.value.variationType, # 1-洗图
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
            image_count = settings.image_generation.copy_style.gen_count
            
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
            type=GenImgType.SKETCH_TO_DESIGN.value.type,  # 2-图生图
            variation_type=GenImgType.SKETCH_TO_DESIGN.value.variationType, # Sketch to Design
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
            image_count = settings.image_generation.sketch_to_design.gen_count
            
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
            type=GenImgType.MIX_IMAGE.value.type,  # 2-图生图
            variation_type=GenImgType.MIX_IMAGE.value.variationType, # 5-混合图片
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            original_prompt=prompt,
            refer_pic_url=refer_pic_url,
            fidelity=int(fidelity * 100),  # 将0-1保真度按百分比入库
            create_time=now,
            update_time=now
        )

        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量
            image_count = settings.image_generation.mix_image.gen_count
            
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
    async def create_vary_style_image_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        refer_pic_url: str,
        prompt: str,
        style_strength_level: str = "middle"
    ) -> Dict[str, Any]:
        """创建风格变换任务"""
        
        # 创建任务记录  
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=GenImgType.VARY_STYLE_IMAGE.value.type,  # 2-图生图
            variation_type=GenImgType.VARY_STYLE_IMAGE.value.variationType, # 11-图片风格变换
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            original_prompt=prompt,
            refer_pic_url=refer_pic_url,
            fidelity=50,  # 默认50作为占位符，实际使用style_strength_level
            create_time=now,
            update_time=now
        )

        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量
            image_count = settings.image_generation.vary_style_image.gen_count
            
            # 创建指定数量的结果记录
            result_ids = []
            for i in range(image_count):
                result = GenImgResult(
                    gen_id=task.id,
                    uid=uid,
                    status=1,  # 1-待生成
                    result_pic="",
                    create_time=now,
                    update_time=now
                )
                db.add(result)
                db.flush()
                result_ids.append(result.id)
            
            # 提交事务
            db.commit()
            
            # 启动并行的图像生成任务
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_vary_style_image_generation(result_id, style_strength_level)
                )
            
            return {
                "taskId": task.id,
                "status": task.status,
                "estimatedTime": 60
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create vary style image task: {str(e)}")
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
            type=GenImgType.VIRTUAL_TRY_ON.value.type,  # 3-虚拟试穿
            variation_type=GenImgType.VIRTUAL_TRY_ON.value.variationType, # 1-虚拟试穿
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
            image_count = settings.image_generation.virtual_try_on.gen_count
            
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
    async def apply_supir_enhancement(image_url: str, strength: float = 0.5, upscale_size: int = 2048, face_fix_denoise: float = 0.3) -> str:
        """
        通用SUPIR图像增强后处理 - 已禁用SUPIR，直接返回原图
        
        Args:
            image_url: 原始图像URL
            strength: 增强强度 (0-1)
            upscale_size: 放大尺寸
            face_fix_denoise: 人脸修复去噪强度 (0-1)
            
        Returns:
            增强后的图像URL
        """
        # ===============================================
        # SUPIR Fix Face 功能已被注释掉 - 直接返回原图
        # ===============================================
        logger.info(f"SUPIR enhancement disabled, returning original image: {image_url}")
        return image_url
        
        # ===============================================
        # 以下是原SUPIR Fix Face调用代码（已注释）
        # ===============================================
        # try:
        #     adapter = InfiniAIAdapter.get_adapter()
        #     enhanced_url = await adapter.comfy_request_supir_fix_face(
        #         original_image_url=image_url,
        #         strength=strength,
        #         upscale_size=upscale_size,
        #         face_fix_denoise=face_fix_denoise,
        #         seed=None
        #     )
        #     
        #     if not enhanced_url:
        #         logger.warning(f"SUPIR enhancement failed for {image_url}, returning original")
        #         return image_url
        #         
        #     logger.info(f"Successfully applied SUPIR enhancement to image")
        #     return enhanced_url
        #     
        # except Exception as e:
        #     logger.error(f"Error applying SUPIR enhancement: {str(e)}")
        #     # 如果SUPIR处理失败，返回原始图像而不是抛出异常
        #     return image_url
    
    @staticmethod
    async def call_generation_api(task: GenImgRecord, result: GenImgResult, enhanced_prompt: str) -> str:
        """调用图像生成API"""
        try:
            # 初始化Ideogram适配器
            ideogram_adapter = IdeogramAdapter.get_adapter()
            
            # 构建增强的提示词，包含模特信息
            final_prompt = enhanced_prompt
            if task.with_human_model == 1:
                # 添加模特相关信息到提示词
                gender_text = "male" if task.gender == 1 else "female"
                final_prompt = f"{enhanced_prompt}, {gender_text} model wearing the clothing"
            
            # 映射宽高比格式到Ideogram的aspect_ratio（注意：Ideogram使用 x 而不是 :）
            aspect_ratio_map = {
                "1:1": "1x1",
                "2:3": "2x3", 
                "3:4": "3x4",
                "9:16": "9x16",
            }
            aspect_ratio = aspect_ratio_map.get(task.format, "1x1")
            
            # 调用Ideogram generate方法生成图片
            result_pics = await ideogram_adapter.generate(
                prompt=final_prompt,
                aspect_ratio=aspect_ratio,
                rendering_speed="DEFAULT",
                style_type="DESIGN",  # 服装设计适合用DESIGN风格
                num_images=1
            )
            
            # 获取第一张图片URL
            if not result_pics or len(result_pics) == 0:
                raise Exception("Failed to generate image: no images returned")
                
            # 应用SUPIR增强后处理
            result_pic = result_pics[0]
            try:
                enhanced_pic = await ImageService.apply_supir_enhancement(result_pic)
                return enhanced_pic
            except Exception as e:
                logger.warning(f"SUPIR enhancement failed, using original image: {str(e)}")
                return result_pic
            
        except Exception as e:
            logger.error(f"Failed to call generation API: {str(e)}")
            raise e

    @staticmethod
    async def process_text_to_image_generation(result_id: int):
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
                
                credit_value = settings.image_generation.text_to_image.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.text_to_image.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
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
                
                credit_value = settings.image_generation.fabric_to_design.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
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
        
                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.fabric_to_design.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
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
                
                logger.info(f"virtual try on completed for result {result_id}, task {task.id}")
                
                credit_value = settings.image_generation.virtual_try_on.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to generate virtual try on image for result {result_id}, task {task.id}: {str(e)}")
                
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.virtual_try_on.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
        except Exception as e:
            logger.error(f"Error processing vitual try on generation for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    async def create_virtual_try_on_manual_task(
        db: Session,
        uid: int,
        model_image_url: str,
        model_mask_url: str,
        garment_image_url: str,
        garment_mask_url: str,
        model_margin: int,
        garment_margin: int
    ) -> Dict[str, Any]:
        """创建虚拟试穿手动版任务"""

        # 创建任务记录
        now = datetime.utcnow()
        
        # 将额外参数存储到JSON字段中
        input_params = {
            "model_margin": model_margin,
            "garment_margin": garment_margin
        }
        
        task = GenImgRecord(
            uid=uid,
            type=GenImgType.VIRTUAL_TRY_ON_MANUAL.value.type,  # 3-虚拟试穿
            variation_type=GenImgType.VIRTUAL_TRY_ON_MANUAL.value.variationType, # 3-虚拟试穿手动版
            status=1,  # 1-待生成
            original_pic_url=model_image_url,
            refer_pic_url=garment_image_url,
            clothing_photo=garment_mask_url,
            mask_pic_url=model_mask_url,
            input_param_json=input_params,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量
            image_count = settings.image_generation.virtual_try_on.gen_count
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                
                # 创建结果记录
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
                    ImageService.process_virtual_try_on_manual_generation(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            logger.error(f"Failed to create virtual try on manual task: {str(e)}")
            db.rollback()
            raise e

    @staticmethod
    async def process_virtual_try_on_manual_generation(result_id: int):
        """处理虚拟试穿手动版任务"""
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
                # 从JSON字段中获取参数
                input_params = task.input_param_json or {}
                model_margin = input_params.get("model_margin", 10)  # 默认值
                garment_margin = input_params.get("garment_margin", 10)  # 默认值
                
                # 调用InfiniAI适配器进行虚拟试穿手动版处理
                result_pic = await InfiniAIAdapter.get_adapter().comfy_request_virtual_tryon_manual(
                    model_image_url=task.original_pic_url,
                    model_mask_url=task.mask_pic_url,
                    garment_image_url=task.refer_pic_url,
                    garment_mask_url=task.clothing_photo,
                    model_margin=model_margin,
                    garment_margin=garment_margin,
                    seed=None
                )
                
                # 应用SUPIR增强处理
                enhanced_pic = await ImageService.apply_supir_enhancement(result_pic)
                
                # 更新结果记录状态为成功
                result.status = 3  # 已生成
                result.result_pic = enhanced_pic
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
                
                logger.info(f"virtual try on manual completed for result {result_id}, task {task.id}")
                
                credit_value = settings.image_generation.virtual_try_on.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to generate virtual try on manual image for result {result_id}, task {task.id}: {str(e)}")
                
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.virtual_try_on.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
        except Exception as e:
            logger.error(f"Error processing virtual try on manual generation for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    async def create_extend_image_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        top_padding: int,
        right_padding: int,
        bottom_padding: int,
        left_padding: int
    ) -> Dict[str, Any]:
        """创建扩图任务"""

        # 创建任务记录
        now = datetime.utcnow()
        
        # 将扩图参数存储到JSON字段中
        input_params = {
            "top_padding": top_padding,
            "right_padding": right_padding,
            "bottom_padding": bottom_padding,
            "left_padding": left_padding
        }
        
        task = GenImgRecord(
            uid=uid,
            type=GenImgType.EXTEND_IMAGE.value.type,  # 4-Magic Kit
            variation_type=GenImgType.EXTEND_IMAGE.value.variationType, # 9-扩图
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            input_param_json=input_params,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量 (默认1个)
            image_count = getattr(settings.image_generation, 'extend_image', type('obj', (object,), {'gen_count': 1})).gen_count
            
            # 创建指定数量的结果记录并存储它们的ID
            result_ids = []
            for i in range(image_count):
                
                # 创建结果记录
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
                    ImageService.process_extend_image_generation(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            logger.error(f"Failed to create extend image task: {str(e)}")
            db.rollback()
            raise e

    @staticmethod
    async def process_extend_image_generation(result_id: int):
        """处理扩图任务"""
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
                # 从JSON字段中获取参数
                input_params = task.input_param_json or {}
                top_padding = input_params.get("top_padding", 0)
                right_padding = input_params.get("right_padding", 0)
                bottom_padding = input_params.get("bottom_padding", 0)
                left_padding = input_params.get("left_padding", 0)
                
                # 调用InfiniAI适配器进行扩图处理
                result_pic = await InfiniAIAdapter.get_adapter().comfy_request_extend_image(
                    original_image_url=task.original_pic_url,
                    top_padding=top_padding,
                    right_padding=right_padding,
                    bottom_padding=bottom_padding,
                    left_padding=left_padding,
                    seed=None
                )
                
                # 应用SUPIR增强处理
                enhanced_pic = await ImageService.apply_supir_enhancement(result_pic)
                
                # 更新结果记录状态为成功
                result.status = 3  # 已生成
                result.result_pic = enhanced_pic
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
                
                logger.info(f"extend image completed for result {result_id}, task {task.id}")
                
                # 使用默认的magic kit积分设置
                credit_value = getattr(settings.image_generation, 'extend_image', 
                                     getattr(settings.image_generation, 'upscale', type('obj', (object,), {'use_credit': 1}))).use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to generate extend image for result {result_id}, task {task.id}: {str(e)}")
                
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

                if result.fail_count >= 3:
                    try:
                        credit_value = getattr(settings.image_generation, 'extend_image', 
                                             getattr(settings.image_generation, 'upscale', type('obj', (object,), {'use_credit': 1}))).use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
        except Exception as e:
            logger.error(f"Error processing extend image generation for result {result_id}: {str(e)}")
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
                
                credit_value = settings.image_generation.sketch_to_design.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.sketch_to_design.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
        
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

                # 使用新的 Mix_2images 融合接口（保留兼容的强度语义：fidelity 作为 mix_weight）
                result_pic = await InfiniAIAdapter.get_adapter().comfy_request_mix_2images(
                    original_image_url=task.original_pic_url,
                    reference_image_url=task.refer_pic_url,
                    mix_weight=fidelity,
                    seed=None
                )
                
                # 应用SUPIR增强处理
                enhanced_pic = await ImageService.apply_supir_enhancement(result_pic)
                
                # 更新结果记录状态为成功
                result.status = 3  # 已生成
                result.result_pic = enhanced_pic
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
                
                credit_value = settings.image_generation.mix_image.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
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
        
                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.mix_image.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
        
        except Exception as e:
            logger.error(f"Error processing mix image generation for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    async def process_vary_style_image_generation(result_id: int, style_strength_level: str = "middle"):
        """处理风格变换图片任务"""
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
                # 映射风格强度级别到数值
                style_strength_map = {"low": 0.3, "middle": 0.5, "high": 0.9}
                style_strength = style_strength_map.get(style_strength_level, 0.5)
                control_strength = 0.8  # 默认原图控制强度
                
                # 使用风格变换接口
                result_pic = await InfiniAIAdapter.get_adapter().comfy_request_vary_style_image(
                    original_image_url=task.original_pic_url,
                    reference_image_url=task.refer_pic_url,
                    control_strength=control_strength,
                    style_strength=style_strength,
                    seed=None
                )
                
                # 应用SUPIR增强处理
                enhanced_pic = await ImageService.apply_supir_enhancement(result_pic)
                
                # 更新结果记录状态为成功
                result.status = 3  # 已生成
                result.result_pic = enhanced_pic
                result.update_time = datetime.utcnow()
                result.fail_count = 0
                
                # 检查该任务的所有结果记录是否都成功
                all_results = db.query(GenImgResult).filter(GenImgResult.gen_id == task.id).all()
                all_successful = all(r.status == 3 for r in all_results)
                
                # 只有当所有结果都成功时，才更新任务状态为成功
                if all_successful:
                    task.status = 3  # 已生成
                    task.update_time = datetime.utcnow()
                
                logger.info(f"Style vary completed for result {result_id}, task {task.id}")
                db.commit()
                
            except Exception as e:
                logger.error(f"Error during style vary for result {result_id}: {str(e)}")
                # 更新结果记录状态为失败
                result.status = 4  # 生成失败
                result.update_time = datetime.utcnow()
                
                # 累加失败次数
                if result.fail_count is None:
                    result.fail_count = 1
                else:
                    result.fail_count += 1
                
                db.commit()
                
                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.vary_style_image.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
        
        except Exception as e:
            logger.error(f"Error processing vary style image generation for result {result_id}: {str(e)}")
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
                
                credit_value = settings.image_generation.copy_style.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
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
        
                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.copy_style.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
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
            type=GenImgType.CHANGE_CLOTHES.value.type,  # 2-图转图
            variation_type=GenImgType.CHANGE_CLOTHES.value.variationType,  # 2-更换服装
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
            image_count = settings.image_generation.change_clothes.gen_count
            
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
                
                credit_value = settings.image_generation.change_clothes.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
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
        
                if result.fail_count >= 3:
                    try:
                        credit_value = CreditService.get_credit_value_by_type(GenImgType.get_by_type_and_variation_type(task.type, task.variation_type))
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
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
            
            is_collected = db.query(
                CollectImg
            ).filter(
                CollectImg.user_id == uid,
                CollectImg.gen_img_id == result.id
            ).first()

            # 构建单条记录
            history_item = {
                "genImgId": result.id,  # GenImgResult的ID
                "genId": result.gen_id,  # 对应的GenImgRecord的ID
                "type": record.type,     # 生成类型
                "variationType": record.variation_type,  # 变化类型
                "status": result.status,  # 状态
                "resultPic": result.result_pic,  # 生成结果图片URL
                "isCollected": 1 if is_collected else 0,
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
            "resultPic": result.result_pic or "",  # 处理None值，返回空字符串
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
    def delete_image(
        db: Session,
        uid: int,
        gen_img_id: int
    ) -> int:
        """删除图片
        
        Args:
            db: 数据库会话
            uid: 用户ID
            gen_img_id: 图片ID

        Returns:
            删除的图片ID
        """
        # 删除图片
        result = db.query(GenImgResult).filter(GenImgResult.id == gen_img_id, GenImgResult.uid == uid).delete()
        db.commit()
        return result

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
            type=GenImgType.STYLE_TRANSFER.value.type,  # 2-图生图
            variation_type=GenImgType.STYLE_TRANSFER.value.variationType,  # 5-风格转换
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
            image_count = settings.image_generation.style_transfer.gen_count
            
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
                result_pic = adapter.transfer_style(
                    image_a_url=task.original_pic_url,
                    image_b_url=task.style_pic_url,
                    strength=strength or 0.5
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
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
                
                credit_value = settings.image_generation.style_transfer.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing style transfer for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.style_transfer.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
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
            type=GenImgType.FABRIC_TRANSFER.value.type,  # 5-面料转换
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
            image_count = settings.image_generation.fabric_transfer.gen_count
            
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
            type=GenImgType.CHANGE_COLOR.value.type,  # 4-magic kit
            variation_type=GenImgType.CHANGE_COLOR.value.variationType,  # 1-change color
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
            image_count = settings.image_generation.change_color.gen_count
            
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
                result_pic = adapter.transfer_fabric(
                    fabric_image_url=task.original_pic_url,
                    model_image_url=task.model_pic_url,
                    model_mask_url=task.mask_pic_url
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
                
                logger.info(f"Fabric transfer completed for result {result_id}, task {task.id}")
                
                credit_value = settings.image_generation.fabric_transfer.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing fabric transfer for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.fabric_transfer.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
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
                
                credit_value = settings.image_generation.change_color.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing change color for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.change_color.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
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
            type=GenImgType.CHANGE_BACKGROUND.value.type,  # 4-magic kit
            variation_type=GenImgType.CHANGE_BACKGROUND.value.variationType,  # 2-change background
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
            image_count = settings.image_generation.change_background.gen_count
            
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
                result_pic = await adapter.comfy_request_change_background(
                    original_image_url=task.original_pic_url,
                    reference_image_url=task.refer_pic_url,
                    background_prompt=task.original_prompt
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
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
                
                credit_value = settings.image_generation.change_background.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing change_background for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.change_background.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
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
            type=GenImgType.REMOVE_BACKGROUND.value.type,  # 4-magic kit
            variation_type=GenImgType.REMOVE_BACKGROUND.value.variationType,  # 3-remove background
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
            image_count = settings.image_generation.remove_background.gen_count
            
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
                # 使用 InfiniAI comfy 去背景工作流（保留 Replicate 方案，现切换为 comfy 方案）
                adapter = InfiniAIAdapter()

                # 默认背景色使用透明，可按需扩展为请求参数或配置
                result_pic = await adapter.comfy_request_remove_background(
                    original_image_url=task.original_pic_url,
                    background_color="transparent"
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
                # 应用SUPIR增强处理
                enhanced_pic = await ImageService.apply_supir_enhancement(result_pic)
                
                # 更新结果记录状态为成功
                result.status = 3  # 已生成
                result.result_pic = enhanced_pic
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
                
                credit_value = settings.image_generation.remove_background.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing remove background for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.remove_background.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
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
            type=GenImgType.PARTICIAL_MODIFICATION.value.type,  # 4-magic kit
            variation_type=GenImgType.PARTICIAL_MODIFICATION.value.variationType,  # 4-particial modification
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
            image_count = settings.image_generation.particial_modification.gen_count
            
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
            for idx, result_id in enumerate(result_ids):
                asyncio.create_task(
                    ImageService.process_particial_modification(result_id)
                )
            
            # 返回任务信息
            task_info = {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            return task_info
            
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
        logger.info(f"[Partial Modification Process] Starting processing for result_id: {result_id}")
        
        db = SessionLocal()
        try:
            # 获取结果记录
            logger.info(f"[Partial Modification Process] Fetching result record for ID: {result_id}")
            result = db.query(GenImgResult).filter(GenImgResult.id == result_id).first()
            
            if not result:
                logger.error(f"[Partial Modification Process] Result record {result_id} not found")
                return
            
            logger.info(f"[Partial Modification Process] Found result record: gen_id={result.gen_id}, uid={result.uid}, status={result.status}")
            
            # 获取关联的任务记录
            logger.info(f"[Partial Modification Process] Fetching task record for gen_id: {result.gen_id}")
            task = db.query(GenImgRecord).filter(GenImgRecord.id == result.gen_id).first()
            
            if not task:
                logger.error(f"[Partial Modification Process] Task {result.gen_id} not found for result {result_id}")
                return
            
            logger.info(f"[Partial Modification Process] Found task record: id={task.id}, uid={task.uid}, type={task.type}, variation_type={task.variation_type}")
            logger.info(f"[Partial Modification Process] Task details: original_pic_url={task.original_pic_url}, refer_pic_url={task.refer_pic_url}, prompt='{task.original_prompt}'")
            
            # 更新任务和结果状态为生成中
            if task.status == 1:
                logger.info(f"[Partial Modification Process] Updating task {task.id} status from 1 (pending) to 2 (processing)")
                task.status = 2  # 生成中
                task.update_time = datetime.utcnow()
            
            logger.info(f"[Partial Modification Process] Updating result {result_id} status from {result.status} to 2 (processing)")
            result.status = 2  # 生成中
            result.update_time = datetime.utcnow()
            db.commit()
            
            try:
                # 使用 InfiniAI（Comfy 工作流）适配器
                adapter = InfiniAIAdapter()

                # 调用 Comfy 局部修改工作流
                result_pic = await adapter.comfy_request_partial_modify(
                    original_image_url=task.original_pic_url,
                    original_mask_url=task.refer_pic_url,
                    prompt=task.original_prompt,
                    seed=None
                )

                if not result_pic:
                    raise Exception("No images generated from InfiniAI")

                logger.info(f"[Partial Modification Process] InfiniAI Comfy workflow returned result for result {result_id}: {result_pic}")
                
                # 更新结果记录状态为成功
                logger.info(f"[Partial Modification Process] Updating result {result_id} to success status")
                result.status = 3  # 已生成

                result.result_pic = result_pic  # 修复变量名错误

                result.update_time = datetime.utcnow()
                result.fail_count = 0
                
                # 检查该任务的所有结果记录是否都成功
                logger.info(f"[Partial Modification Process] Checking if all results for task {task.id} are successful")
                all_results = db.query(GenImgResult).filter(GenImgResult.gen_id == task.id).all()
                all_successful = all(r.status == 3 for r in all_results)
                
                logger.info(f"[Partial Modification Process] Task {task.id} has {len(all_results)} results, all_successful: {all_successful}")
                for idx, r in enumerate(all_results):
                    logger.info(f"[Partial Modification Process] Result {idx+1}: id={r.id}, status={r.status}")
                
                # 只有当所有结果都成功时，才更新任务状态为成功
                if all_successful:
                    logger.info(f"[Partial Modification Process] Updating task {task.id} to success status")
                    task.status = 3  # 已生成
                    task.update_time = datetime.utcnow()
                    logger.info(f"All results for task {task.id} are successful, task marked as complete")
                
                db.commit()
                
                logger.info(f"[Partial Modification Process] Partial modification completed for result {result_id}, task {task.id}")
                
                # 处理积分
                credit_value = settings.image_generation.particial_modification.use_credit
                logger.info(f"[Partial Modification Process] Processing credit spend of {credit_value} for user {task.uid}")
                await CreditService.real_spend_credit(db, task.uid, credit_value)
                logger.info(f"[Partial Modification Process] Credit spent successfully for user {task.uid}")

                # 发送消息队列通知
                task_data = {"genImgId":result.id}
                logger.info(f"[Partial Modification Process] Sending message queue notification: {task_data}")
                await rabbitmq_service.send_image_generation_message(task_data)
                logger.info(f"[Partial Modification Process] Message queue notification sent for result {result_id}")
                
            except CreditError as e:
                logger.error(f"[Partial Modification Process] Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
                import traceback
                logger.error(f"[Partial Modification Process] Credit error stack trace: {traceback.format_exc()}")
            except Exception as e:
                logger.error(f"[Partial Modification Process] Error processing partial modification for result {result_id}: {str(e)}")
                import traceback
                logger.error(f"[Partial Modification Process] Exception stack trace: {traceback.format_exc()}")
                
                # 更新结果记录为失败，并累加失败次数
                logger.info(f"[Partial Modification Process] Updating result {result_id} to failed status")
                result.status = 4  # 生成失败
                result.update_time = datetime.utcnow()
                
                # 累加失败次数
                if result.fail_count is None:
                    result.fail_count = 1
                else:
                    result.fail_count += 1
                
                logger.info(f"[Partial Modification Process] Result {result_id} failure count increased to {result.fail_count}")
                
                db.commit()

                if result.fail_count >= 3:
                    logger.info(f"[Partial Modification Process] Result {result_id} failed 3 times, unlocking credit for user {task.uid}")
                    try:
                        credit_value = settings.image_generation.particial_modification.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                        logger.info(f"[Partial Modification Process] Credit unlocked successfully for user {task.uid}")
                    except Exception as unlock_error:
                        logger.error(f"[Partial Modification Process] Failed to unlock credit for result {result_id}, task {task.id}: {str(unlock_error)}")
                        
        except Exception as e:
            logger.error(f"[Partial Modification Process] Outer exception for result {result_id}: {str(e)}")
            import traceback
            logger.error(f"[Partial Modification Process] Outer exception stack trace: {traceback.format_exc()}")
            db.rollback()
        finally:
            logger.info(f"[Partial Modification Process] Closing database connection for result {result_id}")
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
            type=GenImgType.UPSCALE.value.type,  # 4-magic kit
            variation_type=GenImgType.UPSCALE.value.variationType,  # 5-upscale
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
            image_count = settings.image_generation.upscale.gen_count
            
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
                # ===============================================
                # SUPIR Fix Face 直接调用已被注释掉 - 返回原图URL
                # ===============================================
                # logger.info(f"SUPIR Fix Face upscale disabled, returning original image: {task.original_pic_url}")
                # result_pic = task.original_pic_url  # 直接使用原图URL
                
                # ===============================================
                # 以下是原SUPIR Fix Face直接调用代码（已注释）
                # ===============================================
                # 使用 InfiniAI comfy 的 SUPIR Fix Face 放大流程（保留 Replicate，现切换为 comfy）
                adapter = InfiniAIAdapter()
                
                # 采用默认参数，必要时可从配置扩展
                result_pic = await adapter.comfy_request_supir_fix_face(
                    original_image_url=task.original_pic_url,
                    strength=0.7,
                    upscale_size=2048,
                    face_fix_denoise=0.5,
                    seed=None
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
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
                
                credit_value = settings.image_generation.upscale.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)

                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing upscale for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.upscale.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
        except Exception as e:
            logger.error(f"Error processing upscale for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 
       
    @staticmethod
    async def create_change_pattern_task(
        db: Session,
        uid: int,
        original_pic_url: str
    ) -> Dict[str, Any]:
        """创建局部修改任务
        
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
            type=GenImgType.CHANGE_PATTERN.value.type,  # 2-图生图
            variation_type=GenImgType.CHANGE_PATTERN.value.variationType,  # 6-change pattern
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
            
            # 从配置中获取要创建的结果记录数量，默认为1
            image_count = settings.image_generation.change_pattern.gen_count
            
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
            
            # 启动异步任务处理改变版型
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_change_pattern(result_id)
                )
                
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create change pattern task: {str(e)}")
            raise e

    @staticmethod
    async def process_change_pattern(result_id: int):
        """处理改变版型任务
        
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
                
                
                # 调用改变版型
                result_pic = await adapter.comfy_request_pattern_variation(
                    original_image_url=task.original_pic_url,
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
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
                
                logger.info(f"Change pattern completed for result {result_id}, task {task.id}")
                credit_value = settings.image_generation.change_pattern.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)
                
                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing change pattern for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.change_pattern.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
        except Exception as e:
            logger.error(f"Error processing change pattern for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 
      
    @staticmethod
    async def create_change_fabric_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        fabric_pic_url: str,
        mask_pic_url: str
    ) -> Dict[str, Any]:
        """创建局部修改任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            original_pic_url: 图片URL
            fabric_pic_url: 面料图片URL
            mask_pic_url: 蒙版图片URL
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=GenImgType.CHANGE_FABRIC.value.type,
            variation_type=GenImgType.CHANGE_FABRIC.value.variationType,
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            fabric_pic_url=fabric_pic_url,
            mask_pic_url=mask_pic_url,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为1
            image_count = settings.image_generation.change_fabric.gen_count
            
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
            
            # 启动异步任务处理改变版型
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_change_fabric(result_id)
                )
                
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create change fabric task: {str(e)}")
            raise e

    @staticmethod
    async def process_change_fabric(result_id: int):
        """处理改变面料任务
        
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
                
                
                # 调用面料替换工作流（保留原接口不删，这里切换为 fabric_replacement）
                result_pic = await adapter.comfy_request_fabric_replacement(
                    original_image_url=task.original_pic_url,
                    original_mask_url=task.mask_pic_url,
                    fabric_image_url=task.fabric_pic_url
                    # fabric_size 使用默认值 2048，必要时可从配置中扩展
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
                # 应用SUPIR增强处理
                enhanced_pic = await ImageService.apply_supir_enhancement(result_pic)
                
                # 更新结果记录状态为成功
                result.status = 3  # 已生成
                result.result_pic = enhanced_pic
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
                
                logger.info(f"Change fabric completed for result {result_id}, task {task.id}")
                credit_value = settings.image_generation.change_fabric.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)
                
                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing change fabric for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.change_fabric.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
        except Exception as e:
            logger.error(f"Error processing change fabric for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 

    @staticmethod
    async def create_change_printing_task(
        db: Session,
        uid: int,
        original_pic_url: str,
    ) -> Dict[str, Any]:
        """创建局部修改任务
        
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
            type=GenImgType.CHANGE_PRINTING.value.type,
            variation_type=GenImgType.CHANGE_PRINTING.value.variationType,
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
            
            # 从配置中获取要创建的结果记录数量，默认为1
            image_count = settings.image_generation.change_printing.gen_count
            
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
            
            # 启动异步任务处理改变版型
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_change_printing(result_id)
                )
                
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create change fabric task: {str(e)}")
            raise e

    @staticmethod
    async def process_change_printing(result_id: int):
        """处理改变印花任务
        
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
                
                
                # 调用改变印花
                result_pic = await adapter.comfy_request_printing_variation(
                    model_image_url=task.original_pic_url
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
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
                
                logger.info(f"Change printing completed for result {result_id}, task {task.id}")
                credit_value = settings.image_generation.change_printing.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)
                
                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing change printing for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.change_printing.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
        except Exception as e:
            logger.error(f"Error processing change printing for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close() 
       
    @staticmethod
    async def process_caption(result_id: int):
        """处理改变印花任务
        
        Args:
            result_id: 结果记录ID
        """
        db = SessionLocal()
        try:
            # 获取结果记录
            result = db.query(GenImgResult).filter(GenImgResult.id == result_id).first()
            
            if not result:
                logger.error(f"process_caption, Result record {result_id} not found")
                raise CustomException(code=601, message=f"process_caption, Result record {result_id} not found")
            
            if result.result_pic is None:
                logger.error(f"process_caption, Result record {result_id} has no result_pic")
                raise CustomException(code=601, message=f"process_caption, Result record {result_id} has no result_pic")
            
            # 获取关联的任务记录
            task = db.query(GenImgRecord).filter(GenImgRecord.id == result.gen_id).first()
            
            if not task:
                logger.error(f"process_caption, Task {result.gen_id} not found for result {result_id}")
                raise CustomException(code=601, message=f"process_caption, Task {result.gen_id} not found for result {result_id}")
            
            try:
                # 调用改变印花
                result = FashionProductDescription.caption(result.result_pic)
                
                if not result:
                    raise Exception("No images caption from FashionProductDescription")
                
                await ImageService.deal_image_caption(db, result_id, result.trend_style, result.material, result.ai_design_description)
                
                db.commit()
                
                logger.info(f"process caption completed for result {result_id}, task {task.id}")
            except Exception as e:
                logger.error(f"Error in process caption for result {result_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing process caption for result {result_id}: {str(e)}")
            raise e
        finally:
            db.close()

    @staticmethod
    async def deal_image_caption(db: Session, result_id: int, styles: List[str], materials: List[str], description: str):
        """处理图片描述
        
        Args:
            result_id: 结果记录ID
            style: 风格
            material: 面料
            description: 描述"""
        # 获取结果记录
        result = db.query(GenImgResult).filter(GenImgResult.id == result_id).first()
        
        if not result:
            logger.error(f"process_caption, Result record {result_id} not found")
            raise CustomException(code=601, message=f"process_caption, Result record {result_id} not found")
        
        if result.result_pic is None:
            logger.error(f"process_caption, Result record {result_id} has no result_pic")
            raise CustomException(code=601, message=f"process_caption, Result record {result_id} has no result_pic")
        
        result.description = description

        seo_img_uid = ""
        for style in styles:
            trend_style = db.query(TrendStyle).filter(TrendStyle.name == style).first()
            if not trend_style:
                trend_style = TrendStyle(name=style)
                db.add(trend_style)
                db.flush()
            style_id = trend_style.id

            img_style_tags = ImgStyleTags(
                gen_img_id=result_id,
                style_id=style_id
            )
            db.add(img_style_tags)
            seo_img_uid += f"{style}-"

        seo_img_uid += generate_uid()
        result.seo_img_uid = seo_img_uid

        for material in materials:
            cloth_material = db.query(Material).filter(Material.name == material).first()
            if not cloth_material:
                cloth_material = Material(name=material)
                db.add(cloth_material)
                db.flush()
            material_id = cloth_material.id

            img_material_tags = ImgMaterialTags(
                gen_img_id=result_id,
                material_id=material_id
            )
            db.add(img_material_tags)

    @staticmethod
    async def create_change_pose_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        refer_pic_url: str
    ) -> Dict[str, Any]:
        """创建局部修改任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            original_pic_url: 图片URL
            refer_pic_url: 参考图片URL
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=GenImgType.CHANGE_POSE.value.type,
            variation_type=GenImgType.CHANGE_POSE.value.variationType,
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            refer_pic_url=refer_pic_url,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为1
            image_count = settings.image_generation.change_pose.gen_count
            
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
            
            # 启动异步任务处理改变版型
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_change_pose(result_id)
                )
                
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create change pose task: {str(e)}")
            raise e

    @staticmethod
    async def process_change_pose(result_id: int):
        """处理改变姿态任务
        
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
                
                # 调用改变印花
                result_pic = await adapter.comfy_request_change_pose_redux(
                    original_image_url=task.original_pic_url,
                    pose_reference_image_url=task.refer_pic_url
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
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
                
                logger.info(f"Change pose completed for result {result_id}, task {task.id}")
                credit_value = settings.image_generation.change_pose.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)
                
                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing change pose for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.change_pose.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
                
        except Exception as e:
            logger.error(f"Error processing change pose for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    
    @staticmethod
    async def create_style_fusion_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        refer_pic_url: str
    ) -> Dict[str, Any]:
        """创建风格融合任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            original_pic_url: 图片URL
            refer_pic_url: 参考图片URL
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=GenImgType.STYLE_FUSION.value.type,
            variation_type=GenImgType.STYLE_FUSION.value.variationType,
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            refer_pic_url=refer_pic_url,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为1
            image_count = settings.image_generation.style_fusion.gen_count
            
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
            
            # 启动异步任务处理改变版型
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_style_fusion(result_id)
                )
                
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create change fabric task: {str(e)}")
            raise e

    @staticmethod
    async def process_style_fusion(result_id: int):
        """处理风格融合任务
        
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
                
                # 调用改变印花
                result_pic = await adapter.comfy_request_style_fusion(
                    original_image_url=task.original_pic_url,
                    reference_image_url=task.refer_pic_url
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
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
                
                logger.info(f"Style fusion completed for result {result_id}, task {task.id}")
                credit_value = settings.image_generation.style_fusion.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)
                
                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing style fusion for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.style_fusion.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
                
        except Exception as e:
            logger.error(f"Error processing style fusion for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    async def create_extract_pattern_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        original_mask_url: str
    ) -> Dict[str, Any]:
        """创建印花提取任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            original_pic_url: 图片URL
            mask_pic_url: mask图片URL
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=GenImgType.EXTRACT_PATTERN.value.type,
            variation_type=GenImgType.EXTRACT_PATTERN.value.variationType,
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            mask_pic_url=original_mask_url,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为1
            image_count = settings.image_generation.extract_pattern.gen_count
            
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
            
            # 启动异步任务处理改变版型
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_extract_pattern(result_id)
                )
                
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create extract pattern task: {str(e)}")
            raise e
        
    @staticmethod
    async def process_extract_pattern(result_id: int):
        """处理印花提取任务
        
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
                
                # 调用改变印花
                result_pic = await adapter.comfy_request_extract_pattern(
                    original_image_url=task.original_pic_url,
                    original_mask_url=task.mask_pic_url
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
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
                
                logger.info(f"Extract pattern completed for result {result_id}, task {task.id}")
                credit_value = settings.image_generation.extract_pattern.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)
                
                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing extract pattern for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.extract_pattern.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
                
        except Exception as e:
            logger.error(f"Error processing extract pattern for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    async def create_dress_printing_tryon_task(
        db: Session,
        uid: int,
        original_pic_url: str,
        printing_pic_url: str,
        fabric_pic_url: str
    ) -> Dict[str, Any]:
        """创建印花上身任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            original_pic_url: 图片URL
            printing_pic_url: 印花图片URL
            fabric_pic_url: 面料图片URL
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=GenImgType.DRESS_PRINTING_TRYON.value.type,
            variation_type=GenImgType.DRESS_PRINTING_TRYON.value.variationType,
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            refer_pic_url=printing_pic_url,
            fabric_pic_url=fabric_pic_url,
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为1
            image_count = settings.image_generation.dress_printing_tryon.gen_count
            
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
            
            # 启动异步任务处理改变版型
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_dress_printing_tryon(result_id)
                )
                
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create dress printing tryon task: {str(e)}")
            raise e

    @staticmethod
    async def process_dress_printing_tryon(result_id: int):
        """处理印花上身任务
        
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
                
                # 调用改变印花
                result_pic = await adapter.comfy_request_dress_printing_tryon(
                    original_image_url=task.original_pic_url,
                    printing_image_url=task.refer_pic_url,
                    fabric_image_url=task.fabric_pic_url
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
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
                
                logger.info(f"Dress printing tryon completed for result {result_id}, task {task.id}")
                credit_value = settings.image_generation.dress_printing_tryon.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)
                
                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing dress printing tryon for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.dress_printing_tryon.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
                
        except Exception as e:
            logger.error(f"Error processing dress printing tryon for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    async def create_printing_replacement_task(
        db: Session,
        uid: int,
        original_pic_url: str, 
        printing_pic_url: str,
        x: int, 
        y: int, 
        scale: float, 
        rotate: float,
        remove_printing_background: bool
    ) -> Dict[str, Any]:
        """创建印花摆放任务
        
        Args:
            db: 数据库会话
            uid: 用户ID
            original_pic_url: 图片URL
            printing_pic_url: 印花图片URL
            x: 印花摆放位置x坐标
            y: 印花摆放位置y坐标
            scale: 印花摆放位置缩放比例
            rotate: 印花摆放位置旋转角度
            remove_printing_background: 是否去除印花背景
        Returns:
            任务信息
        """
        # 创建任务记录
        now = datetime.utcnow()
        task = GenImgRecord(
            uid=uid,
            type=GenImgType.PRINTING_REPLACEMENT.value.type,
            variation_type=GenImgType.PRINTING_REPLACEMENT.value.variationType,
            status=1,  # 1-待生成
            original_pic_url=original_pic_url,
            refer_pic_url=printing_pic_url,
            input_param_json={"printing_pic_url": printing_pic_url, "x": x, "y": y, "scale": scale, "rotate": rotate, "remove_printing_background": remove_printing_background},
            create_time=now,
            update_time=now
        )
        
        try:
            # 保存到数据库
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 从配置中获取要创建的结果记录数量，默认为1
            image_count = settings.image_generation.printing_replacement.gen_count
            
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
            
            # 启动异步任务处理改变版型
            for result_id in result_ids:
                asyncio.create_task(
                    ImageService.process_printing_replacement(result_id)
                )
            
            # 返回任务信息
            return {
                "taskId": task.id,
                "status": 1,  # 1-待生成
                "estimatedTime": settings.image_generation.estimated_time_seconds
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create printing replacement task: {str(e)}")
            raise e


    @staticmethod
    async def process_printing_replacement(result_id: int):
        """处理印花摆放任务
        
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
                
                # 调用改变印花
                result_pic = await adapter.comfy_request_printing_replacement(
                    original_image_url=task.original_pic_url,
                    printing_image_url=task.refer_pic_url,
                    x=int(task.input_param_json['x']),
                    y=int(task.input_param_json['y']),
                    scale=float(task.input_param_json['scale']),
                    rotate=float(task.input_param_json['rotate']),
                    remove_printing_background=bool(task.input_param_json['remove_printing_background'])
                )
                
                if not result_pic:
                    raise Exception("No images generated from InfiniAI")
                
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
                
                logger.info(f"Printing replacement completed for result {result_id}, task {task.id}")
                credit_value = settings.image_generation.printing_replacement.use_credit
                await CreditService.real_spend_credit(db, task.uid, credit_value)
                
                task_data = {"genImgId":result.id}
                await rabbitmq_service.send_image_generation_message(task_data)
            except CreditError as e:
                logger.error(f"Failed to spend credit for result {result_id}, task {task.id}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing printing replacement for result {result_id}: {str(e)}")
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

                if result.fail_count >= 3:
                    try:
                        credit_value = settings.image_generation.printing_replacement.use_credit
                        await CreditService.unlock_credit(db, task.uid, credit_value)
                    except:
                        logger.error(f"Failed to unlock credit for result {result_id}, task {task.id}")
                
        except Exception as e:
            logger.error(f"Error processing printing replacement for result {result_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()