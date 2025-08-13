
from typing import Any, Dict
from pydantic import BaseModel

from src.dto.common import CommonResponse


class CreatePaypalProductRequest(BaseModel):
    name: str
    description: str
    category: str = "SOFTWARE"

class CreatePaypalProductResponseData(BaseModel):
    resp: Dict[str, Any]

class CreatePaypalProductResponse(CommonResponse[CreatePaypalProductResponseData]):
    pass 

class CreatePaypalPlanRequest(BaseModel):
    product_id: str
    plan_name: str
    price: float
    currency: str
    interval_unit: str
    interval_count: int
    total_cycles: int
    
class CreatePaypalPlanResponseData(BaseModel):
    resp: Dict[str, Any]

class CreatePaypalPlanResponse(CommonResponse[CreatePaypalPlanResponseData]):
    pass


class RechargeCreditRequest(BaseModel):
    email: str
    amount: int
    secret_key: str

class RechargeCreditResponseData(BaseModel):
    user_id: int
    old_credit: int
    new_credit: int
    recharge_amount: int

class RechargeCreditResponse(CommonResponse[RechargeCreditResponseData]):
    pass


