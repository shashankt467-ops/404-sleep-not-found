import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import threading
from app.core.config import settings

logger = logging.getLogger(__name__)

def send_otp_email_sync(recipient_email: str, patient_name: str, patient_id: str, otp_code: str) -> bool:
    if not settings.SMTP_USER:
        return False

    target_email = recipient_email.strip() if recipient_email else settings.DEFAULT_PATIENT_EMAIL
    if not target_email or '@' not in target_email:
        target_email = settings.DEFAULT_PATIENT_EMAIL

    subject = f"HEALIX Patient Portal Verification Code: {otp_code}"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; background-color: #050914; color: #E9F0F3; margin: 0; padding: 24px;">
  <div style="max-width: 520px; margin: 0 auto; background: #0A1428; border: 1px solid rgba(0,240,255,0.3); border-radius: 12px; padding: 32px;">
    <div style="border-bottom: 1px solid rgba(0,240,255,0.2); padding-bottom: 14px; margin-bottom: 20px;">
      <div style="font-size: 20px; font-weight: 800; color: #00F0FF; letter-spacing: 1px;">HEALIX EMERGENCY NETWORK</div>
      <div style="font-size: 11px; color: #8FADC4; margin-top: 2px;">ZERO-TRUST PATIENT ACCESS PORTAL</div>
    </div>
    <p style="font-size: 14px; color: #E9F0F3;">Hello <strong>{patient_name}</strong>,</p>
    <p style="font-size: 13px; color: #CBD8E0; line-height: 1.5;">You requested access to your personal emergency health records and clinical visit summary on the HEALIX interoperability portal.</p>
    <div style="background: rgba(0,240,255,0.06); border: 1px dashed #00F0FF; border-radius: 8px; text-align: center; padding: 20px; margin: 20px 0;">
      <div style="font-size: 12px; color: #8FADC4; text-transform: uppercase; margin-bottom: 8px; font-weight: 600;">Your 6-Digit One-Time Passcode (OTP)</div>
      <div style="font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #39FF9A; font-family: monospace;">{otp_code}</div>
      <div style="font-size: 11px; color: #FFB020; margin-top: 8px;">Valid for 10 minutes · Do not share this code</div>
    </div>
    <p style="font-size: 12px; color: #8FADC4;">Patient ID: <strong style="color: #00F0FF; font-family: monospace;">{patient_id}</strong></p>
    <div style="margin-top: 24px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.1); font-size: 11px; color: #64748b; line-height: 1.5;">
      This is an automated clinical security notification. If you did not request this OTP, someone may have entered your Patient ID by mistake. Your medical records remain encrypted and protected under Zero-Trust access control.
    </div>
  </div>
</body>
</html>"""

    text_content = f'''HEALIX EMERGENCY HEALTHCARE NETWORK
Zero-Trust Patient Portal Verification

Hello {patient_name},

Your 6-digit one-time verification passcode is:
{otp_code}

This code is valid for 10 minutes for Patient ID: {patient_id}.
If you did not request this code, please disregard this email.
'''

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    msg['To'] = target_email

    msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=12)
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, [target_email], msg.as_string())
        server.quit()
        logger.info(f'OTP email sent successfully to {target_email} for patient {patient_id}')
        return True
    except Exception as e:
        logger.error(f'FAILTO SEND OTP EMAIL: {e}')
        return False

def send_otp_email_async(recipient_email: str, patient_name: str, patient_id: str, otp_code: str):
    t = threading.Thread(
        target=send_otp_email_sync,
        args=(recipient_email, patient_name, patient_id, otp_code),
        daemon=True
    )
    t.start()
