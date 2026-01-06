"""Email sending utilities for authentication"""
import secrets
from datetime import datetime, timedelta
from typing import Optional
from flask import current_app, url_for
from flask_mail import Mail, Message

mail = Mail()


def generate_token() -> str:
    """Generate a secure random token for email verification or password reset"""
    return secrets.token_urlsafe(48)


def send_verification_email(to_email: str, token: str, base_url: str) -> bool:
    """
    Send email verification email.
    
    Args:
        to_email: Recipient email address
        token: Verification token
        base_url: Base URL of the application
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        verify_url = f"{base_url}/api/auth/verify/{token}"
        
        msg = Message(
            subject="Verify your YieldLife account",
            recipients=[to_email],
            body=f"""Welcome to YieldLife!

Please verify your email address by clicking the link below:

{verify_url}

This link will expire in 24 hours.

If you didn't create an account with YieldLife, you can safely ignore this email.

- The YieldLife Team
""",
            html=f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #0e8749;">YieldLife</h1>
    </div>
    
    <h2>Welcome to YieldLife!</h2>
    
    <p>Please verify your email address by clicking the button below:</p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{verify_url}" 
           style="background: #0e8749; color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; font-weight: 600;">
            Verify Email
        </a>
    </div>
    
    <p style="color: #666; font-size: 14px;">
        Or copy and paste this link into your browser:<br>
        <a href="{verify_url}" style="color: #0e8749;">{verify_url}</a>
    </p>
    
    <p style="color: #666; font-size: 14px;">This link will expire in 24 hours.</p>
    
    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
    
    <p style="color: #999; font-size: 12px;">
        If you didn't create an account with YieldLife, you can safely ignore this email.
    </p>
</body>
</html>
"""
        )
        
        mail.send(msg)
        return True
        
    except Exception as e:
        print(f"Failed to send verification email: {e}")
        return False


def send_password_reset_email(to_email: str, token: str, base_url: str) -> bool:
    """
    Send password reset email.
    
    Args:
        to_email: Recipient email address
        token: Reset token
        base_url: Base URL of the application
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        reset_url = f"{base_url}/reset-password/{token}"
        
        msg = Message(
            subject="Reset your YieldLife password",
            recipients=[to_email],
            body=f"""Password Reset Request

You requested to reset your YieldLife password. Click the link below to set a new password:

{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.

- The YieldLife Team
""",
            html=f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #0e8749;">YieldLife</h1>
    </div>
    
    <h2>Password Reset Request</h2>
    
    <p>You requested to reset your YieldLife password. Click the button below to set a new password:</p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{reset_url}" 
           style="background: #0e8749; color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; font-weight: 600;">
            Reset Password
        </a>
    </div>
    
    <p style="color: #666; font-size: 14px;">
        Or copy and paste this link into your browser:<br>
        <a href="{reset_url}" style="color: #0e8749;">{reset_url}</a>
    </p>
    
    <p style="color: #666; font-size: 14px;">This link will expire in 1 hour.</p>
    
    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
    
    <p style="color: #999; font-size: 12px;">
        If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.
    </p>
</body>
</html>
"""
        )
        
        mail.send(msg)
        return True
        
    except Exception as e:
        print(f"Failed to send password reset email: {e}")
        return False


def send_email_added_notification(to_email: str, base_url: str) -> bool:
    """
    Send notification when email is added to a wallet account.
    
    Args:
        to_email: Recipient email address
        base_url: Base URL of the application
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        msg = Message(
            subject="Email added to your YieldLife account",
            recipients=[to_email],
            body=f"""Email Added Successfully

An email address has been added to your YieldLife wallet account.

You can now receive notifications and recover your account if needed.

If you didn't add this email, please contact support immediately.

- The YieldLife Team
""",
            html=f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #0e8749;">YieldLife</h1>
    </div>
    
    <h2>Email Added Successfully</h2>
    
    <p>An email address has been added to your YieldLife wallet account.</p>
    
    <p>You can now receive notifications and recover your account if needed.</p>
    
    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
    
    <p style="color: #999; font-size: 12px;">
        If you didn't add this email, please contact support immediately.
    </p>
</body>
</html>
"""
        )
        
        mail.send(msg)
        return True
        
    except Exception as e:
        print(f"Failed to send email added notification: {e}")
        return False

