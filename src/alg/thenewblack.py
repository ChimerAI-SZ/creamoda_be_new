import asyncio
import concurrent.futures
import time
from enum import Enum
from typing import Optional

import requests

from src.config.config import settings
from src.config.log_config import logger
from src.utils.image import download_and_upload_image  # 导入图片转存工具


class Gender(Enum):
    MAN = 'man'
    WOMAN = 'woman'


class BodyType(Enum):
    SMALL = 'small'
    PLUS = 'plus'
    PREGNANT = 'pregnant'
    MID_SIZE = ''


class ClothingType(Enum):
    TOPS = 'tops'
    BOTTOMS = 'bottoms'
    ONE_PIECES = 'one-pieces'


class TheNewBlackAPI:
    def __init__(self, email: str = None, password: str = None, timeout: int = 300):
        """
        Initializes the TheNewBlackAPI instance with email and password.

        :param email: User's email address
        :param password: User's password
        :param timeout: HTTP request timeout in seconds, default is 5 minutes (300 seconds)
        """
        self.email = email or settings.algorithm.thenewblack_email
        self.password = password or settings.algorithm.thenewblack_password
        self.base_url = "https://thenewblack.ai/api/1.1/wf"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (self.email, self.password)

    def create_clothing(self, outfit: str, gender: Gender, country: str, age: int, width: int, height: int,
                        body_type: BodyType = BodyType.MID_SIZE, background: str = 'no background', negative: str = None) -> str:
        """
        Creates a fashion outfit design given a prompt.

        :param outfit: Describe the clothing outfit (required)
        :param gender: Enter value 'man' or 'woman' only (required, use Gender enum)
        :param country: Enter a country name (ex: 'Italy') (required)
        :param age: Age of the model. Number only (required)
        :param width: Image width. Image width x Image height cannot be superior to 2359296 pixels (required)
        :param height: Image height. Image width x Image height cannot be superior to 2359296 pixels (required)
        :param body_type: Accepted value 'small', 'plus', 'pregnant'. If empty, will be mid-size by default (optional, use BodyType enum)
        :param background: Describe a background. For example: 'NYC street' (optional)
        :param negative: Describe what you DON´T want in the design (optional)
        :return: Response from the API as a URL to the generated image
        """
        url = f"{self.base_url}/clothing"
        data = {
            "email": self.email,
            "password": self.password,
            "outfit": outfit,
            "gender": gender.value,  # Use the value of the Gender enum
            "country": country,
            "age": age,
            "width": width,
            "height": height,
            "body_type": body_type.value,
        }
        if background:
            data["background"] = background
        if negative:
            data["negative"] = negative

        logger.info(f"Sending request to TheNewBlack API for clothing generation")
        start_time = time.time()  # 记录开始时间
        
        try:
            response = self.session.post(url, data=data, timeout=self.timeout)
            
            # 记录响应内容
            logger.info(f"TheNewBlack API response status: {response.status_code}")
            logger.info(f"TheNewBlack API response content: {response.text}")
            
            response.raise_for_status()  # 抛出HTTP错误状态码异常
            logger.info(f"Successfully received response from TheNewBlack API")
            return response.text  # response is a URL to the generated image
        except requests.exceptions.Timeout:
            logger.error(f"Request to TheNewBlack API timed out after {self.timeout} seconds")
            raise TimeoutError(f"Request timed out after {self.timeout} seconds")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling TheNewBlack API: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time  # 计算请求用时
            logger.info(f"TheNewBlack create_clothing API request took {elapsed_time:.2f} seconds")

    def get_credit_balance(self) -> float:
        """
        Retrieves the current credit balance of the account.

        :return: The credit balance as an integer
        """
        url = f"{self.base_url}/credits"
        data = {
            "email": self.email,
            "password": self.password,
        }

        start_time = time.time()  # 记录开始时间
        
        try:
            response = self.session.post(url, data=data, timeout=self.timeout)
            
            # 记录响应内容
            logger.info(f"TheNewBlack API credit balance response status: {response.status_code}")
            logger.info(f"TheNewBlack API credit balance response content: {response.text}")
            
            response.raise_for_status()
            return float(response.text)  # response is the credit balance as an float
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"Error getting credit balance: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time  # 计算请求用时
            logger.info(f"TheNewBlack get_credit_balance API request took {elapsed_time:.2f} seconds")

    def change_clothes(self, image_url: str, remove: str, replace: str, negative: str = None) -> str:
        """
        Modifies an image by removing and replacing clothing based on the provided descriptions.

        :param image_url: URL of the original image (required)
        :param remove: Describe what to remove in the image (required)
        :param replace: Describe what you want instead (required)
        :param negative: Describe what you DON´T want in the design (optional)
        :return: Response from the API as a URL to the modified image
        """
        url = f"{self.base_url}/edit"
        data = {
            "email": self.email,
            "password": self.password,
            "image": image_url,
            "remove": remove,
            "replace": replace,
            "negative": "Background pattern, poor details"
        }
        if negative:
            data["negative"] = negative

        start_time = time.time()  # 记录开始时间
        
        try:
            response = self.session.post(url, data=data, timeout=self.timeout)
            
            # 记录响应内容
            logger.info(f"TheNewBlack API change clothes response status: {response.status_code}")
            logger.info(f"TheNewBlack API change clothes response content: {response.text}")
            
            response.raise_for_status()
            return response.text  # response is a URL to the modified image
        except requests.exceptions.RequestException as e:
            logger.error(f"Error changing clothes: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time  # 计算请求用时
            logger.info(f"TheNewBlack change_clothes API request took {elapsed_time:.2f} seconds")

    def create_variation(self, image_url: str, prompt: str, deviation: float = 1.0) -> str:
        """
        Creates a variation of the provided image based on the given prompt and deviation.

        :param image_url: URL of the original image (required)
        :param prompt: Describe the new variation (required)
        :param deviation: Value between 0 and 1 (1 means the original image is 100% modified) (optional, default is 1.0)
        :return: Response from the API as a URL to the variation image
        """
        url = f"{self.base_url}/variation"
        data = {
            "email": self.email,
            "password": self.password,
            "image": image_url,
            "prompt": prompt,
            "deviation": str(deviation),  # Convert to string as required by the API
        }

        start_time = time.time()  # 记录开始时间
        
        try:
            response = self.session.post(url, data=data, timeout=self.timeout)
            
            # 记录响应内容
            logger.info(f"TheNewBlack API create variation response status: {response.status_code}")
            logger.info(f"TheNewBlack API create variation response content: {response.text}")
            
            response.raise_for_status()
            return response.text  # response is a URL to the variation image
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating variation: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time  # 计算请求用时
            logger.info(f"TheNewBlack create_variation API request took {elapsed_time:.2f} seconds")

    def create_clothing_with_fabric(self, fabric_image_url: str, clothing_prompt: str, gender: Gender,
                                    country: str, age: int) -> str:
        """
        Creates a clothing design from a fabric pattern image.

        :param fabric_image_url: URL of the fabric image (required)
        :param clothing_prompt: Description of the clothing piece with the fabric pattern (required)
        :param gender: Gender of the model (required, use Gender enum)
        :param country: Name of the country for the model (required)
        :param age: Age of the model, between 20 and 70 (required)
        :return: Response from the API as a URL to the generated image
        """
        url = f"{self.base_url}/fabric_to_design"
        data = {
            "email": self.email,
            "password": self.password,
            "fabric_image": fabric_image_url,
            "clothing_prompt": clothing_prompt,
        }

        if gender is not None:
            data["gender"] = gender.value
        if country is not None:
            data["country"] = country
        if age is not None:
            data["age"] = str(age)

        start_time = time.time()  # 记录开始时间

        try:
            response = self.session.post(url, data=data, timeout=self.timeout)

            # 记录响应内容
            logger.info(f"TheNewBlack API fabric to design response status: {response.status_code}")
            logger.info(f"TheNewBlack API fabric to design response content: {response.text}")

            response.raise_for_status()
            return response.text  # response is a URL to the generated image
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating clothing with fabric: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time  # 计算请求用时
            logger.info(f"TheNewBlack create_clothing_with_fabric API request took {elapsed_time:.2f} seconds")

    def start_virtual_try_on(self, model_image_url: str, clothing_image_url: str, clothing_type: ClothingType) -> str:
        """
        Initiates a virtual try-on process.

        :param model_image_url: URL of the model image (required)
        :param clothing_image_url: URL of the clothing image (required)
        :param clothing_type: Type of clothing (required)
        :return: Job ID for retrieving the result
        """
        url = f"{self.base_url}/vto"
        data = {
            "email": self.email,
            "password": self.password,
            "model_photo": model_image_url,
            "clothing_photo": clothing_image_url,
            "clothing_type": clothing_type.value,
        }

        logger.info(f"Sending request to TheNewBlack API for virtual try-on")
        start_time = time.time()  # 记录开始时间

        try:
            response = self.session.post(url, data=data, timeout=self.timeout)

            # 记录响应内容
            logger.info(f"TheNewBlack API virtual try-on response status: {response.status_code}")
            logger.info(f"TheNewBlack API virtual try-on response content: {response.text}")

            response.raise_for_status()
            return response.text  # response is a job ID
        except requests.exceptions.RequestException as e:
            logger.error(f"Error initiating virtual try-on: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time
            logger.info(f"TheNewBlack virtual_try_on API request took {elapsed_time:.2f} seconds")

    def get_results(self, job_id: str) -> str | None:
        """
        Retrieves the result of a previously submitted job.

        :param job_id: Job ID returned from a previous API call
        :return: The result URL or None if the job is still processing
        """
        url = f"{self.base_url}/results"
        data = {
            "email": self.email,
            "password": self.password,
            "id": job_id,
        }

        logger.info(f"Retrieving results for job ID {job_id}")
        start_time = time.time()

        try:
            response = self.session.post(url, data=data, timeout=self.timeout)

            # 记录响应内容
            logger.info(f"TheNewBlack API results response status: {response.status_code}")
            logger.info(f"TheNewBlack API results response content: {response.text}")

            response.raise_for_status()
            if response.text == "Processing...":  # 处理中的状态
                return None
            return response.text  # response is a URL to the generated image
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving results: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time
            logger.info(f"TheNewBlack get_results API request took {elapsed_time:.2f} seconds")

    def start_generate_ai_model(
            self,
            clothing_photo_url: str,
            clothing_type: ClothingType,
            gender: Gender,
            country: str,
            age: int,
            other_clothes: str,
            image_context: str,
            width: int,
            height: int
    ) -> str:
        """
        Creates an AI generated model from a clothing photo.
        This is an asynchronous operation that returns a job ID for later retrieval.

        :param clothing_photo_url: URL of the clothing image (required)
        :param clothing_type: Type of clothing (tops, bottoms, one-pieces) (required)
        :param gender: Gender of the model (required)
        :param country: Name of the country for the model (required)
        :param age: Age of the model, between 20 and 70 (required)
        :param other_clothes: Description of other clothes besides the main one (required)
        :param image_context: Description of the background and context (required)
        :param width: Width of the output image (required)
        :param height: Height of the output image (required)
        :return: Job ID for retrieving the result
        """
        url = f"{self.base_url}/generated-models"
        data = {
            "email": self.email,
            "password": self.password,
            "clothing_photo": clothing_photo_url,
            "clothing_type": clothing_type.value,
            "gender": gender.value,
            "country": country,
            "age": str(age),
            "other_clothes": other_clothes,
            "image_context": image_context,
            "width": str(width),
            "height": str(height),
        }

        logger.info(f"Sending request to TheNewBlack API for AI model generation")
        start_time = time.time()  # 记录开始时间

        try:
            response = self.session.post(url, data=data, timeout=self.timeout)

            # 记录响应内容
            logger.info(f"TheNewBlack API AI model generation response status: {response.status_code}")
            logger.info(f"TheNewBlack API AI model generation response content: {response.text}")

            response.raise_for_status()
            return response.text  # response is a job ID
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating AI model: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time
            logger.info(f"TheNewBlack generate_ai_model API request took {elapsed_time:.2f} seconds")

    def change_model(self, image_url: str, model: str) -> str:
        """
        Creates the same photo by only changing the model.

        :param image_url: URL of the original image (required)
        :param model: Description of the new model (required)
        :return: Response from the API as a URL to the modified image
        """
        url = f"{self.base_url}/change_model"
        data = {
            "email": self.email,
            "password": self.password,
            "image": image_url,
            "model": model,
        }

        start_time = time.time()  # 记录开始时间

        try:
            response = self.session.post(url, data=data, timeout=self.timeout)

            # 记录响应内容
            logger.info(f"TheNewBlack API change model response status: {response.status_code}")
            logger.info(f"TheNewBlack API change model response content: {response.text}")

            response.raise_for_status()
            return response.text  # response is a URL to the modified image
        except requests.exceptions.RequestException as e:
            logger.error(f"Error changing model: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time  # 计算请求用时
            logger.info(f"TheNewBlack change_model API request took {elapsed_time:.2f} seconds")

    def sketch_to_design(self, sketch_url: str, prompt: str) -> str:
        """
        Creates a real clothing design from a sketch.

        :param sketch_url: URL of the original sketch/image (required)
        :param prompt: Describe the final design (required)
        :return: Response from the API as a URL to the generated design
        """
        url = f"{self.base_url}/sketch"
        data = {
            "email": self.email,
            "password": self.password,
            "sketch": sketch_url,
            "prompt": prompt
        }

        start_time = time.time()  # 记录开始时间

        try:
            response = self.session.post(url, data=data, timeout=self.timeout)

            # 记录响应内容
            logger.info(f"TheNewBlack API sketch to design response status: {response.status_code}")
            logger.info(f"TheNewBlack API sketch to design response content: {response.text}")

            response.raise_for_status()
            return response.text  # response is a URL to the generated design
        except requests.exceptions.RequestException as e:
            logger.error(f"Error in sketch to design: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time  # 计算请求用时
            logger.info(f"TheNewBlack sketch_to_design API request took {elapsed_time:.2f} seconds")

    def change_background(self, image_url: str, replace: str, negative: str = None) -> str:
        """
        Changes the background of an image given a prompt.

        :param image_url: URL of the original image (required)
        :param replace: Describe the new background (required)
        :param negative: Describe what you DON'T want in the design (optional)
        :return: Response from the API as a URL to the modified image
        """
        url = f"{self.base_url}/change-background"
        data = {
            "email": self.email,
            "password": self.password,
            "image": image_url,
            "replace": replace,
        }
        if negative:
            data["negative"] = negative

        start_time = time.time()  # 记录开始时间

        try:
            response = self.session.post(url, data=data, timeout=self.timeout)

            # 记录响应内容
            logger.info(f"TheNewBlack API change background response status: {response.status_code}")
            logger.info(f"TheNewBlack API change background response content: {response.text}")

            response.raise_for_status()
            return response.text  # response is a URL to the modified image
        except requests.exceptions.RequestException as e:
            logger.error(f"Error changing background: {str(e)}")
            raise
        finally:
            elapsed_time = time.time() - start_time  # 计算请求用时
            logger.info(f"TheNewBlack change_background API request took {elapsed_time:.2f} seconds")


# 适配器类，与业务代码对接
class TheNewBlack:
    def __init__(self, timeout: int = 300):
        """初始化TheNewBlack适配器类

        Args:
            timeout: HTTP请求超时时间，默认5分钟
        """
        self.api = TheNewBlackAPI(timeout=timeout)
        self.default_width = 900
        self.default_height = 1200

    async def create_clothing(
        self,
        prompt: str,
        with_human_model: int,
        gender: int,
        age: int,
        country: str,
        model_size: int,
        width: int,
        height: int,
        result_id: str
    ) -> str:
        """创建服装图片 - 与业务代码接口匹配的方法

        Args:
            prompt: 提示词
            with_human_model: 是否使用人类模特 (1-使用 0-不使用)
            gender: 性别 (1-男 2-女)
            age: 年龄
            country: 国家代码
            model_size: 模特身材代码
            result_id: 生成任务结果ID

        Returns:
            生成的图片URL
        """
        # 记录开始调用
        logger.info(f"Starting image generation with TheNewBlack for task result {result_id}")
        logger.info(f"Parameters: prompt='{prompt}', gender={gender}, age={age}, country='{country}'")

        # 将数字性别转换为API枚举
        gender_enum = Gender.MAN if gender == 1 else Gender.WOMAN

        # 根据model_size确定身材类型
        if model_size == 1:
            body_type = BodyType.SMALL
        elif model_size == 2:
            body_type = BodyType.MID_SIZE
        elif model_size == 3:
            body_type = BodyType.PLUS
        else:
            body_type = BodyType.MID_SIZE  # 默认值

        # 如果不需要人类模特，可以在prompt中增加特定指令
        outfit_prompt = prompt
        if with_human_model == 0:
            outfit_prompt = f"{prompt} (without human model, just the clothing on white background)"

        # 使用线程池执行同步请求，避免阻塞事件循环
        try:
            # 使用concurrent.futures直接调用，不依赖于事件循环获取
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.api.create_clothing,
                    width=width if width != None else self.default_width,
                    height=height if height != None else self.default_height,
                    outfit=outfit_prompt,
                    gender=gender_enum,
                    country=country,
                    age=age,
                    body_type=body_type
                )

                # 添加超时处理，避免无限等待
                image_url = await asyncio.wrap_future(future)

                # 将第三方图片URL转存到阿里云OSS
                oss_image_url = await download_and_upload_image(
                    image_url,
                    f"tnb_clothing_{result_id}"
                )

                if not oss_image_url:
                    logger.warning(f"Failed to transfer image to OSS, using original URL: {image_url}")
                    return image_url

                # 记录成功结果
                logger.info(f"Successfully generated image for task result {result_id}: {oss_image_url}")
                return oss_image_url

        except Exception as e:
            # 详细记录异常
            logger.error(f"Error in TheNewBlack image generation for task result {result_id}: {str(e)}")
            import traceback
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            raise

    async def create_image_variation(
        self,
        image_url: str,
        prompt: str,
        fidelity: float = 0.5,
        result_id: str = None
    ) -> str:
        """创建图片变体 - 与业务代码接口匹配的方法

        Args:
            image_url: 原始图片URL
            prompt: 变体描述提示词
            fidelity: 保真度，值在0-1之间（1表示最高保真度）
            result_id: 生成任务结果ID

        Returns:
            生成的图片URL
        """
        # 记录开始调用
        logger.info(f"Starting image variation with TheNewBlack for task result {result_id}")
        logger.info(f"Parameters: image_url='{image_url}', prompt='{prompt}', fidelity={fidelity}")

        # 计算deviation参数 (TheNewBlack API中，deviation是与原图的偏离度)
        # 转换保真度为deviation: 保真度越高，deviation越低
        deviation = 1.0 - fidelity

        # 使用线程池执行同步请求，避免阻塞事件循环
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.api.create_variation,
                    image_url=image_url,
                    prompt=prompt,
                    deviation=deviation
                )

                # 添加超时处理，避免无限等待
                image_url = await asyncio.wrap_future(future)

                # 将第三方图片URL转存到阿里云OSS
                oss_image_url = await download_and_upload_image(
                    image_url,
                    f"tnb_variation_{result_id}"
                )

                if not oss_image_url:
                    logger.warning(f"Failed to transfer image to OSS, using original URL: {image_url}")
                    return image_url

                # 记录成功结果
                logger.info(f"Successfully generated image variation for task result {result_id}: {oss_image_url}")
                return oss_image_url

        except Exception as e:
            # 详细记录异常
            logger.error(f"Error in TheNewBlack image variation for task result {result_id}: {str(e)}")
            import traceback
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            raise

    async def change_clothes(
        self,
        image_url: str,
        remove: str,
        replace: str,
        negative: Optional[str] = None,
        result_id: str = None
    ) -> str:
        """更换图片中的服装 - 与业务代码接口匹配的方法

        Args:
            image_url: 原始图片URL
            remove: 描述要从图片中移除的内容
            replace: 描述要替换成的新内容
            negative: 描述不想要的内容(可选)
            result_id: 生成任务结果ID

        Returns:
            生成的图片URL
        """
        # 记录开始调用
        logger.info(f"Starting change clothes with TheNewBlack for task result {result_id}")
        logger.info(f"Parameters: image_url='{image_url}', remove='{remove}', replace='{replace}'")

        # 使用线程池执行同步请求，避免阻塞事件循环
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.api.change_clothes,
                    image_url=image_url,
                    remove=remove,
                    replace=replace,
                    negative=negative
                )

                # 添加超时处理，避免无限等待
                image_url = await asyncio.wrap_future(future)

                # 将第三方图片URL转存到阿里云OSS
                oss_image_url = await download_and_upload_image(
                    image_url,
                    f"tnb_clothes_{result_id}"
                )

                if not oss_image_url:
                    logger.warning(f"Failed to transfer image to OSS, using original URL: {image_url}")
                    return image_url

                # 记录成功结果
                logger.info(f"Successfully changed clothes for task result {result_id}: {oss_image_url}")
                return oss_image_url

        except Exception as e:
            # 详细记录异常
            logger.error(f"Error in TheNewBlack change clothes for task result {result_id}: {str(e)}")
            import traceback
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            raise

    async def create_clothing_with_fabric(
        self,
        fabric_image_url: str, 
        prompt: str, 
        gender: int,
        country: str, 
        age: int,
        result_id: str = None
    ) -> str:
        """更换图片中的服装 - 与业务代码接口匹配的方法

        Args:
            image_url: 原始图片URL
            remove: 描述要从图片中移除的内容
            replace: 描述要替换成的新内容
            negative: 描述不想要的内容(可选)
            result_id: 生成任务结果ID

        Returns:
            生成的图片URL
        """
        # 记录开始调用
        logger.info(f"Starting change clothes with TheNewBlack for task result {result_id}")
        logger.info(f"Parameters: fabric_image_url='{fabric_image_url}', prompt='{prompt}', gender={gender}, country='{country}', age={age}")

        gender_enum = Gender.MAN if gender == 1 else Gender.WOMAN

        # 使用线程池执行同步请求，避免阻塞事件循环
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.api.create_clothing_with_fabric,
                    fabric_image_url=fabric_image_url,
                    prompt=prompt,
                    gender=gender_enum,
                    country=country,
                    age=age
                )

                # 添加超时处理，避免无限等待
                image_url = await asyncio.wrap_future(future)

                # 将第三方图片URL转存到阿里云OSS
                oss_image_url = await download_and_upload_image(
                    image_url,
                    f"tnb_clothes_{result_id}"
                )

                if not oss_image_url:
                    logger.warning(f"Failed to transfer image to OSS, using original URL: {image_url}")
                    return image_url

                # 记录成功结果
                logger.info(f"Successfully changed clothes for task result {result_id}: {oss_image_url}")
                return oss_image_url

        except Exception as e:
            # 详细记录异常
            logger.error(f"Error in TheNewBlack change clothes for task result {result_id}: {str(e)}")
            import traceback
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            raise

    async def create_virtual_try_on(
        self,
        model_image_url: str,
        clothing_image_url: str,
        clothing_type: str,
        result_id: str = None
    ) -> str:
        """虚拟试穿 - 与业务代码接口匹配的方法

        Args:
            model_image_url: 模特图片URL
            clothing_image_url: 服装图片URL
            clothing_type: 服装类型
            result_id: 生成任务结果ID

        Returns:
            生成的图片URL
        """
        # 记录开始调用
        logger.info(f"Starting change clothes with TheNewBlack for task result {result_id}")
        logger.info(f"Parameters: model_image_url='{model_image_url}', clothing_image_url='{clothing_image_url}', clothing_type='{clothing_type}'")

        clothing_type_enum = ClothingType.TOPS if clothing_type == 'tops' else ClothingType.BOTTOMS if clothing_type == 'bottoms' else ClothingType.ONE_PIECES

        # 使用线程池执行同步请求，避免阻塞事件循环
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.api.start_virtual_try_on,
                    model_image_url=model_image_url,
                    clothing_image_url=clothing_image_url,
                    clothing_type=clothing_type_enum
                )

                # 添加超时处理，避免无限等待
                job_id = await asyncio.wrap_future(future)

                # 获取虚拟试穿结果，每十秒获取一次，最多尝试300秒
                start_time = time.time()
                result_pic = None
                while True:
                    result = self.api.get_results(job_id)
                    if result:
                        result_pic = result
                        break
                    await asyncio.sleep(10)
                    if time.time() - start_time > 300:
                        logger.error(f"Virtual try on job {job_id} timed out after 300 seconds")
                        raise Exception("Virtual try on job timed out")

                # 将第三方图片URL转存到阿里云OSS
                oss_image_url = await download_and_upload_image(
                    result_pic,
                    f"tnb_clothes_{result_id}"
                )

                if not oss_image_url:
                    logger.warning(f"Failed to transfer image to OSS, using original URL: {result_pic}")
                    return result_pic

                # 记录成功结果
                logger.info(f"Successfully changed clothes for task result {result_id}: {oss_image_url}")
                return oss_image_url

        except Exception as e:
            # 详细记录异常
            logger.error(f"Error in TheNewBlack change clothes for task result {result_id}: {str(e)}")
            import traceback
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            raise

    async def create_sketch_to_design(
        self,
        original_pic_url: str,
        prompt: str,
        fidelity: float,
        result_id: str = None
    ) -> str:
        """虚拟试穿 - 与业务代码接口匹配的方法

        Args:
            original_pic_url: 原始图片URL
            prompt: 草图转设计提示词
            fidelity: 保真度，值在0-1之间（1表示最高保真度）
            result_id: 生成任务结果ID

        Returns:
            生成的图片URL
        """
        # 记录开始调用
        logger.info(f"Starting sketch to design with TheNewBlack for task result {result_id}")
        logger.info(f"Parameters: original_pic_url='{original_pic_url}', prompt='{prompt}', fidelity={fidelity}")

        # 使用线程池执行同步请求，避免阻塞事件循环
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future = executor.submit(
                    self.api.sketch_to_design,
                    sketch_url=original_pic_url,
                    prompt=prompt,
                    strength=fidelity
                )

                # 添加超时处理，避免无限等待
                job_id = await asyncio.wrap_future(future)

                # 获取虚拟试穿结果，每十秒获取一次，最多尝试300秒
                start_time = time.time()
                result_pic = None
                while True:
                    result = self.api.get_results(job_id)
                    if result:
                        result_pic = result
                        break
                    await asyncio.sleep(10)
                    if time.time() - start_time > 300:
                        logger.error(f"Sketch to design job {job_id} timed out after 300 seconds")
                        raise Exception("Sketch to design job timed out")

                # 将第三方图片URL转存到阿里云OSS
                oss_image_url = await download_and_upload_image(
                    result_pic,
                    f"tnb_clothes_{result_id}"
                )

                if not oss_image_url:
                    logger.warning(f"Failed to transfer image to OSS, using original URL: {result_pic}")
                    return result_pic

                # 记录成功结果
                logger.info(f"Successfully changed clothes for task result {result_id}: {oss_image_url}")
                return oss_image_url

        except Exception as e:
            # 详细记录异常
            logger.error(f"Error in TheNewBlack sketch to design for task result {result_id}: {str(e)}")
            import traceback
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            raise
