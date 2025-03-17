import random
from typing import List, Tuple

# 定义风格提示词列表
STYLE_PROMPTS: List[Tuple[str, str]] = [
    ("Classic Style", ", classic style"),
    ("Bohemian Style", ", bohemian style"),
    ("Streetwear Style", ", streetwear style"),
    ("Minimalist Style", ", minimalist style"),
    ("Luxury Style", ", luxury style"),
    ("Vintage Style", ", vintage style"),
    ("Athleisure Style", ", athleisure style")
]

def get_random_style_prompt() -> Tuple[str, str]:
    """
    随机选择一个风格提示词
    
    Returns:
        Tuple[str, str]: 包含风格名称和风格提示词的元组
    """
    return random.choice(STYLE_PROMPTS)

def append_random_style_to_prompt(prompt: str) -> Tuple[str, str]:
    """
    在提示词后面添加随机风格
    
    Args:
        prompt: 原始提示词
        
    Returns:
        Tuple[str, str]: (添加风格后的提示词, 风格名称)
    """
    style_name, style_prompt = get_random_style_prompt()
    enhanced_prompt = f"{prompt}{style_prompt}"
    return enhanced_prompt, style_name 