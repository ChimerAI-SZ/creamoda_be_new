import replicate

from src.config.config import settings


class Replicate:
    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = settings.algorithm.replicate_api_key
        self.api_key = api_key
        self.client = replicate.client.Client(api_token=api_key)

    def upscale(self, image_url: str, scale: int = 2) -> bytes:
        input = {
            "image": image_url,
            "scale": scale
        }
        output = self.client.run(
            "nightmareai/real-esrgan:f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa",
            input=input
        )
        return output.read()

    def remove_background(self, image_url: str) -> bytes:
        input = {
            "image": image_url
        }
        output = self.client.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input=input
        )
        return output.read()
