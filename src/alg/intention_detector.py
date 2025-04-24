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
        logger.info(f"SmartAPI Processing '{prompt}' '{image_url}'")

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
        intention = llm.with_structured_output(ClothingSwapIntention, method="json_schema").invoke(messages)
        logger.info(f"SmartAPI Extract Intention: {intention}")
        remove = intention.remove
        replace = intention.replace
        return {
            "remove": remove,
            "replace": replace
        }


if __name__ == "__main__":
    image_url = "https://40e507dd0272b7bb46d376a326e6cb3c.cdn.bubble.io/cdn-cgi/image/w=384,h=,f=auto,dpr=2,fit=contain/f1744341105145x719100574055149000/upscale"
    detector = IntentionDetector()
    result = detector.clothing_swap(image_url, "I want a t-shirt.")
    print(result)
    from src.alg.thenewblack import TheNewBlackAPI
    thenewblack_api = TheNewBlackAPI()
    result = thenewblack_api.change_clothes(image_url, *result)
    print(result)
