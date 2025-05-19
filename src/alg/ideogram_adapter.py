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
            rendering_speed: Optional[str] = "TURBO",
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
            