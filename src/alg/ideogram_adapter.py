import asyncio
from typing import Optional, List, Union, IO
import concurrent.futures

from src.config.log_config import logger
from src.alg.ideogram import Ideogram
from src.dto.upload_file import MockUploadFile
from src.utils.image import download_and_upload_image

class IdeogramAdapter:
    """Ideogram适配器类，提供更简洁的接口来使用Ideogram的功能"""
    _adapter = None

    def __init__(self, api_key: str = None):
        """
        初始化Ideogram适配器
        
        Args:
            api_key: InfiniAI API密钥，如果不提供则使用配置中的默认值
        """
        self.ideogram = Ideogram(api_key=api_key)
        logger.info("Ideogram适配器初始化完成")
    
    @classmethod
    def get_adapter(cls):
        if cls._adapter is None:
            cls._adapter = IdeogramAdapter()
        return cls._adapter
    
    async def edit(
            self,
            image: Union[str, IO],
            mask: Union[str, IO],
            prompt: str,
            magic_prompt: Optional[str] = "ON",
            num_images: Optional[int] = 1,
            seed: Optional[int] = None,
            rendering_speed: Optional[str] = "QUALITY",
            color_palette: Optional[dict] = None,
            style_codes: Optional[List[str]] = None,
            style_reference_images: Optional[List[Union[str, IO]]] = None,
            is_white_mask: Optional[bool] = True
    ) -> str:
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future = executor.submit(
                self.ideogram.edit,
                image=image,
                mask=mask,
                prompt=prompt,
                magic_prompt=magic_prompt,
                num_images=num_images,
                seed=seed,
                rendering_speed=rendering_speed,
                color_palette=color_palette,
                style_codes=style_codes,
                style_reference_images=style_reference_images,
                is_white_mask=is_white_mask
            )
            
            res_dict = await asyncio.wrap_future(future)
            original_url = res_dict['data'][0]['url']
        
            # 上传到阿里云OSS
            oss_image_url = await download_and_upload_image(
                    original_url
                )

            if not oss_image_url:
                logger.warning(f"Failed to transfer image to OSS, using original URL: {original_url}")
                return original_url

            # 记录成功结果
            logger.info(f"Successfully edit cloth for task result: {oss_image_url}")
            return oss_image_url

    async def generate(
            self,
            prompt: str,
            seed: Optional[int] = None,
            resolution: Optional[str] = None,
            aspect_ratio: Optional[str] = None,
            rendering_speed: Optional[str] = "QUALITY",
            magic_prompt: Optional[str] = "AUTO",
            negative_prompt: Optional[str] = None,
            num_images: Optional[int] = 1,
            color_palette: Optional[dict] = None,
            style_codes: Optional[List[str]] = None,
            style_type: Optional[str] = "GENERAL",
            style_reference_images: Optional[List[Union[str, IO]]] = None,
            character_reference_images: Optional[List[Union[str, IO]]] = None,
            character_reference_images_mask: Optional[List[Union[str, IO]]] = None
    ) -> List[str]:
        """
        异步生成图像
        
        Args:
            prompt: 生成图像的提示词
            seed: 随机种子
            resolution: 图像分辨率
            aspect_ratio: 图像宽高比
            rendering_speed: 渲染速度
            magic_prompt: 是否使用MagicPrompt
            negative_prompt: 负面提示词
            num_images: 生成图像数量
            color_palette: 颜色调色板
            style_codes: 风格代码列表
            style_type: 风格类型
            style_reference_images: 风格参考图像
            character_reference_images: 角色参考图像
            character_reference_images_mask: 角色参考图像遮罩
        
        Returns:
            生成的图像URL列表
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future = executor.submit(
                self.ideogram.generate,
                prompt=prompt,
                seed=seed,
                resolution=resolution,
                aspect_ratio=aspect_ratio,
                rendering_speed=rendering_speed,
                magic_prompt=magic_prompt,
                negative_prompt=negative_prompt,
                num_images=num_images,
                color_palette=color_palette,
                style_codes=style_codes,
                style_type=style_type,
                style_reference_images=style_reference_images,
                character_reference_images=character_reference_images,
                character_reference_images_mask=character_reference_images_mask
            )
            
            res_dict = await asyncio.wrap_future(future)
            
            # 提取图像URL列表并上传到阿里云OSS
            oss_image_urls = []
            if res_dict and "data" in res_dict:
                for item in res_dict["data"]:
                    if "url" in item:
                        original_url = item["url"]
                        # 上传到阿里云OSS
                        oss_image_url = await download_and_upload_image(original_url)
                        if oss_image_url:
                            oss_image_urls.append(oss_image_url)
                        else:
                            logger.warning(f"Failed to transfer image to OSS, using original URL: {original_url}")
                            oss_image_urls.append(original_url)
            
            logger.info(f"Successfully generated {len(oss_image_urls)} images")
            return oss_image_urls
            