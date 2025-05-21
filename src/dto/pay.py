from typing import List
from pydantic import BaseModel, Field, validator

from src.constants.credit_point_value import PointValue
from src.dto.common import CommonResponse


class SubscribeRequest(BaseModel):
    """订阅请求DTO"""
    level: int = Field(..., description="订阅等级", ge=1, le=3)

class SubscribeResponseData(BaseModel):
    """订阅响应DTO"""
    url: str = Field(..., description="支付链接")

class SubscribeResponse(CommonResponse[SubscribeResponseData]):
    pass

class CancelSubscribeRequest(BaseModel):
    pass

class CancelSubscribeResponse(BaseModel):
    """取消订阅响应DTO"""
    code: int
    msg: str

class PurchaseCreditRequest(BaseModel):
    """购买积分请求DTO"""
    value: PointValue = Field(..., description="积分")

class PurchaseCreditResponseData(BaseModel):
    url: str = Field(..., description="支付链接")

class PurchaseCreditResponse(CommonResponse[PurchaseCreditResponseData]):
    pass

class BillingHistoryRequest(BaseModel):
    """账单历史请求DTO"""
    page: int = Field(..., description="页码")
    pageSize: int = Field(..., description="每页数量")

class BillingHistoryItem(BaseModel):
    """账单历史项DTO"""
    id: int = Field(..., description="账单ID")
    amount: int = Field(..., description="金额")
    createdAt: str = Field(..., description="创建时间")
    type: str = Field(..., description="类型")

class BillingHistoryItem(BaseModel):
    """账单历史项DTO"""
    dueDate: str = Field(..., description="到期时间")
    description: str = Field(..., description="描述")
    status: str = Field(..., description="账单状态")
    invoice: str = Field(..., description="金额")
    
class BillingHistoryData(BaseModel):
    total: int = Field(..., description="总记录数")
    list: List[BillingHistoryItem] = Field(..., description="记录列表")

class BillingHistoryResponse(CommonResponse[BillingHistoryData]):
    pass


