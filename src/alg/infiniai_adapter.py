import asyncio
from concurrent.futures import ThreadPoolExecutor
import random
import io
import concurrent.futures
import requests
from typing import Union, List, Dict, Any, Optional, Tuple
from PIL import Image

from src.config.log_config import logger
from src.alg.infiniai import InfiniAI
from src.utils.image import download_and_upload_image

class InfiniAIAdapter:
    """InfiniAI适配器类，提供更简洁的接口来使用InfiniAI的功能"""
    _adapter = None

    def __init__(self, api_key: str = None):
        """
        初始化InfiniAI适配器
        
        Args:
            api_key: InfiniAI API密钥，如果不提供则使用配置中的默认值
        """
        self.infiniai = InfiniAI(api_key=api_key)
        logger.info("InfiniAI适配器初始化完成")
    
    @classmethod
    def get_adapter(cls):
        if cls._adapter is None:
            cls._adapter = InfiniAIAdapter()
        return cls._adapter
    
    def _download_image(self, image_url: str) -> Image.Image:
        """
        从URL下载图片并转换为PIL.Image对象
        
        Args:
            image_url: 图片URL
            
        Returns:
            PIL.Image对象
            
        Raises:
            Exception: 下载或转换失败时抛出异常
        """
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content))
        except Exception as e:
            logger.error(f"图片下载失败: {e}")
            raise Exception(f"图片下载失败: {str(e)}")
    
    def _process_images(self, *image_urls: str) -> List[str]:
        """
        处理多个图片URL，下载并上传到InfiniAI OSS
        
        Args:
            *image_urls: 一个或多个图片URL
            
        Returns:
            上传到InfiniAI OSS后的图片ID列表
        """
        oss_image_ids = []
        
        for url in image_urls:
            if not url:
                logger.warning(f"跳过空URL")
                oss_image_ids.append(None)
                continue
                
            try:
                # 下载图片
                image = self._download_image(url)
                
                # 上传到InfiniAI OSS
                image_id = self.infiniai.upload_image_to_infiniai_oss(image)
                
                if not image_id:
                    raise Exception(f"上传图片到OSS失败: {url}")
                
                oss_image_ids.append(image_id)
                logger.info(f"图片处理成功: {url} -> OSS ID: {image_id}")
                
            except Exception as e:
                logger.error(f"图片处理失败: {e}")
                raise Exception(f"图片处理失败: {str(e)}")
        
        return oss_image_ids
    
    async def transfer_style(self, image_a_url: str, image_b_url: str, prompt: str, strength: float = 0.5, 
                      seed: int = None) -> Union[str, List[str]]:
        """
        混合两个图片的风格
        
        Args:
            image_a_url: 图片A的URL
            image_b_url: 图片B的URL
            strength: 混合强度，0为完全保留图片A风格，1为完全采用图片B风格
            seed: 随机种子，不提供则随机生成
            wait_for_result: 是否等待任务完成并返回结果URL，False则只返回任务ID
            
        Returns:
            如果wait_for_result为True，返回生成的图片URL列表
            如果wait_for_result为False，返回任务ID
        """
        try:
            with ThreadPoolExecutor() as executor:
                # 设置随机种子
                if seed is None:
                    seed = random.randint(0, 2147483647)
                
                # 处理图片
                future = executor.submit(
                    self._process_images,
                    image_a_url, image_b_url)
                oss_image_ids = await asyncio.wrap_future(future)
                
                # 调用InfiniAI的混合风格接口
                future2 = executor.submit(
                    self.infiniai.comfy_request_transfer_ab,
                    prompt=prompt,
                    image_a_url=oss_image_ids[0],
                    image_b_url=oss_image_ids[1],
                    strength=strength,
                    seed=seed
                )
                prompt_id = await asyncio.wrap_future(future2)
                
                logger.info(f"风格混合任务已提交，任务ID: {prompt_id}")
                
                future3 = executor.submit(
                        self.infiniai.get_task_result,
                        prompt_id)
                result_urls = await asyncio.wrap_future(future3)
                logger.info(f"风格混合任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(
                        original_url
                    )

                if not oss_image_url:
                    logger.warning(f"Failed to transfer style to OSS, using original URL: {original_url}")
                    return original_url

                # 记录成功结果
                logger.info(f"Successfully transfer style for task result: {oss_image_url}")
                return oss_image_url
        except Exception as e:
            logger.error(f"风格混合失败: {e}")
            raise Exception(f"风格混合失败: {str(e)}")

        
    async def comfy_request_mix_2images(self, original_image_url: str, reference_image_url: str,
                                        mix_weight: float, seed: Optional[int] = None) -> str:
        """
        异步封装 Mix_2images 图像融合

        Args:
            original_image_url: 原始图片URL
            reference_image_url: 参考图片URL
            mix_weight: 融合权重（0-1）
            seed: 随机种子，不传则随机

        Returns:
            生成后的阿里云OSS图片URL
        """
        try:
            with ThreadPoolExecutor() as executor:
                if seed is None:
                    seed = random.randint(0, 2147483647)

                # 将外部URL转为InfiniAI OSS可访问的URL（按既有风格）
                future = executor.submit(self._process_images, original_image_url, reference_image_url)
                oss_image_ids = await asyncio.wrap_future(future)

                # 调用后端算法
                future2 = executor.submit(
                    self.infiniai.comfy_request_mix_2images,
                    original_image_url=oss_image_ids[0],
                    reference_image_url=oss_image_ids[1],
                    mix_weight=mix_weight,
                    seed=seed
                )
                prompt_id = await asyncio.wrap_future(future2)

                # 取结果
                future3 = executor.submit(self.infiniai.get_task_result, prompt_id)
                result_urls = await asyncio.wrap_future(future3)

                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(original_url)
                if not oss_image_url:
                    logger.warning(f"Failed to transfer mix_2images to OSS, using original URL: {original_url}")
                    return original_url

                logger.info(f"Successfully mix_2images result: {oss_image_url}")
                return oss_image_url
        except Exception as e:
            logger.error(f"Error in comfy_request_mix_2images: {e}")
            raise

    async def comfy_request_vary_style_image(self, original_image_url: str, reference_image_url: str,
                                           control_strength: float = 0.8, style_strength: float = 0.5, seed: Optional[int] = None) -> str:
        """
        异步封装风格迁移功能 - 将参考图片的风格应用到原始图片上
        
        Args:
            original_image_url: 原始图片URL
            reference_image_url: 参考图片URL
            control_strength: 原图控制强度，默认0.8
            style_strength: 风格强度（low:0.3, middle:0.5, high:0.9），默认0.5
            seed: 随机种子，不传则随机
            
        Returns:
            生成后的阿里云OSS图片URL
        """
        try:
            with ThreadPoolExecutor() as executor:
                if seed is None:
                    seed = random.randint(0, 2147483647)

                # 将外部URL转为InfiniAI OSS可访问的URL
                future = executor.submit(self._process_images, original_image_url, reference_image_url)
                oss_image_ids = await asyncio.wrap_future(future)

                # 调用后端算法
                future2 = executor.submit(
                    self.infiniai.comfy_request_vary_style_image,
                    original_image_url=oss_image_ids[0],
                    reference_image_url=oss_image_ids[1],
                    control_strength=control_strength,
                    style_strength=style_strength,
                    seed=seed
                )
                prompt_id = await asyncio.wrap_future(future2)

                # 取结果
                future3 = executor.submit(self.infiniai.get_task_result, prompt_id)
                result_urls = await asyncio.wrap_future(future3)

                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(original_url)
                if not oss_image_url:
                    logger.warning(f"Failed to transfer vary_style_image to OSS, using original URL: {original_url}")
                    return original_url

                logger.info(f"Successfully vary_style_image result: {oss_image_url}")
                return oss_image_url
        except Exception as e:
            logger.error(f"Error in comfy_request_vary_style_image: {e}")
            raise
    
    async def transfer_fabric(self, fabric_image_url: str, model_image_url: str, model_mask_url: str = None,
                       seed: int = None) -> Union[str, List[str]]:
        """
        将面料图案应用到服装上
        
        Args:
            fabric_image_url: 面料图案的URL
            model_image_url: 模特图片的URL
            model_mask_url: 模特服装区域蒙版的URL，如果为None则尝试自动生成
            seed: 随机种子，不提供则随机生成
            wait_for_result: 是否等待任务完成并返回结果URL，False则只返回任务ID
            
        Returns:
            如果wait_for_result为True，返回生成的图片URL列表
            如果wait_for_result为False，返回任务ID
        """
        try:
            # 设置随机种子
            if seed is None:
                seed = random.randint(0, 2147483647)
            
            # TODO: 如果没有提供mask_url，可以考虑自动生成蒙版
            if not model_mask_url:
                logger.warning("未提供服装蒙版，这可能会影响结果质量")
                # 在此可以添加自动生成蒙版的逻辑
            
            # 处理图片
            oss_image_ids = self._process_images(fabric_image_url, model_image_url, model_mask_url)
            
            # 调用InfiniAI的面料转换接口
            prompt_id = self.infiniai.comfy_request_transfer_fabric_to_clothes(
                fabric_image_url=oss_image_ids[0],
                model_image_url=oss_image_ids[1],
                model_mask_url=oss_image_ids[2],
                seed=seed
            )
            
            logger.info(f"面料转换任务已提交，任务ID: {prompt_id}")
            
            result_urls = self.infiniai.get_task_result(prompt_id)
            original_url = result_urls[0]

            # 上传到阿里云OSS
            oss_image_url = await download_and_upload_image(
                    original_url
                )

            if not oss_image_url:
                logger.warning(f"Failed to change background to OSS, using original URL: {original_url}")
                return original_url

            # 记录成功结果
            logger.info(f"Successfully change background for task result: {oss_image_url}")
            return oss_image_url
                
        except Exception as e:
            logger.error(f"面料转换失败: {e}")
            raise Exception(f"面料转换失败: {str(e)}")
    
    async def comfy_request_change_background(self, original_image_url: str, reference_image_url: str, background_prompt: str,
                                        seed: Optional[int] = None, refine_size: int = 1536) -> Union[str, List[str]]:
        """
        将面料图案应用到服装上
        
        Args:
            original_image_url: 原始图片的URL
            reference_image_url: 参考图片的URL
            background_prompt: 背景描述
            seed: 随机种子，不提供则随机生成
            refine_size: 放大倍数，默认1536
            
        Returns:
            如果wait_for_result为True，返回生成的图片URL列表
            如果wait_for_result为False，返回任务ID
        """
        try:
            # 设置随机种子
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片
            oss_image_ids = self._process_images(original_image_url, reference_image_url)

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_change_background,
                    original_image_url=oss_image_ids[0],
                    reference_image_url=oss_image_ids[1],
                    background_prompt=background_prompt,
                    seed=seed,
                    refine_size=refine_size
                )

                prompt_id = await asyncio.wrap_future(future)
                logger.info(f"背景转换任务已提交，任务ID: {prompt_id}")

                result_urls = self.infiniai.get_task_result(prompt_id)
                logger.info(f"背景转换任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(
                        original_url
                    )

                if not oss_image_url:
                    logger.warning(f"Failed to change background to OSS, using original URL: {original_url}")
                    return original_url

                # 记录成功结果
                logger.info(f"Successfully change background for task result: {oss_image_url}")
                return oss_image_url
                
        except Exception as e:
            logger.error(f"背景转换失败: {e}")
            raise Exception(f"背景转换失败: {str(e)}")

    async def comfy_request_remove_background(self, original_image_url: str, background_color: str = "transparent") -> Union[str, List[str]]:
        """
        去背景（comfy工作流版本），保持 Replicate 方案不变，仅新增可选工作流
        """
        try:
            # 处理图片
            oss_image_ids = self._process_images(original_image_url)

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_remove_background,
                    original_image_url=oss_image_ids[0],
                    background_color=background_color
                )

                prompt_id = await asyncio.wrap_future(future)
                logger.info(f"去背景任务已提交，任务ID: {prompt_id}")

                result_urls = self.infiniai.get_task_result(prompt_id)
                logger.info(f"去背景任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(original_url)
                if not oss_image_url:
                    logger.warning(f"Failed to remove background to OSS, using original URL: {original_url}")
                    return original_url

                logger.info(f"Successfully remove background for task result: {oss_image_url}")
                return oss_image_url
        except Exception as e:
            logger.error(f"去背景失败: {e}")
            raise Exception(f"去背景失败: {str(e)}")

    async def comfy_request_partial_modify(self, original_image_url: str, original_mask_url: str, prompt: str, seed: Optional[int] = None) -> Union[str, List[str]]:
        """
        局部修改（comfy工作流版本），保留 Ideogram 方案不变，仅新增可选工作流
        """
        try:
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片
            oss_image_ids = self._process_images(original_image_url, original_mask_url)

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_partial_modify,
                    original_image_url=oss_image_ids[0],
                    original_mask_url=oss_image_ids[1],
                    prompt=prompt,
                    seed=seed
                )

                prompt_id = await asyncio.wrap_future(future)
                logger.info(f"局部修改任务已提交，任务ID: {prompt_id}")

                result_urls = self.infiniai.get_task_result(prompt_id)
                logger.info(f"局部修改任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(original_url)
                if not oss_image_url:
                    logger.warning(f"Failed to partial modify to OSS, using original URL: {original_url}")
                    return original_url

                logger.info(f"Successfully partial modify for task result: {oss_image_url}")
                return oss_image_url
        except Exception as e:
            logger.error(f"局部修改失败: {e}")
            raise Exception(f"局部修改失败: {str(e)}")

    async def comfy_request_supir_fix_face(self, original_image_url: str,
                                           strength: float,
                                           upscale_size: int,
                                           face_fix_denoise: float,
                                           seed: Optional[int] = None) -> Union[str, List[str]]:
        """
        SUPIR Fix Face 放大工作流
        """
        try:
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片到 InfiniAI OSS
            oss_image_ids = self._process_images(original_image_url)

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_supir_fix_face,
                    original_image_url=oss_image_ids[0],
                    strength=strength,
                    upscale_size=upscale_size,
                    face_fix_denoise=face_fix_denoise,
                    seed=seed
                )

                prompt_id = await asyncio.wrap_future(future)
                logger.info(f"SUPIR Fix Face 任务已提交，任务ID: {prompt_id}")

                result_urls = self.infiniai.get_task_result(prompt_id)
                logger.info(f"SUPIR Fix Face 任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(original_url)
                if not oss_image_url:
                    logger.warning(f"Failed to SUPIR Fix Face to OSS, using original URL: {original_url}")
                    return original_url

                logger.info(f"Successfully SUPIR Fix Face result: {oss_image_url}")
                return oss_image_url
        except Exception as e:
            logger.error(f"SUPIR Fix Face 失败: {e}")
            raise Exception(f"SUPIR Fix Face 失败: {str(e)}")

    async def comfy_request_pattern_variation(self, original_image_url: str, seed: Optional[int] = None):
        """
        改变图片中的版型
        
        Args:
            original_image_url: 原始图片的URL
            seed: 随机种子，不提供则随机生成
        """
        try:
            # 设置随机种子
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片
            oss_image_ids = self._process_images(original_image_url)

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_pattern_variation,
                    original_image_url=oss_image_ids[0],
                    seed=seed
                )

                pattern_variation_prompt_id = await asyncio.wrap_future(future)
                logger.info(f"版型变化任务已提交，任务ID: {pattern_variation_prompt_id}")

                result_urls = self.infiniai.get_task_result(pattern_variation_prompt_id)
                logger.info(f"版型变化任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(
                        original_url
                    )
                if not oss_image_url:
                    logger.warning(f"Failed to change pattern variation to OSS, using original URL: {original_url}")
                    return original_url

                # 记录成功结果
                logger.info(f"Successfully change pattern variation for task result: {oss_image_url}")
                return oss_image_url
        except Exception as e:
            logger.error(f"改变图片中的版型失败: {e}")
            raise Exception(f"改变图片中的版型失败: {str(e)}")
    
    async def comfy_request_change_fabric(self, model_image_url: str, model_mask_url: str, fabric_image_url: str, seed: Optional[int] = None):
        """
        将面料图案应用到服装上
        
        Args:
            model_image_url: 模特图片的URL
            model_mask_url: 模特服装区域蒙版的URL
            fabric_image_url: 面料图案的URL
            seed: 随机种子，不提供则随机生成
        """
        try:
            # 设置随机种子
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片
            oss_image_ids = self._process_images(model_image_url, model_mask_url, fabric_image_url)
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_change_fabric,
                    original_image_url=oss_image_ids[0],
                    original_mask_url=oss_image_ids[1],
                    fabric_image_url=oss_image_ids[2],
                    seed=seed
                )

                change_fabric_prompt_id = await asyncio.wrap_future(future)
                logger.info(f"面料转换任务已提交，任务ID: {change_fabric_prompt_id}")

                result_urls = self.infiniai.get_task_result(change_fabric_prompt_id)
                logger.info(f"面料转换任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(
                        original_url
                    )
                if not oss_image_url:
                    logger.warning(f"Failed to change fabric to OSS, using original URL: {original_url}")
                    return original_url

                # 记录成功结果
                logger.info(f"Successfully change fabric for task result: {oss_image_url}")
                return oss_image_url
        
        except Exception as e:
            logger.error(f"面料转换失败: {e}")
            raise Exception(f"面料转换失败: {str(e)}")

    async def comfy_request_fabric_replacement(self, original_image_url: str, original_mask_url: str,
                                               fabric_image_url: str, fabric_size: int = 2048, seed: Optional[int] = None):
        """
        面料替换（Fabric Replacement）
        """
        try:
            # 设置随机种子
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片
            oss_image_ids = self._process_images(original_image_url, original_mask_url, fabric_image_url)
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_fabric_replacement,
                    original_image_url=oss_image_ids[0],
                    original_mask_url=oss_image_ids[1],
                    fabric_image_url=oss_image_ids[2],
                    fabric_size=fabric_size,
                    seed=seed
                )

                prompt_id = await asyncio.wrap_future(future)
                logger.info(f"面料替换任务已提交，任务ID: {prompt_id}")

                result_urls = self.infiniai.get_task_result(prompt_id)
                logger.info(f"面料替换任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(original_url)
                if not oss_image_url:
                    logger.warning(f"Failed to fabric replacement to OSS, using original URL: {original_url}")
                    return original_url

                logger.info(f"Successfully fabric replacement for task result: {oss_image_url}")
                return oss_image_url
        
        except Exception as e:
            logger.error(f"面料替换失败: {e}")
            raise Exception(f"面料替换失败: {str(e)}")

    async def comfy_request_change_pose_redux(self, original_image_url: str, pose_reference_image_url: str, seed: Optional[int] = None):
        """
        将面料图案应用到服装上
        
        Args:
            original_image_url: 原始图片的URL
            pose_reference_image_url: 参考图片的URL
            seed: 随机种子，不提供则随机生成
        """
        try:
            # 设置随机种子
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片
            oss_image_ids = self._process_images(original_image_url, pose_reference_image_url)
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_change_pose_redux,
                    original_image_url=oss_image_ids[0],
                    pose_reference_image_url=oss_image_ids[1],
                    seed=seed
                )

                change_pose_prompt_id = await asyncio.wrap_future(future)
                logger.info(f"模特换姿态任务已提交，任务ID: {change_pose_prompt_id}")

                result_urls = self.infiniai.get_task_result(change_pose_prompt_id)
                logger.info(f"模特换姿态任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(
                        original_url
                    )
                if not oss_image_url:
                    logger.warning(f"Failed to change pose to OSS, using original URL: {original_url}")
                    return original_url

                # 记录成功结果
                logger.info(f"Successfully change pose for task result: {oss_image_url}")
                return oss_image_url
        
        except Exception as e:
            logger.error(f"模特换姿态失败: {e}")
            raise Exception(f"模特换姿态失败: {str(e)}")
    
    async def comfy_request_style_fusion(self, original_image_url: str, reference_image_url: str, seed: Optional[int] = None):
        """
        将风格融合到服装上
        
        Args:
            original_image_url: 原始图片的URL
            reference_image_url: 参考图 片的URL
            seed: 随机种子，不提供则随机生成
        """
        try:
            # 设置随机种子
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片
            oss_image_ids = self._process_images(original_image_url, reference_image_url)
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_style_fusion,
                    original_image_url=oss_image_ids[0],
                    reference_image_url=oss_image_ids[1],
                    seed=seed
                )

                style_fusion_prompt_id = await asyncio.wrap_future(future)
                logger.info(f"风格融合任务已提交，任务ID: {style_fusion_prompt_id}")

                result_urls = self.infiniai.get_task_result(style_fusion_prompt_id)
                logger.info(f"风格融合任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(
                        original_url
                    )
                if not oss_image_url:
                    logger.warning(f"Failed to change style fusion to OSS, using original URL: {original_url}")
                    return original_url

                # 记录成功结果
                logger.info(f"Successfully change style fusion for task result: {oss_image_url}")
                return oss_image_url
        
        except Exception as e:
            logger.error(f"风格融合失败: {e}")
            raise Exception(f"风格融合失败: {str(e)}")
    
    async def comfy_request_printing_variation(self, model_image_url: str, seed: Optional[int] = None):
        """
        改变图片中的印花
        
        Args:
            model_image_url: 模特图片的URL
            seed: 随机种子，不提供则随机生成
        """
        try:
            # 设置随机种子
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片
            oss_image_ids = self._process_images(model_image_url)
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_printing_variation,
                    original_image_url=oss_image_ids[0],
                    seed=seed
                    )

                printing_variation_prompt_id = await asyncio.wrap_future(future)
                logger.info(f"印花变化任务已提交，任务ID: {printing_variation_prompt_id}")

                result_urls = self.infiniai.get_task_result(printing_variation_prompt_id)
                logger.info(f"印花变化任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(
                        original_url
                    )
                if not oss_image_url:
                    logger.warning(f"Failed to change printing variation to OSS, using original URL: {original_url}")
                    return original_url

                # 记录成功结果
                logger.info(f"Successfully change printing variation for task result: {oss_image_url}")
                return oss_image_url


        except Exception as e:
            logger.error(f"改变图片中的印花失败: {e}")
            raise Exception(f"改变图片中的印花失败: {str(e)}")
    
    async def comfy_request_extract_pattern(self, original_image_url: str, original_mask_url: str, seed: Optional[int] = None):
        """
        印花提取
        
        Args:
            original_image_url: 原始图片的URL
            original_mask_url: mask的URL
            seed: 随机种子，不提供则随机生成
        """
        try:
            # 设置随机种子
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片
            oss_image_ids = self._process_images(original_image_url, original_mask_url)
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_extract_pattern,
                    original_image_url=oss_image_ids[0],
                    original_mask_url=oss_image_ids[1],
                    seed=seed
                )

                style_fusion_prompt_id = await asyncio.wrap_future(future)
                logger.info(f"印花提取任务已提交，任务ID: {style_fusion_prompt_id}")

                result_urls = self.infiniai.get_task_result(style_fusion_prompt_id)
                logger.info(f"印花提取任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(
                        original_url
                    )
                if not oss_image_url:
                    logger.warning(f"Failed to extract pattern to OSS, using original URL: {original_url}")
                    return original_url

                # 记录成功结果
                logger.info(f"Successfully extract pattern for task result: {oss_image_url}")
                return oss_image_url
        
        except Exception as e:
            logger.error(f"印花提取失败: {e}")
            raise Exception(f"印花提取失败: {str(e)}")
        
    
    async def comfy_request_dress_printing_tryon(self, original_image_url: str, printing_image_url: str, fabric_image_url: str, seed: Optional[int] = None):
        """
        印花上身
        
        Args:
            original_image_url: 原始图片的URL
            printing_image_url: 印花图片的URL
            fabric_image_url: 面料图片的URL
            seed: 随机种子，不提供则随机生成
        """
        try:
            # 设置随机种子
            if seed is None:
                seed = random.randint(0, 2147483647)

            # 处理图片
            oss_image_ids = self._process_images(original_image_url, printing_image_url, fabric_image_url)
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_dress_printing_tryon,
                    original_image_url=oss_image_ids[0],
                    printing_image_url=oss_image_ids[1],
                    fabric_image_url=oss_image_ids[2],
                    seed=seed
                )

                prompt_id = await asyncio.wrap_future(future)
                logger.info(f"印花上身任务已提交，任务ID: {prompt_id}")

                result_urls = self.infiniai.get_task_result(prompt_id)
                logger.info(f"印花上身任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(
                        original_url
                    )
                if not oss_image_url:
                    logger.warning(f"Failed to dress printing tryon to OSS, using original URL: {original_url}")
                    return original_url

                # 记录成功结果
                logger.info(f"Successfully dress printing tryon for task result: {oss_image_url}")
                return oss_image_url
        
        except Exception as e:
            logger.error(f"印花上身失败: {e}")
            raise Exception(f"印花上身失败: {str(e)}")

    async def comfy_request_printing_replacement(self, original_image_url: str, printing_image_url: str,
                                           x: int, y: int, scale: float, rotate: float,
                                           remove_printing_background: bool):
        """
        印花摆放
        
        Args:
            original_image_url: 原始图片的URL
            printing_image_url: 印花图片的URL
            x: - 印花图片的中心点相对于衣服图片的x坐标
            y: - 印花图片的中心点相对于衣服图片的y坐标
            scale: - 印花图片的缩放比例
            rotate: - 印花图片的旋转角度
            remove_printing_background: - 是否去除印花图片的背景
        """
        try:
            # 处理图片
            oss_image_ids = self._process_images(original_image_url, printing_image_url)
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.infiniai.comfy_request_printing_replacement,
                    original_image_url=oss_image_ids[0],
                    printing_image_url=oss_image_ids[1],
                    x=x,
                    y=y,
                    scale=scale,
                    rotate=rotate,
                    remove_printing_background=remove_printing_background
                )

                prompt_id = await asyncio.wrap_future(future)
                logger.info(f"印花摆放任务已提交，任务ID: {prompt_id}")

                result_urls = self.infiniai.get_task_result(prompt_id)
                logger.info(f"印花摆放任务完成，生成了 {len(result_urls)} 张图片")
                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(
                        original_url
                    )
                if not oss_image_url:
                    logger.warning(f"Failed to printing replacement to OSS, using original URL: {original_url}")
                    return original_url

                # 记录成功结果
                logger.info(f"Successfully printing replacement for task result: {oss_image_url}")
                return oss_image_url
        
        except Exception as e:
            logger.error(f"印花摆放失败: {e}")
            raise Exception(f"印花摆放失败: {str(e)}")


    def get_result(self, prompt_id: str) -> List[str]:
        """
        获取任务结果
        
        Args:
            prompt_id: 任务ID
            
        Returns:
            生成的图片URL列表
        """
        try:
            result_urls = self.infiniai.get_task_result(prompt_id)
            logger.info(f"任务 {prompt_id} 完成，生成了 {len(result_urls)} 张图片")
            return result_urls
        except Exception as e:
            logger.error(f"获取任务结果失败: {e}")
            raise Exception(f"获取任务结果失败: {str(e)}")

    async def comfy_request_virtual_tryon_manual(self, model_image_url: str, model_mask_url: str, 
                                               garment_image_url: str, garment_mask_url: str,
                                               model_margin: int, garment_margin: int, 
                                               seed: Optional[int] = None) -> str:
        """
        异步封装虚拟试穿手动版

        Args:
            model_image_url: 模特图片URL
            model_mask_url: 模特遮罩URL
            garment_image_url: 服装图片URL
            garment_mask_url: 服装遮罩URL
            model_margin: 模特边距
            garment_margin: 服装边距
            seed: 随机种子，不传则随机

        Returns:
            生成后的阿里云OSS图片URL
        """
        try:
            with ThreadPoolExecutor() as executor:
                if seed is None:
                    seed = random.randint(0, 2147483647)

                # 将外部URL转为InfiniAI OSS可访问的URL
                future = executor.submit(self._process_images, model_image_url, model_mask_url, garment_image_url, garment_mask_url)
                oss_image_ids = await asyncio.wrap_future(future)

                # 调用后端算法
                future2 = executor.submit(
                    self.infiniai.comfy_request_virtual_tryon_manual,
                    model_image_url=oss_image_ids[0],
                    model_mask_url=oss_image_ids[1],
                    garment_image_url=oss_image_ids[2],
                    garment_mask_url=oss_image_ids[3],
                    model_margin=model_margin,
                    garment_margin=garment_margin,
                    seed=seed
                )
                prompt_id = await asyncio.wrap_future(future2)

                # 取结果
                future3 = executor.submit(self.infiniai.get_task_result, prompt_id)
                result_urls = await asyncio.wrap_future(future3)

                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(original_url)
                if not oss_image_url:
                    logger.warning(f"Failed to transfer virtual_tryon_manual to OSS, using original URL: {original_url}")
                    return original_url

                logger.info(f"Successfully virtual_tryon_manual result: {oss_image_url}")
                return oss_image_url
        except Exception as e:
            logger.error(f"Error in comfy_request_virtual_tryon_manual: {e}")
            raise

    async def comfy_request_extend_image(self, original_image_url: str, top_padding: int, 
                                       right_padding: int, bottom_padding: int, left_padding: int,
                                       seed: Optional[int] = None) -> str:
        """
        异步封装扩图功能

        Args:
            original_image_url: 原始图片URL
            top_padding: 上边距
            right_padding: 右边距
            bottom_padding: 下边距
            left_padding: 左边距
            seed: 随机种子，不传则随机

        Returns:
            生成后的阿里云OSS图片URL
        """
        try:
            with ThreadPoolExecutor() as executor:
                if seed is None:
                    seed = random.randint(0, 2147483647)

                # 将外部URL转为InfiniAI OSS可访问的URL
                future = executor.submit(self._process_images, original_image_url)
                oss_image_ids = await asyncio.wrap_future(future)

                # 调用后端算法
                future2 = executor.submit(
                    self.infiniai.comfy_request_extend_image,
                    original_image_url=oss_image_ids[0],
                    top_padding=top_padding,
                    right_padding=right_padding,
                    bottom_padding=bottom_padding,
                    left_padding=left_padding,
                    seed=seed
                )
                prompt_id = await asyncio.wrap_future(future2)

                # 取结果
                future3 = executor.submit(self.infiniai.get_task_result, prompt_id)
                result_urls = await asyncio.wrap_future(future3)

                original_url = result_urls[0]

                # 上传到阿里云OSS
                oss_image_url = await download_and_upload_image(original_url)
                if not oss_image_url:
                    logger.warning(f"Failed to transfer extend_image to OSS, using original URL: {original_url}")
                    return original_url

                logger.info(f"Successfully extend_image result: {oss_image_url}")
                return oss_image_url
        except Exception as e:
            logger.error(f"Error in comfy_request_extend_image: {e}")
            raise
    


