import io
import json
from typing import Optional, List, Union, IO

import requests
from PIL.Image import Image

from src.config.config import settings


class Ideogram:
    """
    Client for Ideogram 3.0 API. Provides methods to edit images using Ideogram's edit endpoint.
    """

    BASE_URL = "https://api.ideogram.ai/v1/ideogram-v3"
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self, api_key: str = None, timeout: Optional[float] = 300):
        """
        Initialize the Ideogram client.

        :param api_key: Your Ideogram API key.
        :param timeout: Request timeout in seconds (default: 30).
        """
        self.api_key = api_key
        self.timeout = timeout
        final_api_key = self.api_key or settings.algorithm.ideogram_api_key
        
        # Validate API key format
        if not final_api_key or len(final_api_key) < 10:
            raise ValueError("Invalid or missing Ideogram API key")
            
        self.headers = {
            "Api-Key": final_api_key,
        }
    
    def test_connection(self) -> bool:
        """
        Test if the API key and connection are working by making a simple request.
        
        :return: True if connection is successful, False otherwise.
        """
        try:
            # Make a simple generate request with minimal parameters
            test_response = self.generate(
                prompt="test",
                num_images=1,
                rendering_speed="TURBO"
            )
            return "data" in test_response and len(test_response["data"]) > 0
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False

    def _prepare_file(self, f: Union[str, IO], invert_mask: bool = False) -> IO:
            """
            Prepare a file-like object for upload. If input is a URL, download it.
            If the content exceeds MAX_FILE_SIZE, compress it using PIL.
            Optionally invert black and white pixels in mask images.

            :param f: File path, URL, or file-like object.
            :param invert_mask: If True, inverts black and white pixels in the image.
            :return: File-like object ready for upload.
            """
            # Download if URL
            if isinstance(f, str) and f.startswith(("http://", "https://")):
                resp = requests.get(f, stream=True, timeout=self.timeout)
                resp.raise_for_status()
                raw = resp.content
                file_io = io.BytesIO(raw)
            elif isinstance(f, str):
                file_io = open(f, "rb")
            else:
                file_io = f

            # If inversion is needed, process the image
            if invert_mask:
                from PIL import Image, ImageOps

                # Store position and rewind
                pos = file_io.tell()
                file_io.seek(0)

                # Open, invert, and save back to buffer
                img = Image.open(file_io)
                inverted_img = ImageOps.invert(img.convert("L"))

                buffer = io.BytesIO()
                inverted_img.save(buffer, format=img.format if img.format else "PNG")
                buffer.seek(0)
                file_io = buffer
            else:
                # Reset to beginning if we opened the file
                if isinstance(f, str):
                    file_io.seek(0)

            # Check size
            file_io.seek(0, io.SEEK_END)
            size = file_io.tell()
            file_io.seek(0)

            # Compress if needed
            if size > self.MAX_FILE_SIZE:
                img = Image.open(file_io)
                buffer = io.BytesIO()
                fmt = img.format if img.format else "JPEG"
                quality = 85
                # Iteratively reduce quality
                while True:
                    buffer.seek(0)
                    buffer.truncate()
                    save_kwargs = {"format": fmt}
                    if fmt.upper() in ["JPEG", "JPG", "WEBP"]:
                        save_kwargs["quality"] = quality
                    else:
                        save_kwargs["optimize"] = True
                    img.save(buffer, **save_kwargs)
                    if buffer.getbuffer().nbytes <= self.MAX_FILE_SIZE or quality <= 10:
                        break
                    quality -= 10
                buffer.seek(0)
                return buffer

            file_io.seek(0)
            return file_io

    def edit(
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
    ) -> dict:
        """
        Edit an image using Ideogram 3.0 API.

        :param image: URL, path, or file-like object of the source image.
        :param mask: URL, path, or file-like object of the mask image.
        :param prompt: Text prompt guiding the edit.
        :param magic_prompt: 'AUTO', 'ON', or 'OFF' to enable MagicPrompt.
        :param num_images: Number of images to generate (1-8).
        :param seed: Random seed for reproducibility.
        :param rendering_speed: 'TURBO', 'DEFAULT', or 'QUALITY'.
        :param color_palette: Palette dict (preset name or members list).
        :param style_codes: List of style hex codes.
        :param style_reference_images: List of style reference images (URLs, paths, or file-like).
        :param is_white_mask: If True, inverts black and white pixels in the mask.
        :return: JSON response from the API.
        """
        url = f"{self.BASE_URL}/edit"

        files = {}
        # Prepare main image and mask
        files["image"] = self._prepare_file(image)
        files["mask"] = self._prepare_file(mask, invert_mask=is_white_mask)

        # Prepare style reference images
        if style_reference_images:
            for idx, ref in enumerate(style_reference_images):
                key = f"style_reference_images[{idx}]"
                files[key] = self._prepare_file(ref)

        # Prepare form data
        data = {"prompt": prompt, "rendering_speed": rendering_speed}
        if magic_prompt:
            data["magic_prompt"] = magic_prompt
        if num_images:
            data["num_images"] = str(num_images)
        if seed is not None:
            data["seed"] = str(seed)
        if color_palette:
            data["color_palette"] = json.dumps(color_palette)
        if style_codes:
            data["style_codes"] = json.dumps(style_codes)

        try:
            response = requests.post(
                url,
                headers=self.headers,
                files=files,
                data=data,
                timeout=self.timeout
            )

            # Close file objects
            for f_obj in files.values():
                try:
                    f_obj.close()
                except Exception:
                    pass

            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            # Log detailed error information for debugging
            if e.response.status_code == 415:
                print(f"HTTP 415 Error - Request URL: {url}")
                print(f"HTTP 415 Error - Request headers: {self.headers}")
                print(f"HTTP 415 Error - Request data keys: {list(data.keys()) if data else 'None'}")
                print(f"HTTP 415 Error - Request files keys: {list(files.keys()) if files else 'None'}")
                print(f"HTTP 415 Error - Response text: {e.response.text}")
                print(f"HTTP 415 Error - Response headers: {dict(e.response.headers)}")
            raise
        except Exception as e:
            # Close file objects in case of any exception
            for f_obj in files.values():
                try:
                    f_obj.close()
                except Exception:
                    pass
            raise

    def generate(
            self,
            prompt: str,
            seed: Optional[int] = None,
            resolution: Optional[str] = None,
            aspect_ratio: Optional[str] = None,
            rendering_speed: Optional[str] = "DEFAULT",
            magic_prompt: Optional[str] = "AUTO",
            negative_prompt: Optional[str] = None,
            num_images: Optional[int] = 1,
            color_palette: Optional[dict] = None,
            style_codes: Optional[List[str]] = None,
            style_type: Optional[str] = "GENERAL",
            style_reference_images: Optional[List[Union[str, IO]]] = None,
            character_reference_images: Optional[List[Union[str, IO]]] = None,
            character_reference_images_mask: Optional[List[Union[str, IO]]] = None
    ) -> dict:
        """
        Generate images using Ideogram 3.0 API.

        :param prompt: The prompt to use to generate the image.
        :param seed: Random seed for reproducible generation (0-2147483647).
        :param resolution: The resolution for image generation.
        :param aspect_ratio: The aspect ratio to use for image generation.
        :param rendering_speed: 'TURBO', 'DEFAULT', or 'QUALITY'.
        :param magic_prompt: 'AUTO', 'ON', or 'OFF' to enable MagicPrompt.
        :param negative_prompt: Description of what to exclude from an image.
        :param num_images: Number of images to generate (1-8).
        :param color_palette: Palette dict (preset name or members list).
        :param style_codes: List of 8 character hexadecimal codes representing the style.
        :param style_type: 'AUTO', 'GENERAL', 'REALISTIC', 'DESIGN', 'FICTION'.
        :param style_reference_images: List of style reference images (URLs, paths, or file-like).
        :param character_reference_images: List of character reference images.
        :param character_reference_images_mask: Optional masks for character reference images.
        :return: JSON response from the API.
        """
        url = f"{self.BASE_URL}/generate"

        files = {}
        
        # Prepare style reference images
        if style_reference_images:
            for idx, ref in enumerate(style_reference_images):
                key = f"style_reference_images[{idx}]"
                files[key] = self._prepare_file(ref)

        # Prepare character reference images
        if character_reference_images:
            for idx, ref in enumerate(character_reference_images):
                key = f"character_reference_images[{idx}]"
                files[key] = self._prepare_file(ref)

        # Prepare character reference images mask
        if character_reference_images_mask:
            for idx, mask in enumerate(character_reference_images_mask):
                key = f"character_reference_images_mask[{idx}]"
                files[key] = self._prepare_file(mask)

        # Prepare form data
        data = {"prompt": prompt, "rendering_speed": rendering_speed}
        if seed is not None:
            data["seed"] = str(seed)
        if resolution:
            data["resolution"] = resolution
        if aspect_ratio:
            data["aspect_ratio"] = aspect_ratio
        if magic_prompt:
            data["magic_prompt"] = magic_prompt
        if negative_prompt:
            data["negative_prompt"] = negative_prompt
        if num_images:
            data["num_images"] = str(num_images)
        if color_palette:
            data["color_palette"] = json.dumps(color_palette)
        if style_codes:
            data["style_codes"] = json.dumps(style_codes)
        if style_type:
            data["style_type"] = style_type

        try:
            # 根据是否有文件选择不同的请求格式
            if files:
                # 有文件时使用 multipart/form-data
                response = requests.post(
                    url,
                    headers=self.headers,
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
            else:
                # 没有文件时使用 application/json
                # 需要将字符串类型的数值转换为适当的类型
                json_data = data.copy()
                if "seed" in json_data:
                    json_data["seed"] = int(json_data["seed"])
                if "num_images" in json_data:
                    json_data["num_images"] = int(json_data["num_images"])
                if "color_palette" in json_data:
                    json_data["color_palette"] = json.loads(json_data["color_palette"])
                if "style_codes" in json_data:
                    json_data["style_codes"] = json.loads(json_data["style_codes"])
                
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=json_data,  # 使用 json 参数而不是 data
                    timeout=self.timeout
                )

            # Close file objects
            for f_obj in files.values():
                try:
                    f_obj.close()
                except Exception:
                    pass

            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            # Log detailed error information for debugging
            error_status = e.response.status_code
            print(f"HTTP {error_status} Error - Request URL: {url}")
            print(f"HTTP {error_status} Error - Request headers: {self.headers}")
            print(f"HTTP {error_status} Error - Request data: {data}")
            print(f"HTTP {error_status} Error - Request files keys: {list(files.keys()) if files else 'None'}")
            print(f"HTTP {error_status} Error - Response text: {e.response.text}")
            print(f"HTTP {error_status} Error - Response headers: {dict(e.response.headers)}")
            
            # 特别处理400错误，打印更多调试信息
            if error_status == 400:
                print(f"HTTP 400 Error - Likely parameter validation failed")
                print(f"HTTP 400 Error - Check aspect_ratio: {data.get('aspect_ratio', 'Not set')}")
                print(f"HTTP 400 Error - Check prompt length: {len(data.get('prompt', ''))} chars")
                print(f"HTTP 400 Error - Check style_type: {data.get('style_type', 'Not set')}")
            raise
        except Exception as e:
            # Close file objects in case of any exception
            for f_obj in files.values():
                try:
                    f_obj.close()
                except Exception:
                    pass
            raise


if __name__ == "__main__":
    ideogram = Ideogram()
    result = ideogram.edit(
        "https://replicate.delivery/pbxt/HtGQBfA5TrqFYZBf0UL18NTqHrzt8UiSIsAkUuMHtjvFDO6p/overture-creations-5sI6fQgYIuo.png",
        "https://replicate.delivery/pbxt/HtGQBqO9MtVbPm0G0K43nsvvjBB0E0PaWOhuNRrRBBT4ttbf/mask.png",
        "a cat"
    )
    url = result['data'][0]['url']
    print(url)
