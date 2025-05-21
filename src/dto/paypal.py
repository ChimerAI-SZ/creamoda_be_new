from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class PaypalCaptureRequest(BaseModel):
    order_id: str

class PaypalCaptureResponse(BaseModel):
    """Paypal捕获响应"""
    code: int
    msg: str

class PaypalCallbackResponse(BaseModel):
    """Paypal回调响应"""
    code: int
    msg: str

class PayPalOrderLink(BaseModel):
    """PayPal订单链接项DTO"""
    href: str = Field(..., description="链接URL")
    method: str = Field(..., description="HTTP方法")
    rel: str = Field(..., description="关系类型")


class PayPalOrderResponse(BaseModel):
    """PayPal订单响应DTO"""
    id: str = Field(..., description="PayPal订单ID")
    links: List[PayPalOrderLink] = Field(..., description="操作链接列表")
    status: str = Field(..., description="订单状态")
    
    def get_approve_link(self) -> Optional[str]:
        """获取支付批准链接"""
        for link in self.links:
            if link.rel == "approve":
                return link.href
        return None
    
    def get_capture_link(self) -> Optional[str]:
        """获取支付捕获链接"""
        for link in self.links:
            if link.rel == "capture":
                return link.href
        return None
    
class PayPalAmount(BaseModel):
    currency_code: str = Field(..., description="货币代码")
    value: str = Field(..., description="金额值")


class PayPalLink(BaseModel):
    href: str = Field(..., description="链接URL")
    rel: str = Field(..., description="关系类型")
    method: str = Field(..., description="HTTP方法")


class PayPalSellerProtection(BaseModel):
    status: str = Field(..., description="保护状态")
    dispute_categories: List[str] = Field(..., description="争议类别")


class PayPalSellerReceivableBreakdown(BaseModel):
    gross_amount: PayPalAmount = Field(..., description="总金额")
    paypal_fee: PayPalAmount = Field(..., description="PayPal费用")
    net_amount: PayPalAmount = Field(..., description="净金额")


class PayPalResource(BaseModel):
    id: str = Field(..., description="捕获ID")
    status: str = Field(..., description="状态")
    amount: PayPalAmount = Field(..., description="金额")
    seller_protection: PayPalSellerProtection = Field(..., description="卖家保护")
    final_capture: bool = Field(..., description="是否为最终捕获")
    seller_receivable_breakdown: PayPalSellerReceivableBreakdown = Field(..., description="卖家收款明细")
    links: List[PayPalLink] = Field(..., description="相关链接")


class PayPalWebhookEvent(BaseModel):
    id: str = Field(..., description="Webhook事件ID")
    event_version: str = Field(..., description="事件版本")
    create_time: datetime = Field(..., description="创建时间")
    resource_type: str = Field(..., description="资源类型")
    event_type: str = Field(..., description="事件类型")
    summary: str = Field(..., description="事件摘要")
    resource: PayPalResource = Field(..., description="资源对象")
    links: List[PayPalLink] = Field(..., description="事件相关链接")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class PayPalAddress(BaseModel):
    country_code: str = Field(..., description="国家代码")
    address_line_1: Optional[str] = Field(None, description="地址行1")
    admin_area_1: Optional[str] = Field(None, description="省/州")
    admin_area_2: Optional[str] = Field(None, description="城市")
    postal_code: Optional[str] = Field(None, description="邮政编码")


class PayPalName(BaseModel):
    given_name: Optional[str] = Field(None, description="名")
    surname: Optional[str] = Field(None, description="姓")
    full_name: Optional[str] = Field(None, description="全名")


class PayPalPayer(BaseModel):
    address: PayPalAddress = Field(..., description="地址")
    email_address: str = Field(..., description="邮箱地址")
    name: PayPalName = Field(..., description="姓名")
    payer_id: str = Field(..., description="支付者ID")


class PayPalPayPalSource(BaseModel):
    account_id: str = Field(..., description="账户ID")
    account_status: str = Field(..., description="账户状态")
    address: PayPalAddress = Field(..., description="地址")
    email_address: str = Field(..., description="邮箱地址")
    name: PayPalName = Field(..., description="姓名")


class PayPalPaymentSource(BaseModel):
    paypal: PayPalPayPalSource = Field(..., description="PayPal支付源")


class PayPalShipping(BaseModel):
    address: PayPalAddress = Field(..., description="地址")
    name: PayPalName = Field(..., description="姓名")


class PayPalCapture(BaseModel):
    amount: PayPalAmount = Field(..., description="金额")
    create_time: datetime = Field(..., description="创建时间")
    final_capture: bool = Field(..., description="是否为最终捕获")
    id: str = Field(..., description="捕获ID")
    links: List[PayPalLink] = Field(..., description="相关链接")
    seller_protection: PayPalSellerProtection = Field(..., description="卖家保护")
    seller_receivable_breakdown: PayPalSellerReceivableBreakdown = Field(..., description="卖家收款明细")
    status: str = Field(..., description="状态")
    update_time: datetime = Field(..., description="更新时间")


class PayPalPayments(BaseModel):
    captures: List[PayPalCapture] = Field(..., description="捕获列表")


class PayPalPurchaseUnit(BaseModel):
    payments: PayPalPayments = Field(..., description="支付信息")
    reference_id: str = Field(..., description="参考ID")
    shipping: PayPalShipping = Field(..., description="配送信息")


class PayPalCaptureOrderResponse(BaseModel):
    """PayPal捕获订单响应DTO"""
    id: str = Field(..., description="PayPal订单ID")
    links: List[PayPalLink] = Field(..., description="操作链接列表")
    payer: PayPalPayer = Field(..., description="支付人信息")
    payment_source: PayPalPaymentSource = Field(..., description="支付来源")
    purchase_units: List[PayPalPurchaseUnit] = Field(..., description="购买单元列表")
    status: str = Field(..., description="订单状态")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }