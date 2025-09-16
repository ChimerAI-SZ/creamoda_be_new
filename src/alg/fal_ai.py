"""
fal.ai API 集成模块
用于与 fal.ai 的 Gemini 2.5 Flash Image API 进行交互
"""

import requests
import json
import asyncio
import concurrent.futures
import time
from typing import Optional, List, Dict, Any
from ..config.config import settings
from ..config.log_config import logger
from ..utils.image import download_and_upload_image

# 创建全局线程池
_global_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)

class FalAiAPI:
    """fal.ai API 客户端"""
    
    def __init__(self):
        self.api_key = settings.fal_ai.api_key
        self.base_url = "https://queue.fal.run"
        self.timeout = settings.fal_ai.timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Key {self.api_key}',
            'Content-Type': 'application/json'
        })

    def submit_image_edit_request(self, image_urls: List[str], prompt: str) -> str:
        """
        提交图像编辑请求到 fal.ai
        
        Args:
            image_urls: 图像URL列表
            prompt: 编辑提示词
            
        Returns:
            请求ID
        """
        url = f"{self.base_url}/fal-ai/gemini-25-flash-image/edit"
        
        data = {
            "image_urls": image_urls,
            "prompt": prompt,
            "num_images": 1,
            "output_format": "jpeg"
        }
        
        start_time = time.time()
        
        try:
            response = self.session.post(url, json=data, timeout=self.timeout)
            
            logger.info(f"fal.ai submit request status: {response.status_code}")
            logger.info(f"fal.ai submit request response: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            return result.get('request_id')
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error submitting to fal.ai: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time
            logger.info(f"fal.ai submit request took {elapsed_time:.2f} seconds")

    def get_request_result(self, request_id: str) -> Dict[str, Any]:
        """
        获取请求结果
        
        Args:
            request_id: 请求ID
            
        Returns:
            结果数据
        """
        url = f"{self.base_url}/fal-ai/gemini-25-flash-image/requests/{request_id}/status"
        
        start_time = time.time()
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            
            logger.info(f"fal.ai get result status: {response.status_code}")
            logger.info(f"fal.ai get result response: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting result from fal.ai: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time
            logger.info(f"fal.ai get result took {elapsed_time:.2f} seconds")

    def wait_for_completion(self, request_id: str, max_wait_time: int = 300) -> Optional[str]:
        """
        等待请求完成并返回结果图像URL
        
        Args:
            request_id: 请求ID
            max_wait_time: 最大等待时间（秒）
            
        Returns:
            生成的图像URL，如果失败则返回None
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                result = self.get_request_result(request_id)
                
                status = result.get('status')
                
                if status == 'COMPLETED':
                    # 状态检查返回COMPLETED时，需要从response_url获取实际结果
                    response_url = result.get('response_url')
                    if response_url:
                        # 从response_url获取实际结果
                        response = self.session.get(response_url, timeout=self.timeout)
                        response.raise_for_status()
                        actual_result = response.json()
                        
                        # 提取图像URL
                        images = actual_result.get('images', [])
                        if images and len(images) > 0:
                            return images[0].get('url')
                    
                    logger.error("No images in completed result")
                    return None
                        
                elif status == 'FAILED':
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"fal.ai request failed: {error_msg}")
                    return None
                    
                elif status in ['QUEUED', 'IN_PROGRESS']:
                    logger.info(f"Request {request_id} status: {status}")
                    time.sleep(5)  # 等待5秒后重试
                    continue
                else:
                    logger.warning(f"Unknown status: {status}")
                    time.sleep(5)
                    
            except Exception as e:
                logger.error(f"Error checking request status: {str(e)}")
                time.sleep(5)
        
        logger.error(f"Request {request_id} timed out after {max_wait_time} seconds")
        return None

    def sketch_to_design_with_reference(self, sketch_url: str, prompt: str, reference_urls: Optional[List[str]] = None) -> str:
        """
        使用参考图进行手绘转设计
        
        Args:
            sketch_url: 原始手绘图URL
            prompt: 设计提示词
            reference_urls: 参考图URL列表（可选）
            
        Returns:
            生成的设计图URL
        """
        # 构建输入图像列表
        image_urls = [sketch_url]
        if reference_urls:
            image_urls.extend(reference_urls)
            
        # 提交请求
        request_id = self.submit_image_edit_request(image_urls, prompt)
        
        if not request_id:
            raise Exception("Failed to submit request to fal.ai")
        
        # 等待完成并返回结果
        result_url = self.wait_for_completion(request_id)
        
        if not result_url:
            raise Exception("Failed to get result from fal.ai")
            
        return result_url

class FalAiService:
    """fal.ai 服务封装类，用于异步调用"""
    
    def __init__(self):
        self.api = FalAiAPI()

    async def create_sketch_to_design_with_reference(
        self,
        sketch_url: str,
        prompt: str,
        reference_image_url: Optional[str] = None,
        result_id: str = None
    ) -> str:
        """
        异步手绘转设计（带参考图）
        
        Args:
            sketch_url: 原始手绘图URL
            prompt: 设计提示词
            reference_image_url: 参考图URL（可选）
            result_id: 生成任务结果ID
            
        Returns:
            生成的设计图URL
        """
        logger.info(f"Starting sketch to design with fal.ai for result {result_id}")
        logger.info(f"Parameters: sketch_url='{sketch_url}', prompt='{prompt}', reference_image_url='{reference_image_url}'")
        
        try:
            # 构建参考图列表
            reference_urls = [reference_image_url] if reference_image_url else None
            
            # 使用线程池执行同步请求
            future = _global_thread_pool.submit(
                self.api.sketch_to_design_with_reference,
                sketch_url,
                prompt,
                reference_urls
            )
            
            result_url = await asyncio.wait_for(
                asyncio.wrap_future(future),
                timeout=620
            )
            
            # 将第三方图片URL转存到阿里云OSS
            oss_image_url = await download_and_upload_image(
                result_url,
                f"fal_ai_sketch_{result_id}"
            )
            
            if not oss_image_url:
                logger.warning(f"Failed to transfer image to OSS, using original URL: {result_url}")
                return result_url
            
            logger.info(f"Successfully generated design with fal.ai for result {result_id}: {oss_image_url}")
            return oss_image_url
            
        except Exception as e:
            logger.error(f"Error in fal.ai sketch to design for result {result_id}: {str(e)}")
            raise

    async def create_change_color(
        self,
        image_url: str,
        clothing_text: str,
        hex_color: str,
        result_id: str = None
    ) -> str:
        """
        异步改变颜色功能
        
        Args:
            image_url: 原始图片URL
            clothing_text: 要改变颜色的服装描述
            hex_color: 十六进制颜色代码
            result_id: 生成任务结果ID
            
        Returns:
            生成的图片URL
        """
        logger.info(f"Starting change color with fal.ai for result {result_id}")
        logger.info(f"Parameters: image_url='{image_url}', clothing_text='{clothing_text}', hex_color='{hex_color}'")
        
        try:
            # 构建prompt，按照要求的格式：Change the color of {文本框内容} to {色值}
            prompt = f"Change the color of {clothing_text} to {hex_color}"
            
            # 使用线程池执行同步请求
            future = _global_thread_pool.submit(
                self.api.sketch_to_design_with_reference,
                image_url,
                prompt,
                None  # 颜色改变不需要参考图
            )
            
            result_url = await asyncio.wait_for(
                asyncio.wrap_future(future),
                timeout=620
            )
            
            # 将第三方图片URL转存到阿里云OSS
            oss_image_url = await download_and_upload_image(
                result_url,
                f"fal_ai_color_{result_id}"
            )
            
            if not oss_image_url:
                logger.warning(f"Failed to transfer image to OSS, using original URL: {result_url}")
                return result_url
            
            logger.info(f"Successfully changed color with fal.ai for result {result_id}: {oss_image_url}")
            return oss_image_url
            
        except Exception as e:
            logger.error(f"Error in fal.ai change color for result {result_id}: {str(e)}")
            raise
