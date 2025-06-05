from dataclasses import dataclass
from enum import Enum
from typing import Optional
from src.exceptions.base import CustomException

@dataclass(frozen=True)
class GenImgTypeConstant:
    type: int
    variationType: Optional[int] = None
    description: Optional[str] = None

class GenImgType(Enum):
    TEXT_TO_IMAGE = GenImgTypeConstant(1, None, "文本生成图像")
    COPY_STYLE = GenImgTypeConstant(2, 1, "洗图")
    CHANGE_CLOTHES = GenImgTypeConstant(2, 2, "衣服换装")
    FABRIC_TO_DESIGN = GenImgTypeConstant(2, 3, "面料转设计")
    SKETCH_TO_DESIGN = GenImgTypeConstant(2, 4, "手绘转设计")
    MIX_IMAGE = GenImgTypeConstant(2, 5, "图片混搭")
    STYLE_TRANSFER = GenImgTypeConstant(2, 6, "风格迁移")
    VIRTUAL_TRY_ON = GenImgTypeConstant(3, None, "虚拟试穿")
    CHANGE_COLOR = GenImgTypeConstant(4, 1, "改变颜色")
    CHANGE_BACKGROUND = GenImgTypeConstant(4, 2, "背景替换")
    REMOVE_BACKGROUND = GenImgTypeConstant(4, 3, "背景去除")
    PARTIAL_MODIFICATION = GenImgTypeConstant(4, 4, "局部修改")
    UPSCALE = GenImgTypeConstant(4, 5, "图片放大")
    FABRIC_TRANSFER = GenImgTypeConstant(5, None, "面料风格迁移")
    CHANGE_PATTERN = GenImgTypeConstant(2, 6, "图案修改")
    CHANGE_FABRIC = GenImgTypeConstant(2, 7, "面料修改")
    CHANGE_PRINTING = GenImgTypeConstant(2, 8, "印花修改")


    @classmethod
    def get_by_type_and_variation_type(cls, type: int, variation_type: int) -> GenImgTypeConstant:
        for item in cls:
            if item.value.type == type and item.value.variationType == variation_type:
                return item.value
        raise CustomException(f"No GenImgTypeConstant found for type: {type} and variation_type: {variation_type}")