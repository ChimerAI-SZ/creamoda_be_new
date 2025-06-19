import time
import os
from typing import Any, Dict
import requests

from src.config.log_config import logger
from src.dto.paypal import PayPalCaptureOrderResponse, PayPalOrderResponse
from src.exceptions.pay import PayError
from src.config.config import settings


class PayPalClient:
    def __init__(self):
        self.client_id = settings.paypal.paypal_client_id
        self.client_secret = settings.paypal.paypal_secret
        self.webhook_id = settings.paypal.webhook_id
        self.api_base = settings.paypal.paypal_base_url
        self._access_token = None
        self._token_expiry = 0

    def get_access_token(self) -> str:
        """获取 PayPal API 访问令牌"""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        auth = (self.client_id, self.client_secret)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = 'grant_type=client_credentials'
        
        response = requests.post(
            f'{self.api_base}/v1/oauth2/token',
            headers=headers,
            data=data,
            auth=auth
        )
        
        if response.status_code != 200:
            raise PayError(message=f"get paypal access token failed")
        
        token_data = response.json()
        self._access_token = token_data['access_token']
        self._token_expiry = time.time() + token_data.get("expires_in", 3600) - 60
        return self._access_token

    def create_order(self, amount, currency='USD'):
        """创建 PayPal 订单"""
        try:
            access_token = self.get_access_token()
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}',
                'PayPal-Request-Id': os.urandom(16).hex()  # 可选请求ID
            }
            
            data = {
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'amount': {
                        'currency_code': currency,
                        'value': str(amount)
                    }
                }],
                'application_context': {
                    'return_url': settings.paypal.return_url,
                    'cancel_url': settings.paypal.cancel_url,
                    'brand_name': 'Creamoda',
                    'user_action': 'PAY_NOW'
                }
            }
            
            response = requests.post(
                f'{self.api_base}/v2/checkout/orders',
                headers=headers,
                json=data
            )
            
            if response.status_code != 201:
                raise Exception(f"创建订单失败: {response.text}")
            
            # 将响应转换为 PayPalOrderResponse 类型
            logger.info(f"创建订单成功: {response.json()}")
            return PayPalOrderResponse(**response.json())
        except Exception as e:
            logger.error(f"创建订单失败: {e}")
            raise PayError(message=f"create paypal order failed")

    def capture_payment(self, order_id):
        """捕获 PayPal 订单支付"""
        access_token = self.get_access_token()
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.post(
            f'{self.api_base}/v2/checkout/orders/{order_id}/capture',
            headers=headers
        )

        logger.info(f"捕获支付响应: {response.json()}")
        
        if response.status_code != 201:
            raise PayError(f"paypal payment failed")
        
        logger.info(f"捕获支付成功: {response.json()}")
        return PayPalCaptureOrderResponse(**response.json())

    def verify_webhook(self, headers, body):
        """验证 PayPal Webhook 签名"""
        access_token = self.get_access_token()
        
        verification_data = {
            'transmission_id': headers.get('PAYPAL-TRANSMISSION-ID'),
            'transmission_time': headers.get('PAYPAL-TRANSMISSION-TIME'),
            'cert_url': headers.get('PAYPAL-CERT-URL'),
            'auth_algo': headers.get('PAYPAL-AUTH-ALGO'),
            'transmission_sig': headers.get('PAYPAL-TRANSMISSION-SIG'),
            'webhook_id': self.webhook_id,
            'webhook_event': body
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.post(
            f'{self.api_base}/v1/notifications/verify-webhook-signature',
            headers=headers,
            json=verification_data
        )
        
        if response.status_code != 200:
            return False
        
        return response.json().get('verification_status') == 'SUCCESS'
    
    def create_product(self, name: str, description: str, category: str = "SOFTWARE") -> Dict[str, Any]:
        """
        Create a product for subscriptions.
        Returns the JSON response containing 'id' (product_id).
        """
        url = f"{self.api_base}/v1/catalogs/products"
        payload = {
            "name": name,
            "description": description,
            "type": "SERVICE",
            "category": category
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.get_access_token()}'
        }
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()
    
    def create_plan(self,
                    product_id: str,
                    plan_name: str,
                    price: float,
                    currency: str = "USD",
                    interval_unit: str = "MONTH",
                    interval_count: int = 1,
                    total_cycles: int = 0) -> Dict[str, Any]:
        """
        Create a billing plan for the given product.
        total_cycles=0 means infinite recurring charges.
        """
        url = f"{self.api_base}/v1/billing/plans"
        payload = {
            "product_id": product_id,
            "name": plan_name,
            "billing_cycles": [
                {
                    "frequency": {"interval_unit": interval_unit,
                                  "interval_count": interval_count},
                    "tenure_type": "REGULAR",
                    "sequence": 1,
                    "total_cycles": total_cycles,
                    "pricing_scheme": {
                        "fixed_price": {"value": f"{price:.2f}",
                                         "currency_code": currency}
                    }
                }
            ],
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "setup_fee": {"value": "0", "currency_code": currency},
                "payment_failure_threshold": 3
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.get_access_token()}'
        }
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()
    
    def create_subscription(self,
                            plan_id: str,
                            brand_name: str = "CREAMODA") -> Dict[str, Any]:
        """
        Create a subscription and return approval URL and subscription ID.
        User will be redirected to approval_url to authorize.
        """
        url = f"{self.api_base}/v1/billing/subscriptions"
        payload = {
            "plan_id": plan_id,
            "application_context": {
                "brand_name": brand_name,
                "return_url": settings.paypal.return_url,
                "cancel_url": settings.paypal.cancel_url,
                "user_action": "SUBSCRIBE_NOW"
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.get_access_token()}'
        }
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        approval_url = next((link['href'] for link in data.get('links', [])
                             if link.get('rel') == 'approve'), None)
        return {"approval_url": approval_url,
                "subscription_id": data.get('id'),
                **data}
    
    def get_subscription_details(self, subscription_id):
        """
        获取订阅详情
        """
        url = f"{self.api_base}/v1/billing/subscriptions/{subscription_id}"
        headers = {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        status = data["status"]
        next_billing_time = data.get("billing_info", {}).get("next_billing_time")
        return {"status": status, "next_billing_time": next_billing_time, **data}
    
    def cancel_subscription(self,
                             subscription_id: str,
                             reason: str = "User requested cancellation") -> bool:
        """
        Cancel an active subscription.
        Returns True if cancellation succeeded.
        """
        url = f"{self.api_base}/v1/billing/subscriptions/{subscription_id}/cancel"
        payload = {"reason": reason}
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.get_access_token()}'
        }
        resp = requests.post(url, headers=headers, json=payload)
        if resp.status_code == 204:
            return True
        resp.raise_for_status()
        return False

paypal_client = PayPalClient()