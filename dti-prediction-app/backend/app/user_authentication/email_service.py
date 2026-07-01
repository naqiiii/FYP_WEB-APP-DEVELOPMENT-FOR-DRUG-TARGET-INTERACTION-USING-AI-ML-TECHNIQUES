# Email Service for sending verification and password reset emails

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import traceback
from app.settings import SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, FRONTEND_URL

def is_email_configured() -> bool:
    """Returns True if real SMTP credentials are provided in .env"""
    return bool(SMTP_USERNAME and SMTP_PASSWORD and SMTP_USERNAME != "your-email@gmail.com")

def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Sends an email using standard smtplib.
    Returns True if successful, False if failed.
    """
    # If SMTP is not fully configured, just print to console for development
    if not SMTP_USERNAME or not SMTP_PASSWORD or SMTP_USERNAME == "your-email@gmail.com":
        print(f"\\n--- EMAIL STUB ---")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body:\\n{html_body}")
        print(f"------------------\\n")
        return True

    msg = MIMEMultipart("alternative")
    msg['Subject'] = subject
    msg['From'] = SMTP_USERNAME
    msg['To'] = to_email

    part = MIMEText(html_body, 'html')
    msg.attach(part)

    try:
        # Use explicit context if needed, but modern smtplib starttls handles defaults
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.ehlo()
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, to_email, msg.as_string())
        server.close()
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        traceback.print_exc()
        return False

def send_verification_email(to_email: str, full_name: str, token: str, client_url: str = None) -> bool:
    """Sends account verification email with a JWT token link"""
    subject = "Verify Your DTI Predict Account"
    base_url = client_url if client_url else FRONTEND_URL
    verify_link = f"{base_url}/verify-email?token={token}"
    
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #008080;">Welcome to DTI Predict!</h2>
        <p>Hi {full_name},</p>
        <p>Thank you for registering. To complete your signup and verify your email address, please click the button below:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verify_link}" style="background-color: #0d9488; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Verify Email</a>
        </div>
        <p>Or copy and paste this link into your browser:<br>
        <a href="{verify_link}" style="color: #0d9488; word-break: break-all;">{verify_link}</a></p>
        <p>This link will expire in 24 hours.</p>
        <p>If you did not create this account, you can safely ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">
        <p style="font-size: 12px; color: #777;">&copy; DTI Predict. All rights reserved.</p>
      </body>
    </html>
    """
    return send_email(to_email, subject, html)

def send_password_reset_email(to_email: str, name: str, token: str, client_url: str = None) -> bool:
    """
    Sends a password reset email with a reset link containing the token.
    """
    base_url = client_url if client_url else FRONTEND_URL
    reset_url = f"{base_url}/reset-password?token={token}"
    subject = "Reset your DTI Predict Password"
    
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #0f172a;">Password Reset Request</h2>
        <p>Hello {name},</p>
        <p>We received a request to reset the password for your DTI Predict account. If you made this request, please click the link below to set a new password:</p>
        <div style="margin: 30px 0;">
          <a href="{reset_url}" style="background-color: #0ea5e9; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Reset Password</a>
        </div>
        <p>This link will expire in 15 minutes.</p>
        <p>If you didn't request a password reset, you can safely ignore this email.</p>
        <p>Best regards,<br>The DTI Predict Team</p>
      </body>
    </html>
    """
    return send_email(to_email, subject, html_body)

def send_login_alert_email(to_email: str, name: str, ip_address: str, device_info: str) -> bool:
    """
    Sends an alert notifying the user of a successful login from a new device/IP.
    """
    from datetime import datetime
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    subject = "Security Alert: New Login to DTI Predict"
    
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #0f172a;">New Login Detected</h2>
        <p>Hello {name},</p>
        <p>Your DTI Predict account was just accessed.</p>
        <div style="background-color: #f8fafc; padding: 15px; border-radius: 5px; margin: 20px 0;">
          <p style="margin: 5px 0;"><b>Time:</b> {current_time}</p>
          <p style="margin: 5px 0;"><b>IP Address:</b> {ip_address}</p>
          <p style="margin: 5px 0;"><b>Device:</b> {device_info}</p>
        </div>
        <p>If this was you, no further action is required.</p>
        <p>If you did not authorize this login, please <a href="{FRONTEND_URL}/forgot-password">reset your password</a> immediately.</p>
        <p>Stay safe,<br>The DTI Predict Security Team</p>
      </body>
    </html>
    """
    return send_email(to_email, subject, html_body)
