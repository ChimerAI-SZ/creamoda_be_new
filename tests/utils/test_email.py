import unittest
from unittest.mock import MagicMock, patch

from src.utils.email import EmailSender

class TestEmailSender(unittest.TestCase):
    @patch('smtplib.SMTP', autospec=True)
    def test_send_verification_email(self, mock_smtp):
        # 配置mock
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance

        email_sender = EmailSender()

        # 测试发送验证邮件
        result = email_sender.send_verification_email(
            to_address="rick.yliu@foxmail.com",
            verification_code="test123",
            user_id=1
        )

        # 验证结果
        self.assertTrue(result)
        mock_smtp_instance.sendmail.assert_called_once()
        
        # 验证邮件内容包含验证码
        send_args = mock_smtp_instance.sendmail.call_args[0]
        self.assertIn("test123", send_args[2])

if __name__ == '__main__':
    unittest.main() 