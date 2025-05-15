import os
import random
import time
from io import BytesIO

from PIL import Image

from src.config.config import settings  # Import settings
from src.config.log_config import logger  # Import the logger


class InfiniAI:
    def __init__(self, api_key: str = None,
                 api_url: str = "https://cloud.infini-ai.com/api/maas/comfy_task_api/prompt"):
        """
        Initialize InfiniAI instance with the provided API key.

        :param api_key: The API key for authentication.
        :param api_url: The base URL for the InfiniAI API.
        """
        self.api_key = api_key or settings.algorithm.infiniai_api_key
        self.api_url = api_url
        logger.info(f"InfiniAI initialized with API Key: {self.api_key}")

    def save_images(self, images: list, prompt_id: str, save_dir: str) -> list:
        """
        Save the generated images to the specified directory.

        :param images: List of Image objects to save.
        :param prompt_id: The ID of the prompt associated with these images.
        :param save_dir: The directory where the images should be saved.

        :return: List of saved file paths.
        """
        start_time = time.time()
        os.makedirs(save_dir, exist_ok=True)
        saved_paths = []

        for index, img in enumerate(images):
            # Generate filename
            timestamp = int(time.time())
            filename = f"{prompt_id}_{timestamp}_{index}.png"
            save_path = os.path.join(save_dir, filename)

            # Save image
            img.save(save_path, "PNG")
            saved_paths.append(save_path)
            logger.info(f'Saved image {index} to: {save_path}')

        end_time = time.time()
        logger.info(f"Saved {len(images)} images in {end_time - start_time:.2f} seconds.")
        return saved_paths

    def upload_image_to_infiniai_oss(self, image: Image) -> str:
        """
        Upload an image to InfiniAI's OSS and return the image ID.

        :param image: The Image object to upload.

        :return: The image ID from the response.
        """
        start_time = time.time()
        url = "https://cloud.infini-ai.com/api/maas/comfy_task_api/upload/image"

        # Convert Image object to byte array
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format=image.format or 'PNG')
        img_byte_arr.seek(0)

        boundary = "---011000010111000001101001"
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="source_file"; filename="image.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode('utf-8')

        payload += img_byte_arr.getvalue()
        payload += f"\r\n--{boundary}--\r\n".encode('utf-8')

        try:
            response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()  # Check if request was successful
            image_id = response.json()["data"]["image_id"]
            end_time = time.time()
            logger.info(f"Uploaded image to OSS with ID: {image_id} in {end_time - start_time:.2f} seconds.")
            return image_id
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during image upload: {e}")
            return None

    def get_task_result(self, prompt_id: str, time_limit: int = 1800, check_interval: int = 2) -> list:
        """
        Get the result of a task using the prompt ID.

        :param prompt_id: The ID of the task.
        :param time_limit: The time limit to wait for the result in seconds.
        :param check_interval: The interval in seconds between checks for the task status.

        :return: List of generated images or error message.
        """
        start_time = time.time()
        url = "https://cloud.infini-ai.com/api/maas/comfy_task_api/get_task_info"
        ret_images = []

        payload = {
            "comfy_task_ids": [prompt_id],
            "image_post_process_cmd": "image/format,jpg/quality,Q_100",
            "url_expire_period": 1000
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        status_code = -1
        try:
            while status_code != 3:
                response = requests.post(url, json=payload, headers=headers)
                response.raise_for_status()  # Check if request was successful
                result = response.json()
                status_code = result.get('data', {}).get('comfy_task_info', [{}])[0].get('status', None)
                time.sleep(check_interval)
                if time.time() - start_time > time_limit:
                    logger.warning(f"Image generation exceeded time limit of {time_limit} seconds.")
                    return f"Generate image out of time: {time_limit} seconds."

            final_files = result['data']['comfy_task_info'][0]['final_files']

            end_time = time.time()
            logger.info(f"Task completed in {end_time - start_time:.2f} seconds.")
            return final_files

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during task result retrieval: {e}")
            return str(e)

    def comfy_request_transfer_ab(self, prompt: str, image_a_url: str, image_b_url: str, strength: float,
                                  seed: int) -> str:
        """
        Send a request for AB flow image transformation.

        :param prompt: Image prompt.
        :param image_a_url: URL of image A.
        :param image_b_url: URL of image B.
        :param strength: 0 for image A, 1 for image B.
        :param seed: The seed for randomization.

        :return: The prompt ID for the task.
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            "workflow_id": "wf-da4nq3lky7culoia",
            "prompt": {
                "4": {
                    "inputs": {
                        "ckpt_name": "sdxl/realvisxlV50_v50Bakedvae_fp16.safetensors"
                    }
                },
                "6": {
                    "inputs": {
                        "text": prompt
                    }
                },
                "7": {
                    "inputs": {
                        "text": "Nsfw, ugly, paintings, sketches, (worstquality:2), (low quality:2), (normal quality:2),lowres"
                    }
                },
                "18": {
                    "inputs": {
                        "image": image_b_url
                    }
                },
                "19": {
                    "inputs": {
                        "batch_size": 1,
                        "height": 1152,
                        "width": 832
                    }
                },
                "24": {
                    "inputs": {
                        "image": image_a_url
                    }
                },
                "40": {
                    "inputs": {
                        "cfg": 8,
                        "denoise": 1,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "steps": 20
                    }
                },
                "45": {
                    "inputs": {
                        "embeds_scaling": "V only",
                        "end_at": 1,
                        "start_at": 0,
                        "weight": 1,
                        "weight_type": "style transfer precise"
                    }
                },
                "47": {
                    "inputs": {
                        "method": "average"
                    }
                },
                "48": {
                    "inputs": {
                        "preset": "STANDARD (medium strength)"
                    }
                },
                "50": {
                    "inputs": {
                        "embeds_scaling": "V only",
                        "end_at": 1,
                        "start_at": 0,
                        "weight": 0.9,
                        "weight_type": "composition"
                    }
                },
                "51": {
                    "inputs": {
                        "method": "average"
                    }
                },
                "92": {
                    "inputs": {
                        "a_value": "1",
                        "b_value": "",
                        "operator": "-"
                    }
                },
                "93": {
                    "inputs": {
                        "float_value": strength
                    }
                },
                "104": {
                    "inputs": {
                        "seed": seed
                    }
                },
                "105": {
                    "inputs": {
                        "cfg": 1,
                        "denoise": 0.3,
                        "sampler_name": "euler",
                        "scheduler": "simple",
                        "steps": 12
                    }
                },
                "111": {
                    "inputs": {
                        "clip_name1": "clip_l.safetensors",
                        "clip_name2": "t5xxl_fp16.safetensors",
                        "device": "default",
                        "type": "flux"
                    }
                },
                "112": {
                    "inputs": {
                        "vae_name": "flux/ae.safetensors"
                    }
                },
                "113": {
                    "inputs": {
                        "text": ""
                    }
                },
                "115": {
                    "inputs": {
                        "blind_watermark": "",
                        "custom_path": "",
                        "filename_prefix": "comfyui",
                        "format": "png",
                        "meta_data": False,
                        "preview": True,
                        "quality": 80,
                        "save_workflow_as_json": False,
                        "timestamp": "None"
                    }
                },
                "116": {
                    "inputs": {
                        "max_skip_steps": 3,
                        "model_type": "flux",
                        "rel_l1_thresh": 0.2
                    }
                },
                "118": {
                    "inputs": {
                        "unet_name": "flux1-dev-Q8_0.gguf"
                    }
                }
            }
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            prompt_id = response.json()["data"]["prompt_id"]
            logger.info(f"AB flow transformation request sent with prompt ID: {prompt_id}")
            return prompt_id
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during AB flow request: {e}")
            return None

    def comfy_request_transfer_fabric_to_clothes(self, fabric_image_url: str, model_image_url: str, model_mask_url: str,
                                                 seed: int) -> str:
        """
        Send a request for fabric-to-clothes transformation.

        :param fabric_image_url: URL of the fabric image.
        :param model_image_url: URL of the model image.
        :param model_mask_url: URL of the model mask image.
        :param seed: The seed for randomization.

        :return: The prompt ID for the task.
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            "workflow_id": "wf-da4oumbjat2wufpd",
            "prompt": {
                "39": {
                    "inputs": {
                        "image": fabric_image_url
                    }
                },
                "47": {
                    "inputs": {
                        "base_multiplier": 0.8,
                        "flip_weights": False,
                        "uncond_multiplier": 1
                    }
                },
                "110": {
                    "inputs": {
                        "aspect_ratio": "original",
                        "background_color": "#000000",
                        "fit": "fill",
                        "method": "lanczos",
                        "proportional_height": 1,
                        "proportional_width": 1,
                        "round_to_multiple": "8",
                        "scale_to_length": 1024,
                        "scale_to_side": "width"
                    }
                },
                "115": {
                    "inputs": {
                        "text": "Nsfw, ugly, paintings, sketches, (worstquality:2), (low quality:2), (normal quality:2),lowres"
                    }
                },
                "116": {
                    "inputs": {
                        "end_percent": 1,
                        "start_percent": 0,
                        "strength": 0.8
                    }
                },
                "119": {
                    "inputs": {
                        "cfg": 5,
                        "denoise": 1,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "steps": 30
                    }
                },
                "140": {
                    "inputs": {
                        "combine_embeds": "concat",
                        "embeds_scaling": "V only",
                        "end_at": 1,
                        "start_at": 0,
                        "weight": 1.0,
                        "weight_type": "style transfer"
                    }
                },
                "142": {
                    "inputs": {
                        "preset": "STANDARD (medium strength)"
                    }
                },
                "260": {
                    "inputs": {
                        "image": model_image_url
                    }
                },
                "289": {
                    "inputs": {
                        "text": "Dynamic pose, photography, masterpiece, bestquality,8K,HDR, highres,(absurdres: 1.2),Kodak portra 400,film grain, blurrybackground, (bokeh: 1.2), lens flare"
                    }
                },
                "294": {
                    "inputs": {
                        "text": "Nsfw, ugly, paintings, sketches, (worstquality:2), (low quality:2), (normal quality:2),lowres"
                    }
                },
                "295": {
                    "inputs": {
                        "cfg": 8,
                        "denoise": 1,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "steps": 20
                    }
                },
                "296": {
                    "inputs": {
                        "control_net_name": "xinsir/controlnet-union-promax-sdxl-1.0.safetensors"
                    }
                },
                "297": {
                    "inputs": {
                        "end_percent": 1,
                        "start_percent": 0,
                        "strength": 1
                    }
                },
                "301": {
                    "inputs": {
                        "ckpt_name": "sdxl/realvisxlV40_v40Bakedvae.safetensors"
                    }
                },
                "303": {
                    "inputs": {
                        "base_multiplier": 0.9,
                        "flip_weights": False,
                        "uncond_multiplier": 1
                    }
                },
                "305": {
                    "inputs": {
                        "text": "white clothing,  solo, full body,\nSolid color studio, solid color background, cool white tones, studio scene, premium, Canon DSLR shooting, 50mm prime lens, cinematic filter, medium depth of field, wide format,"
                    }
                },
                "306": {
                    "inputs": {
                        "aspect_ratio": "original",
                        "background_color": "#000000",
                        "fit": "crop",
                        "method": "lanczos",
                        "proportional_height": 1,
                        "proportional_width": 1,
                        "round_to_multiple": "8",
                        "scale_to_length": 1024,
                        "scale_to_side": "width"
                    }
                },
                "322": {
                    "inputs": {
                        "expand": 4,
                        "tapered_corners": True
                    }
                },
                "326": {
                    "inputs": {
                        "blend_mode": "normal",
                        "invert_mask": False,
                        "opacity": 100
                    }
                },
                "331": {
                    "inputs": {
                        "seed": seed
                    }
                },
                "332": {
                    "inputs": {
                        "blind_watermark": "",
                        "custom_path": "",
                        "filename_prefix": "comfyui",
                        "format": "png",
                        "meta_data": False,
                        "preview": True,
                        "quality": 80,
                        "save_workflow_as_json": False,
                        "timestamp": "None"
                    }
                },
                "333": {
                    "inputs": {
                        "background_color": "#FFFFFF",
                        "fit": "fill",
                        "method": "lanczos"
                    }
                },
                "339": {
                    "inputs": {
                        "blur": 7,
                        "grow": 0,
                        "invert_mask": False
                    }
                },
                "342": {
                    "inputs": {
                        "image": model_mask_url
                    }
                },
                "343": {
                    "inputs": {
                        "channel": "red"
                    }
                }
            }
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            prompt_id = response.json()["data"]["prompt_id"]
            logger.info(f"Fabric-to-clothes transformation request sent with prompt ID: {prompt_id}")
            return prompt_id
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during fabric-to-clothes request: {e}")
            return None

    def create_full_mask(self, image_url) -> Image.Image:
        # Download the original image to get its dimensions
        response = requests.get(image_url)
        response.raise_for_status()
        original_image = Image.open(BytesIO(response.content))

        # Create a white image with the same dimensions
        white_mask = Image.new('RGB', original_image.size, (255, 255, 255))
        return white_mask

    def comfy_request_upscale(self, image_url: str, mask_url: str, seed: int, strength: float = 0.3,
                              size: int = 2048):
        """
        Send a request for image upscaling.

        :param image_url: URL of the image to upscale.
        :param mask_url: URL of the mask image.
        :param seed: The seed for randomization.
        :param strength: Strength of the upscaling.
        :param size: Size of the output image.

        :return: The prompt ID for the task.
        """

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        # input node ID
        # 2="Load Original Image"
        # 45="Load Original Mask"
        # 42="Strength"
        # 43="Upscale Size"
        # 54="Seed"
        payload = {
            "workflow_id": "wf-da6d45bnopdz3r2w",
            "prompt": {
                "2": {
                    "inputs": {
                        "image": image_url
                    }
                },
                "42": {
                    "inputs": {
                        "float_value": strength
                    }
                },
                "43": {
                    "inputs": {
                        "int_value": size
                    }
                },
                "45": {
                    "inputs": {
                        "image": mask_url
                    }
                },
                "54": {
                    "inputs": {
                        "seed": seed
                    }
                }
            }
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()  # 检查请求是否成功
            return response.json()["data"]["prompt_id"]
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during upscale request: {e}")
            return None

    def comfy_request_change_background(self, original_image_url: str, reference_image_url: str, background_prompt: str,
                                        seed: int, refine_size: int = 1536) -> str:
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        # input node ID
        # 16="Load Original Image"
        # 15="Load Reference Image"
        # 87="background_prompt"
        # 178="Refine Size"
        # 177="Seed"
        payload = {
            "workflow_id": "wf-da6fbxxysybz56vd",
            "prompt": {
                "15": {
                    "inputs": {
                        "image": reference_image_url
                    }
                },
                "16": {
                    "inputs": {
                        "image": original_image_url
                    }
                },
                "87": {
                    "inputs": {
                        "text": background_prompt
                    }
                },
                "177": {
                    "inputs": {
                        "seed": seed
                    }
                },
                "178": {
                    "inputs": {
                        "int_value": refine_size
                    }
                }
            }
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()  # 检查请求是否成功
            return response.json()["data"]["prompt_id"]
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during change background request: {e}")
            return None

    def comfy_request_change_fabric(self, original_image_url: str, original_mask_url: str, fabric_image_url: str,
                                    seed: int,
                                    fabric_size: int = 2048) -> str:
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        # input node ID
        # 13="Load Original Image"
        # 64="Load Original Mask"
        # 35="Fabric Image"
        # 63="Fabric Size"
        # 69="Seed"
        payload = {
            "workflow_id": "wf-da7vgrwa7aihyvbx",
            "prompt": {
                "13": {
                    "inputs": {
                        "image": original_image_url
                    }
                },
                "35": {
                    "inputs": {
                        "image": fabric_image_url
                    }
                },
                "63": {
                    "inputs": {
                        "int_value": fabric_size
                    }
                },
                "64": {
                    "inputs": {
                        "image": original_mask_url
                    }
                },
                "69": {
                    "inputs": {
                        "seed": seed
                    }
                }
            }
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()  # 检查请求是否成功
            logger.info(f"Change fabric request sent with prompt ID: {response.json()['data']['prompt_id']}")
            return response.json()["data"]["prompt_id"]
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during change fabric request: {e}")
            return None


# Example usage
if __name__ == "__main__":
    import requests
    import io

    infini_ai = InfiniAI()


    def test_mixing_style():
        # Example of Mixing Styles
        image_a_url = "https://40e507dd0272b7bb46d376a326e6cb3c.cdn.bubble.io/cdn-cgi/image/w=384,h=,f=auto,dpr=2,fit=contain/f1744616433323x773760165443033100/upscale"
        image_b_url = "https://40e507dd0272b7bb46d376a326e6cb3c.cdn.bubble.io/cdn-cgi/image/w=384,h=,f=auto,dpr=2,fit=contain/f1744612696516x389731609267175230/gGaWt1YY3fgb6aUQrHybE_output.png"

        image_a = Image.open(io.BytesIO(requests.get(image_a_url).content))
        image_b = Image.open(io.BytesIO(requests.get(image_b_url).content))

        # 必须要先把图片上传到InfiniAI自己的OSS才能用于后续处理，否则会报错
        image_a_url = infini_ai.upload_image_to_infiniai_oss(image_a)
        image_b_url = infini_ai.upload_image_to_infiniai_oss(image_b)

        transfer_ab_prompt_id = infini_ai.comfy_request_transfer_ab("simple background", image_a_url, image_b_url, 0.9,
                                                                    seed=random.randint(0, 2147483647))
        result_urls = infini_ai.get_task_result(transfer_ab_prompt_id)
        return result_urls[0]


    def test_transfer_fabric():
        # Example of Changing Fabric
        fabric_image_url = "https://cdn.pixabay.com/photo/2016/10/17/13/53/velvet-1747666_640.jpg"
        model_image_url = "https://replicate.delivery/pbxt/JF3LddQgRiMM9Q4Smyfw7q7BR9Gn0PwkSWvJjKDPxyvr8Ru0/cool-dog.png"
        model_mask_url = "https://replicate.delivery/pbxt/JF3Ld3yPLVA3JIELHx1uaAV5CQOyr4AoiOfo6mJZn2fofGaT/dog-mask.png"

        fabric_image = Image.open(io.BytesIO(requests.get(fabric_image_url).content))
        model_image = Image.open(io.BytesIO(requests.get(model_image_url).content))
        model_mask = Image.open(io.BytesIO(requests.get(model_mask_url).content))

        # Upload images to InfiniAI's OSS
        fabric_image_url = infini_ai.upload_image_to_infiniai_oss(fabric_image)
        model_image_url = infini_ai.upload_image_to_infiniai_oss(model_image)
        model_mask_url = infini_ai.upload_image_to_infiniai_oss(model_mask)

        seed = random.randint(0, 2147483647)
        transfer_fabric_prompt_id = infini_ai.comfy_request_transfer_fabric_to_clothes(
            fabric_image_url, model_image_url, model_mask_url, seed
        )
        result_urls = infini_ai.get_task_result(transfer_fabric_prompt_id)
        return result_urls[0]


    def test_upscale():
        image_url = "https://40e507dd0272b7bb46d376a326e6cb3c.cdn.bubble.io/cdn-cgi/image/w=384,h=,f=auto,dpr=2,fit=contain/f1744616433323x773760165443033100/upscale"
        image = Image.open(io.BytesIO(requests.get(image_url).content))
        mask_image = infini_ai.create_full_mask(image_url)

        # Upload images to InfiniAI's OSS
        image_url = infini_ai.upload_image_to_infiniai_oss(image)
        mask_url = infini_ai.upload_image_to_infiniai_oss(mask_image)

        seed = random.randint(0, 2147483647)
        upscale_prompt_id = infini_ai.comfy_request_upscale(
            image_url, mask_url, seed
        )
        result_urls = infini_ai.get_task_result(upscale_prompt_id)
        return result_urls[0]


    def test_change_background():
        image_url = "https://40e507dd0272b7bb46d376a326e6cb3c.cdn.bubble.io/cdn-cgi/image/w=384,h=,f=auto,dpr=2,fit=contain/f1744616433323x773760165443033100/upscale"
        background_image_url = "https://tjzk.replicate.delivery/models_models_featured_image/a79cc4a8-318c-4316-a800-097ef0bdce7a/https___replicate.del_25H5GQ7.webp"

        image = Image.open(io.BytesIO(requests.get(image_url).content))
        background_image = Image.open(io.BytesIO(requests.get(background_image_url).content))

        image_url = infini_ai.upload_image_to_infiniai_oss(image)
        background_image_url = infini_ai.upload_image_to_infiniai_oss(background_image)

        prompt = "forest"
        seed = random.randint(0, 2147483647)
        change_background_prompt_id = infini_ai.comfy_request_change_background(image_url, background_image_url, prompt,
                                                                                seed)
        result_urls = infini_ai.get_task_result(change_background_prompt_id)
        return result_urls[0]


    def test_change_fabric():
        model_image_url = "https://replicate.delivery/pbxt/KxK0uEJXomVTQxBx37Q758ubj5l98vymeKWBOKnTvjUOGITF/olga-zhuravleva-A3MleA0jtoE-unsplash.jpg"
        model_mask_url = "https://replicate.delivery/pbxt/fFn9jPcxgNwyPSh3UX2QxuzU9ZNjhLYogUf1Ygvkj3U7f7slA/out.png"
        fabric_image_url = "https://cdn.pixabay.com/photo/2016/10/17/13/53/velvet-1747666_640.jpg"

        fabric_image = Image.open(io.BytesIO(requests.get(fabric_image_url).content))
        model_image = Image.open(io.BytesIO(requests.get(model_image_url).content))
        model_mask = Image.open(io.BytesIO(requests.get(model_mask_url).content))

        # Upload images to InfiniAI's OSS
        fabric_image_url = infini_ai.upload_image_to_infiniai_oss(fabric_image)
        model_image_url = infini_ai.upload_image_to_infiniai_oss(model_image)
        model_mask_url = infini_ai.upload_image_to_infiniai_oss(model_mask)

        seed = random.randint(0, 2147483647)

        change_fabric_prompt_id = infini_ai.comfy_request_change_fabric(
            model_image_url, model_mask_url, fabric_image_url, seed
        )
        result_urls = infini_ai.get_task_result(change_fabric_prompt_id)
        return result_urls[0]
