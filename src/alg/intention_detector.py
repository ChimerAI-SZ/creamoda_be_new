from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.config import settings
from src.config.log_config import logger


class IntentionDetector:

    def clothing_swap(self, image_url: str, prompt: str) -> dict[str, str]:
        """
        检测thenewblack category switcher的意图，根据用户上传的图片和prompt推断remove和replace内容
        """
        logger.info(f"IntentionDetector clothing_swap Processing '{prompt}' '{image_url}'")

        class ClothingSwapIntention(BaseModel):
            remove: str = Field(description="Item to remove")
            replace: str = Field(description="Item to replace with")

        llm = ChatOpenAI(model="openai/gpt-4o-mini", base_url="https://openrouter.ai/api/v1",
                         api_key=settings.algorithm.openrouter_api_key)
        messages = [
            HumanMessage([
                {
                    "type": "text",
                    "text": f"""Analyze this clothing image and the user prompt to determine the clothing swap intention. Identify what item needs to be removed and what it should be replaced with. Respond in JSON format with two keys: 'remove' (the item to remove) and 'replace' (what to replace it with).
User prompt: {prompt}"""
                },
                {
                    "type": "image_url",
                    "image_url": image_url
                }
            ])
        ]
        intention: ClothingSwapIntention = llm.with_structured_output(ClothingSwapIntention,
                                                                      method="json_schema").invoke(messages)
        logger.info(f"IntentionDetector Extract Intention: {intention}")
        remove = intention.remove
        replace = intention.replace
        return {
            "remove": remove,
            "replace": replace
        }

    def copy_fabric(self, image_url: str, prompt: str) -> dict[str, str]:
        """
        检测thenewblack fabric copy的意图，根据用户上传的图片和prompt推断clothing_prompt, gender, country, age的内容
        """
        logger.info(f"IntentionDetector copy_fabric Processing '{prompt}' '{image_url}'")
        from src.alg.thenewblack import Gender  # 在这里import，避免潜在的循环引用
        class CopyFabricIntention(BaseModel):
            gender: Gender = Field(description="Gender of model")
            clothing_prompt: str = Field(description="Describe the clothing prompt, emphasizing the fabric")
            country: str = Field(description="Country of model")
            age: int = Field(description="Age of model, between 20 and 70")

        llm = ChatOpenAI(model="openai/gpt-4o-mini", base_url="https://openrouter.ai/api/v1",
                         api_key=settings.algorithm.openrouter_api_key)
        messages = [
            HumanMessage([
                {
                    "type": "text",
                    "text": f"""User is trying to create a clothing image with model based on input prompt and reference fabric image. Analyze them to detect the final clothing image creation intention in JSON.
User prompt: {prompt}

Note: If user's input is not clear, guess the most likely intention and ensure all fields are filled."""
                },
                {
                    "type": "image_url",
                    "image_url": image_url
                }
            ])
        ]
        intention: CopyFabricIntention = llm.with_structured_output(CopyFabricIntention, method="json_schema").invoke(
            messages)
        logger.info(f"IntentionDetector Extract Intention: {intention}")
        gender = Gender(intention.gender)
        clothing_prompt = intention.clothing_prompt
        country = intention.country
        age = intention.age
        return {
            "gender": gender,
            "clothing_prompt": clothing_prompt,
            "country": country,
            "age": age
        }






if __name__ == "__main__":
    from src.alg.thenewblack import TheNewBlackAPI

    thenewblack_api = TheNewBlackAPI()
    detector = IntentionDetector()
    # Test clothing_swap
    image_url = "https://40e507dd0272b7bb46d376a326e6cb3c.cdn.bubble.io/cdn-cgi/image/w=384,h=,f=auto,dpr=2,fit=contain/f1744341105145x719100574055149000/upscale"
    result = detector.clothing_swap(image_url, "I want a t-shirt.")
    print("[Test IntentionDetector clothing_swap]", result)
    result = thenewblack_api.change_clothes(image_url, **result)
    print("[Test TheNewBlackAPI change_clothes]", result)
    # Test copy_fabric
    fabric_image_url = "https://as1.ftcdn.net/v2/jpg/02/71/58/56/1000_F_271585689_Ocs28VAnoFitD1oL726wzq7oKFG886fM.jpg"
    result = detector.copy_fabric(fabric_image_url, "A girl wearing a white golf suit")
    print("[Test IntentionDetector copy_fabric]", result)
    result = thenewblack_api.create_clothing_with_fabric(fabric_image_url, **result)
    print("[Test TheNewBlackAPI create_clothing_with_fabric]", result)