# 示例用法
if __name__ == "__main__":
    # 创建适配器实例
    adapter = InfiniAIAdapter()
    
    # 示例1：混合两个图片的风格
    image_a_url = "https://40e507dd0272b7bb46d376a326e6cb3c.cdn.bubble.io/cdn-cgi/image/w=384,h=,f=auto,dpr=2,fit=contain/f1744616433323x773760165443033100/upscale"
    image_b_url = "https://40e507dd0272b7bb46d376a326e6cb3c.cdn.bubble.io/cdn-cgi/image/w=384,h=,f=auto,dpr=2,fit=contain/f1744612696516x389731609267175230/gGaWt1YY3fgb6aUQrHybE_output.png"
    
    # 将图片B的风格应用到图片A上，强度为0.9
    result_urls = adapter.transfer_style(image_a_url, image_b_url, strength=0.9)
    print(f"风格混合结果: {result_urls[0]}")
    
    # 示例2：将面料图案应用到服装上
    fabric_image_url = "https://cdn.pixabay.com/photo/2016/10/17/13/53/velvet-1747666_640.jpg"
    model_image_url = "https://replicate.delivery/pbxt/JF3LddQgRiMM9Q4Smyfw7q7BR9Gn0PwkSWvJjKDPxyvr8Ru0/cool-dog.png"
    model_mask_url = "https://replicate.delivery/pbxt/JF3Ld3yPLVA3JIELHx1uaAV5CQOyr4AoiOfo6mJZn2fofGaT/dog-mask.png"
    
    # 将面料图案应用到模特服装上
    result_urls = adapter.transfer_fabric(fabric_image_url, model_image_url, model_mask_url)
    print(f"面料转换结果: {result_urls[0]}") 