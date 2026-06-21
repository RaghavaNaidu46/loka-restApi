import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

def _sendSmtpEmailSync(toEmail: str, subject: str, htmlContent: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.emailFrom
    msg["To"] = toEmail

    part = MIMEText(htmlContent, "html")
    msg.attach(part)

    # Connect to Office365 SMTP server
    with smtplib.SMTP(settings.smtpHost, settings.smtpPort) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.smtpUser, settings.smtpPass)
        server.sendmail(settings.emailFrom, toEmail, msg.as_string())

async def sendEmail(toEmail: str, subject: str, htmlContent: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _sendSmtpEmailSync, toEmail, subject, htmlContent)

def getOtpEmailTemplate(otpCode: str) -> str:
    # A beautiful, clean, modern, and professional civic-branded HTML template
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Loka Verification Code</title>
        <style>
            body {{
                font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background-color: #F7F7F8;
                margin: 0;
                padding: 0;
                color: #111418;
            }}
            .container {{
                max-width: 500px;
                margin: 40px auto;
                background: #FFFFFF;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 4px 12px rgba(17, 20, 24, 0.05);
                border: 1px solid #E6E8EB;
            }}
            .header {{
                background-color: #23618C;
                padding: 32px;
                text-align: center;
            }}
            .header h1 {{
                color: #FFFFFF;
                margin: 0;
                font-size: 28px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            .body {{
                padding: 40px 32px;
            }}
            .greeting {{
                font-size: 16px;
                line-height: 24px;
                margin-bottom: 24px;
                color: #5C6470;
            }}
            .otp-container {{
                background-color: #F0F4F8;
                border-radius: 12px;
                padding: 24px;
                text-align: center;
                margin: 32px 0;
                border: 1px solid #D6DFE6;
            }}
            .otp-code {{
                font-family: 'Courier New', Courier, monospace;
                font-size: 36px;
                font-weight: 700;
                color: #23618C;
                letter-spacing: 6px;
                margin: 0;
            }}
            .instructions {{
                font-size: 14px;
                line-height: 20px;
                color: #889099;
                margin-top: 24px;
            }}
            .footer {{
                background-color: #F7F7F8;
                padding: 24px 32px;
                text-align: center;
                border-top: 1px solid #E6E8EB;
                font-size: 12px;
                color: #889099;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Loka</h1>
            </div>
            <div class="body">
                <div class="greeting">
                    Hello,<br>
                    Welcome to Loka. Please use the following one-time code to complete your verification and sign in.
                </div>
                <div class="otp-container">
                    <div class="otp-code">{otpCode}</div>
                </div>
                <div class="instructions">
                    This verification code is valid for 5 minutes. If you did not request this code, please ignore this email.
                </div>
            </div>
            <div class="footer">
                One Citizen. One Voice.<br>
                &copy; 2026 Loka civic participation platform. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """
