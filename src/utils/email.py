import smtplib
import ssl
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import List, Optional
import traceback

from ..config.config import settings
from ..config.log_config import logger


class EmailSender:
    def __init__(self):
        self.host = settings.smtp.host
        self.port = settings.smtp.port
        self.username = settings.smtp.username
        self.password = settings.smtp.password
        self.from_name = settings.smtp.from_name
        self.timeout = 10  # 设置10秒超时
        self.context = ssl.create_default_context()  # 创建SSL上下文
        self.context.check_hostname = False
        self.context.verify_mode = ssl.CERT_NONE

    def send_email(
        self,
        to_addresses: List[str],
        subject: str,
        body: str,
        html: bool = True,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None
    ) -> bool:
        """
        发送邮件
        :param to_addresses: 收件人列表
        :param subject: 邮件主题
        :param body: 邮件内容
        :param html: 是否为HTML格式
        :param cc_addresses: 抄送列表
        :param bcc_addresses: 密送列表
        :return: 是否发送成功
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = formataddr((self.from_name, self.username))
            msg['To'] = ', '.join(to_addresses)
            msg['Subject'] = subject

            if cc_addresses:
                msg['Cc'] = ', '.join(cc_addresses)
            if bcc_addresses:
                msg['Bcc'] = ', '.join(bcc_addresses)

            # 设置邮件内容
            content_type = 'html' if html else 'plain'
            msg.attach(MIMEText(body, content_type, 'utf-8'))

            # 使用SSL连接SMTP服务器
            with smtplib.SMTP_SSL(self.host, self.port, context=self.context, timeout=self.timeout) as server:
                server.login(self.username, self.password)
                
                # 合并所有收件人
                all_recipients = to_addresses.copy()
                if cc_addresses:
                    all_recipients.extend(cc_addresses)
                if bcc_addresses:
                    all_recipients.extend(bcc_addresses)
                
                # 发送邮件
                server.sendmail(
                    self.username,
                    all_recipients,
                    msg.as_string()
                )
                
                # 增加详细日志
                logger.info(
                    "Email sent successfully. Details: \n"
                    f"To: {to_addresses}\n"
                    f"Subject: {subject}\n"
                    f"CC: {cc_addresses or 'None'}\n"
                    f"BCC: {bcc_addresses or 'None'}\n"
                    f"Content: {body[:500]}{'...' if len(body) > 500 else ''}"  # 记录前500个字符
                )
                return True

        except smtplib.SMTPConnectError as e:
            logger.error(f"Failed to connect to SMTP server: {str(e)}")
            return False
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {str(e)}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error occurred: {str(e)}")
            return False
        except Exception as e:
            # 记录失败详情
            stack_trace = traceback.format_exc()
            logger.error(
                f"Failed to send email. Error: {str(e)}\n"
                f"To: {to_addresses}\n"
                f"Subject: {subject}\n"
                f"Stack Trace: {stack_trace}"
            )
            return False

    def send_verification_email(self, to_address: str, verification_code: str, user_id: int) -> bool:
        """
        发送验证码邮件
        :param to_address: 收件人邮箱
        :param verification_code: 验证码
        :param user_id: 用户ID
        :return: 是否发送成功
        """
        verification_url = f"https://www.creamoda.ai/verify-email?code={verification_code}"
        subject = "Verify Your Email Address"
        body = f"""
        <html>
            <body>
                <h2>Welcome to Creamoda!</h2>
                <p>Please click the link below to verify your email address:</p>
                <p><a href="{verification_url}">{verification_url}</a></p>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't create an account with us, please ignore this email.</p>
            </body>
        </html>
        """
        return self.send_email([to_address], subject, body)

    async def send_email_async(
        self,
        to_addresses: List[str],
        subject: str,
        body: str,
        html: bool = True,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None
    ) -> bool:
        """异步发送邮件"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, 
            lambda: self.send_email(to_addresses, subject, body, html, cc_addresses, bcc_addresses)
        )

    async def send_verification_email_async(self, to_address: str, verification_code: str, user_id: int) -> bool:
        """异步发送验证码邮件
        :param to_address: 收件人邮箱
        :param verification_code: 验证码
        :param user_id: 用户ID
        :return: 是否发送成功
        """
        subject = "Verify Your Email Address"
        body = f"""
        <html>
            <body>
                <h2>Welcome to Creamoda!</h2>
                <p>Your verification code is: <strong>{verification_code}</strong></p>
                <p>This code will expire in 10 minutes.</p>
                <p>If you didn't create an account with us, please ignore this email.</p>
            </body>
        </html>
        """
        return await self.send_email_async([to_address], subject, body)


# 创建全局邮件发送器实例
email_sender = EmailSender() 