"""图像相关常量定义"""

# 图像格式与尺寸映射
IMAGE_FORMAT_SIZE_MAP = {
    "1:1": {"width": 1200, "height": 1200},
    "2:3": {"width": 800, "height": 1200},
    "3:2": {"width": 1200, "height": 800},
    "3:4": {"width": 900, "height": 1200},
    "9:16": {"width": 768, "height": 1366},
}

# 支持的图像格式列表
SUPPORTED_IMAGE_FORMATS = list(IMAGE_FORMAT_SIZE_MAP.keys()) 