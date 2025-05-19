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
        self.headers = {
            "Api-Key": self.api_key or settings.algorithm.ideogram_api_key
        }

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


if __name__ == "__main__":
    ideogram = Ideogram()
    result = ideogram.edit(
        "https://replicate.delivery/pbxt/HtGQBfA5TrqFYZBf0UL18NTqHrzt8UiSIsAkUuMHtjvFDO6p/overture-creations-5sI6fQgYIuo.png",
        "https://replicate.delivery/pbxt/HtGQBqO9MtVbPm0G0K43nsvvjBB0E0PaWOhuNRrRBBT4ttbf/mask.png",
        "a cat"
    )
    url = result['data'][0]['url']
    print(url)
