from dataclasses import dataclass
from enum import Enum
from typing import Optional
from src.exceptions.base import CustomException

@dataclass(frozen=True)
class GenImgTypeConstant:
    type: int
    variationType: Optional[int] = None
    description: Optional[str] = None
    path: Optional[str] = None

class GenImgType(Enum):
    TEXT_TO_IMAGE = GenImgTypeConstant(1, None, "文本生成图像", "design,text to image")
    COPY_STYLE = GenImgTypeConstant(2, 1, "洗图", "design, image to image, copy style")
    CHANGE_CLOTHES = GenImgTypeConstant(2, 2, "衣服换装", "design, image to image, change clothes")
    FABRIC_TO_DESIGN = GenImgTypeConstant(2, 3, "面料转设计", "design, image to image, fabric to design")
    SKETCH_TO_DESIGN = GenImgTypeConstant(2, 4, "手绘转设计", "design, image to image, sketch to design")
    MIX_IMAGE = GenImgTypeConstant(2, 5, "图片混搭", "design, image to image, mix image")
    STYLE_TRANSFER = GenImgTypeConstant(2, 6, "风格迁移(未使用)", "design, image to image, style transfer")
    CHANGE_PATTERN = GenImgTypeConstant(2, 7, "改变版型", "design, image to image, change pattern")
    CHANGE_FABRIC = GenImgTypeConstant(2, 8, "面料替换", "design, image to image, change fabric")
    CHANGE_PRINTING = GenImgTypeConstant(2, 9, "改变印花", "design, image to image, change printing")
    STYLE_FUSION = GenImgTypeConstant(2, 10, "风格融合", "design, image to image, style fusion")
    VIRTUAL_TRY_ON = GenImgTypeConstant(3, 1, "虚拟试穿", "design, virtual try on")
    CHANGE_POSE = GenImgTypeConstant(3, 2, "模特换姿势", "design, virtual try on, change pose")
    CHANGE_COLOR = GenImgTypeConstant(4, 1, "改变颜色", "design, magic kit, change color")
    CHANGE_BACKGROUND = GenImgTypeConstant(4, 2, "背景替换", "design, magic kit, change background")
    REMOVE_BACKGROUND = GenImgTypeConstant(4, 3, "背景去除", "design, magic kit, remove background")
    PARTICIAL_MODIFICATION = GenImgTypeConstant(4, 4, "局部修改", "design, magic kit, partial modification")
    UPSCALE = GenImgTypeConstant(4, 5, "图片放大", "design, magic kit, upscale")
    EXTRACT_PATTERN = GenImgTypeConstant(4, 6, "印花提取", "design, magic kit, extract pattern")
    DRESS_PRINTING_TRYON = GenImgTypeConstant(4, 7, "印花上身", "design, magic kit, dress printing try on")
    PRINTING_REPLACEMENT = GenImgTypeConstant(4, 8, "印花摆放", "design, magic kit, printing replacement")
    FABRIC_TRANSFER = GenImgTypeConstant(5, None, "面料风格迁移", "design, fabric transfer")

    @classmethod
    def get_by_type_and_variation_type(cls, type: int, variation_type: int) -> GenImgTypeConstant:
        for item in cls:
            if item.value.type == type and item.value.variationType == variation_type:
                return item.value
        raise CustomException(f"No GenImgTypeConstant found for type: {type} and variation_type: {variation_type}")