import random
from typing import List, Tuple

# 定义风格提示词列表
STYLE_PROMPTS: List[Tuple[str, str]] = [
    ("Classic Style", ", classic style, timeless design, elegant and refined"),
    ("Bohemian Style", ", bohemian style, flowy and relaxed, with ethnic patterns and fringe details"),
    ("Streetwear Style", ", streetwear style, oversized fit, urban and edgy with bold graphics"),
    ("Minimalist Style", ", minimalist style, clean lines, neutral colors, and no unnecessary embellishments"),
    ("Luxury Style", ", luxury style, high-end fabrics, intricate detailing, and opulent accents"),
    ("Vintage Style", ", vintage style, inspired by the 70s, with retro patterns and nostalgic charm"),
    ("Athleisure Style", ", athleisure style, sporty and functional, with performance fabrics and casual comfort"),
    ("Punk Style", ", punk style, rebellious and bold, with leather, studs, and distressed elements")
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