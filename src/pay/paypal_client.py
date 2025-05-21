import os
import requests

from src.dto.paypal import PayPalCaptureOrderResponse, PayPalOrderResponse

PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.getenv('PAYPAL_SECRET')
PAYPAL_BASE_URL = os.getenv('PAYPAL_BASE_URL')
WEBHOOK_ID = os.getenv('WEBHOOK_ID')


class PayPalClient:
    @staticmethod
    def get_access_token():
        """获取 PayPal API 访问令牌"""
        auth = (PAYPAL_CLIENT_ID, PAYPAL_SECRET)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = 'grant_type=client_credentials'
        
        response = requests.post(
            f'{PAYPAL_BASE_URL}/v1/oauth2/token',
            headers=headers,
            data=data,
            auth=auth
        )
        
        if response.status_code != 200:
            raise Exception(f"获取访问令牌失败: {response.text}")
        
        return response.json()['access_token']

    @staticmethod
    def create_order(amount, currency='USD'):
        """创建 PayPal 订单"""
        access_token = PayPalClient.get_access_token()
        
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
                'return_url': 'https://paypay.creamoda.ai/return',
                'cancel_url': 'https://paypay.creamoda.ai/cancel',
                'brand_name': 'Your Brand Name',
                'user_action': 'PAY_NOW'
            }
        }
        
        response = requests.post(
            f'{PAYPAL_BASE_URL}/v2/checkout/orders',
            headers=headers,
            json=data
        )
        
        if response.status_code != 201:
            raise Exception(f"创建订单失败: {response.text}")
        
        # 将响应转换为 PayPalOrderResponse 类型
        return PayPalOrderResponse(**response.json())

    @staticmethod
    def capture_payment(order_id):
        """捕获 PayPal 订单支付"""
        access_token = PayPalClient.get_access_token()
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.post(
            f'{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture',
            headers=headers
        )
        
        if response.status_code != 201:
            raise Exception(f"捕获支付失败: {response.text}")
        
        return PayPalCaptureOrderResponse(**response.json())

    @staticmethod
    def verify_webhook(headers, body):
        """验证 PayPal Webhook 签名"""
        access_token = PayPalClient.get_access_token()
        
        verification_data = {
            'transmission_id': headers.get('PAYPAL-TRANSMISSION-ID'),
            'transmission_time': headers.get('PAYPAL-TRANSMISSION-TIME'),
            'cert_url': headers.get('PAYPAL-CERT-URL'),
            'auth_algo': headers.get('PAYPAL-AUTH-ALGO'),
            'transmission_sig': headers.get('PAYPAL-TRANSMISSION-SIG'),
            'webhook_id': WEBHOOK_ID,
            'webhook_event': body
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.post(
            f'{PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature',
            headers=headers,
            json=verification_data
        )
        
        if response.status_code != 200:
            return False
        
        return response.json().get('verification_status') == 'SUCCESS'
