from typing import List
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.config import settings


class FashionProductDescription(BaseModel):
    """Fashion product description schema for e-commerce content generation.

    Attributes:
        material: List of fabric or processing keywords (1-3 items)
        trend_style: List of fashion trend/style tags (1-3 items)
        ai_design_description: AI-generated product selling points paragraph (30-120 characters)
    """

    material: List[str] = Field(
        description="""Fabric composition or processing techniques (1-3 items)
        - Follow e-commerce standard formatting for fabric composition
        - Supports percentage composition, finishing techniques, blends
        Example:
        - 100% linen
        - recycled polyester
        - stone-washed denim"""
    )

    trend_style: List[str] = Field(
        description="""Style/trend tags (1-3 items)
        - Selected from controlled vocabulary to avoid synonym confusion
        Example:
        - Quiet Luxury
        - Y2K
        - Modern Boho"""
    )

    ai_design_description: str = Field(
        description="""Product description paragraph (30-120 chars)
        - Natural language ready for product copy
        - Should include: silhouette, usage scenario, and emotional appeal
        Example:
        A relaxed A-line dress crafted from breathable linen, inspired by coastal getaways, complete with hidden side pockets for practicality."""
    )

    @classmethod
    def caption(cls, image_url: str) -> "FashionProductDescription":
        llm = ChatOpenAI(model="openai/gpt-4o-mini", base_url="https://openrouter.ai/api/v1",
                         api_key=settings.algorithm.openrouter_api_key)
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """You are a e-commerce expert and a clothing expert. Analyze the clothing image and generate a structured description for e-commerce content."""
                    },
                    {
                        "type": "image_url",
                        "image_url": image_url
                    }
                ]
            }
        ]
        result = llm.with_structured_output(cls, method="json_schema").invoke(messages)
        return result

    @classmethod
    async def acaption(cls, image_url: str) -> "FashionProductDescription":
        llm = ChatOpenAI(model="openai/gpt-4o-mini", base_url="https://openrouter.ai/api/v1",
                         api_key=settings.algorithm.openrouter_api_key)
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """You are a e-commerce expert and a clothing expert. Analyze the clothing image and generate a structured description for e-commerce content."""
                    },
                    {
                        "type": "image_url",
                        "image_url": image_url
                    }
                ]
            }
        ]
        result = await llm.with_structured_output(cls, method="json_schema").ainvoke(messages)
        return result


if __name__ == "__main__":
    print(FashionProductDescription.caption(
        "https://40e507dd0272b7bb46d376a326e6cb3c.cdn.bubble.io/cdn-cgi/image/w=512,h=,f=auto,dpr=2,fit=contain/f1744341457951x225874588551556060/upscale"))
