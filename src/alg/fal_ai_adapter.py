"""
fal.ai API 适配器
用于调用 fal.ai 的 Gemini 2.5 Flash Image API
"""
import asyncio
import httpx
import json
import logging
from typing import Dict, List, Any, Optional
from ..config.config import settings
from ..utils.image import download_and_upload_image

logger = logging.getLogger(__name__)

class FalAIAdapter:
    """fal.ai API 适配器类"""
    
    def __init__(self):
        self.base_url = "https://fal.run/fal-ai"
        self.api_key = settings.fal_ai.api_key if hasattr(settings, 'fal_ai') else None
        self.timeout = 300  # 5分钟超时
        
    async def fabric_to_design(
        self, 
        fabric_image_url: str, 
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用 fal.ai Gemini 2.5 Flash Image API 进行面料转设计
        
        Args:
            fabric_image_url: 面料图片URL
            prompt: 用户提示词，可选
            
        Returns:
            包含生成结果的字典
        """
        try:
            # 如果没有提供提示词，使用默认提示词
            if not prompt or prompt.strip() == "":
                prompt = "generate a fashion design using the fabric in the image"
            
            # 构建请求数据
            request_data = {
                "prompt": prompt,
                "image_urls": [fabric_image_url],
                "num_images": 1,
                "output_format": "jpeg"
            }
            
            logger.info(f"Calling fal.ai fabric to design API with prompt: {prompt}")
            logger.info(f"Fabric image URL: {fabric_image_url}")
            
            # 调用 fal.ai API
            result = await self._call_fal_api("gemini-25-flash-image/edit", request_data)
            
            logger.info(f"fal.ai API response: {result}")
            
            # 处理响应
            if result and "images" in result and len(result["images"]) > 0:
                image_info = result["images"][0]
                original_url = image_info.get("url")
                
                # 下载生成的图片并上传到OSS
                oss_url = await download_and_upload_image(original_url, "fabric_to_design")
                
                return {
                    "success": True,
                    "image_url": oss_url if oss_url else original_url,
                    "description": result.get("description", ""),
                    "raw_response": result
                }
            else:
                logger.error("fal.ai API returned invalid response format")
                return {
                    "success": False,
                    "error": "Invalid response format from fal.ai API",
                    "raw_response": result
                }
                
        except Exception as e:
            logger.error(f"Error calling fal.ai fabric to design API: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _call_fal_api(self, model_path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 fal.ai API 的通用方法
        
        Args:
            model_path: 模型路径，如 "gemini-25-flash-image/edit"
            data: 请求数据
            
        Returns:
            API响应结果
        """
        if not self.api_key:
            raise ValueError("fal.ai API key not configured")
        
        url = f"{self.base_url}/{model_path}"
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 提交任务
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            # 如果是异步任务，需要轮询结果
            if "request_id" in result:
                return await self._poll_result(model_path, result["request_id"])
            else:
                # 同步返回结果
                return result
    
    async def _poll_result(self, model_path: str, request_id: str) -> Dict[str, Any]:
        """
        轮询异步任务结果
        
        Args:
            model_path: 模型路径
            request_id: 请求ID
            
        Returns:
            最终结果
        """
        status_url = f"{self.base_url}/{model_path}/requests/{request_id}/status"
        result_url = f"{self.base_url}/{model_path}/requests/{request_id}"
        
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        max_attempts = 60  # 最多轮询60次（5分钟）
        attempt = 0
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while attempt < max_attempts:
                try:
                    # 检查任务状态
                    status_response = await client.get(status_url, headers=headers)
                    status_response.raise_for_status()
                    status_data = status_response.json()
                    
                    logger.info(f"fal.ai task status: {status_data.get('status', 'unknown')}")
                    
                    if status_data.get("status") == "COMPLETED":
                        # 获取结果
                        result_response = await client.get(result_url, headers=headers)
                        result_response.raise_for_status()
                        return result_response.json()
                    
                    elif status_data.get("status") in ["FAILED", "CANCELLED"]:
                        raise Exception(f"fal.ai task failed with status: {status_data.get('status')}")
                    
                    # 等待5秒后重试
                    await asyncio.sleep(5)
                    attempt += 1
                    
                except Exception as e:
                    logger.error(f"Error polling fal.ai task status: {str(e)}")
                    if attempt >= max_attempts - 1:
                        raise
                    await asyncio.sleep(5)
                    attempt += 1
        
        raise Exception("fal.ai task timed out after maximum attempts")
    
    async def change_clothes(
        self, 
        image_url: str, 
        prompt: str
    ) -> Dict[str, Any]:
        """
        使用 fal.ai Gemini 2.5 Flash Image API 进行换装
        
        Args:
            image_url: 原始图片URL
            prompt: 换装描述
            
        Returns:
            包含生成结果的字典
        """
        try:
            # 构建请求数据
            request_data = {
                "prompt": prompt,
                "image_urls": [image_url],
                "num_images": 1,
                "output_format": "jpeg"
            }
            
            logger.info(f"Calling fal.ai change clothes API with prompt: {prompt}")
            logger.info(f"Original image URL: {image_url}")
            
            # 调用 fal.ai API
            result = await self._call_fal_api("gemini-25-flash-image/edit", request_data)
            
            logger.info(f"fal.ai API response: {result}")
            
            # 处理响应
            if result and "images" in result and len(result["images"]) > 0:
                image_info = result["images"][0]
                original_url = image_info.get("url")
                
                # 下载生成的图片并上传到OSS
                oss_url = await download_and_upload_image(original_url, "change_clothes")
                
                return {
                    "success": True,
                    "image_url": oss_url if oss_url else original_url,
                    "description": result.get("description", ""),
                    "raw_response": result
                }
            else:
                logger.error("fal.ai API returned invalid response format")
                return {
                    "success": False,
                    "error": "Invalid response format from fal.ai API",
                    "raw_response": result
                }
                
        except Exception as e:
            logger.error(f"Error calling fal.ai change clothes API: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def extract_pattern(
        self, 
        image_url: str, 
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用 fal.ai Gemini 2.5 Flash Image API 进行印花提取
        
        Args:
            image_url: 原始图片URL
            prompt: 提取提示词，可选，默认为 "Generate a seamless pattern from the clothing, keeping the original scale and spacing of only the print"
            
        Returns:
            包含生成结果的字典
        """
        try:
            # 如果没有提供提示词，使用默认提示词
            if not prompt or prompt.strip() == "":
                prompt = "Generate a seamless pattern from the clothing, keeping the original scale and spacing of only the print"
            
            # 构建请求数据
            request_data = {
                "prompt": prompt,
                "image_urls": [image_url],
                "num_images": 1,
                "output_format": "jpeg"
            }
            
            logger.info(f"Calling fal.ai pattern extraction API with prompt: {prompt}")
            logger.info(f"Original image URL: {image_url}")
            
            # 调用 fal.ai API
            result = await self._call_fal_api("gemini-25-flash-image/edit", request_data)
            
            logger.info(f"fal.ai API response: {result}")
            
            # 处理响应
            if result and "images" in result and len(result["images"]) > 0:
                image_info = result["images"][0]
                original_url = image_info.get("url")
                
                # 下载生成的图片并上传到OSS
                oss_url = await download_and_upload_image(original_url, "pattern_extraction")
                
                return {
                    "success": True,
                    "image_url": oss_url if oss_url else original_url,
                    "description": result.get("description", ""),
                    "raw_response": result
                }
            else:
                logger.error("fal.ai API returned invalid response format")
                return {
                    "success": False,
                    "error": "Invalid response format from fal.ai API",
                    "raw_response": result
                }
                
        except Exception as e:
            logger.error(f"Error calling fal.ai pattern extraction API: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def apply_pattern_to_design(
        self, 
        original_image_url: str,
        pattern_image_url: str,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用 fal.ai Gemini 2.5 Flash Image API 将印花应用到服装设计上
        
        Args:
            original_image_url: 原始服装图片URL
            pattern_image_url: 印花图案URL
            prompt: 应用提示词，可选，默认为 "Apply this pattern consistently across the full outfit (both top and bottom), keeping the garment design, original proportions and spacing of the print intact."
            
        Returns:
            包含生成结果的字典
        """
        try:
            # 如果没有提供提示词，使用默认提示词
            if not prompt or prompt.strip() == "":
                prompt = "Apply this pattern consistently across the full outfit (both top and bottom), keeping the garment design, original proportions and spacing of the print intact."
            
            # 构建请求数据 - 将原始图片和印花图片都作为输入
            request_data = {
                "prompt": prompt,
                "image_urls": [original_image_url, pattern_image_url],
                "num_images": 1,
                "output_format": "jpeg"
            }
            
            logger.info(f"Calling fal.ai pattern application API with prompt: {prompt}")
            logger.info(f"Original image URL: {original_image_url}")
            logger.info(f"Pattern image URL: {pattern_image_url}")
            
            # 调用 fal.ai API
            result = await self._call_fal_api("gemini-25-flash-image/edit", request_data)
            
            logger.info(f"fal.ai API response: {result}")
            
            # 处理响应
            if result and "images" in result and len(result["images"]) > 0:
                image_info = result["images"][0]
                original_url = image_info.get("url")
                
                # 下载生成的图片并上传到OSS
                oss_url = await download_and_upload_image(original_url, "pattern_application")
                
                return {
                    "success": True,
                    "image_url": oss_url if oss_url else original_url,
                    "description": result.get("description", ""),
                    "raw_response": result
                }
            else:
                logger.error("fal.ai API returned invalid response format")
                return {
                    "success": False,
                    "error": "Invalid response format from fal.ai API",
                    "raw_response": result
                }
                
        except Exception as e:
            logger.error(f"Error calling fal.ai pattern application API: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }