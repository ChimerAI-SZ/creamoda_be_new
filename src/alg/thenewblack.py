from enum import Enum

import requests

from src.config.config import settings


class Gender(Enum):
    MAN = 'man'
    WOMAN = 'woman'


class BodyType(Enum):
    SMALL = 'small'
    PLUS = 'plus'
    PREGNANT = 'pregnant'
    MID_SIZE = ''


class TheNewBlackAPI:
    def __init__(self, email: str = None, password: str = None):
        """
        Initializes the TheNewBlackAPI instance with email and password.

        :param email: User's email address
        :param password: User's password
        """
        self.email = email or settings.algorithm.thenewblack_email
        self.password = password or settings.algorithm.thenewblack_password
        self.base_url = "https://thenewblack.ai/api/1.1/wf"
        self.session = requests.Session()
        self.session.auth = (self.email, self.password)

    def create_clothing(self, outfit: str, gender: Gender, country: str, age: int, width: int, height: int,
                        body_type: BodyType = BodyType.MID_SIZE, background: str = None, negative: str = None) -> str:
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

        response = self.session.post(url, data=data)
        return response.text  # response is a URL to the generated image

    def get_credit_balance(self) -> int:
        """
        Retrieves the current credit balance of the account.

        :return: The credit balance as an integer
        """
        url = f"{self.base_url}/credits"
        data = {
            "email": self.email,
            "password": self.password,
        }

        response = self.session.post(url, data=data)
        return int(response.text)  # response is the credit balance as an integer

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
        }
        if negative:
            data["negative"] = negative

        response = self.session.post(url, data=data)
        return response.text  # response is a URL to the modified image

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

        response = self.session.post(url, data=data)
        return response.text  # response is a URL to the variation image
