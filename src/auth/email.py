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


def send_welcome_newsletter_email(to_email: str, base_url: str) -> bool:
    """
    Send welcome email when a user subscribes to the monthly newsletter.

    Args:
        to_email: Recipient email address
        base_url: Base URL of the application

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        msg = Message(
            subject="Welcome to the YieldLife Newsletter!",
            recipients=[to_email],
            body=f"""Welcome to the YieldLife Newsletter!

Thanks for subscribing to our monthly newsletter. Here's what you can expect:

- Monthly updates on Cardano DeFi yields and trends
- New protocol listings and feature announcements
- Tips for optimizing your DeFi portfolio

Visit YieldLife anytime at {base_url}

If you didn't subscribe, you can ignore this email.

- The YieldLife Team
""",
            html=f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 30px;">
        <img src="{base_url}/static/YieldLife_Logo_tp_560x560.png" alt="YieldLife" width="200" height="200">
    </div>

    <h2 style="text-align: center;">Welcome to YieldLife!</h2>

    <p>Thanks for subscribing to our monthly newsletter. Here's what you can expect:</p>

    <ul style="line-height: 1.8;">
        <li>Monthly updates on Cardano DeFi yields and trends</li>
        <li>New protocol listings and feature announcements</li>
        <li>Tips for optimizing your DeFi portfolio</li>
    </ul>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{base_url}"
           style="background: #0e8749; color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; font-weight: 600;">
            Visit YieldLife
        </a>
    </div>

    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

    <p style="color: #999; font-size: 12px;">
        If you didn't subscribe to the YieldLife newsletter, you can ignore this email.
    </p>
</body>
</html>
"""
        )

        mail.send(msg)
        return True

    except Exception as e:
        print(f"Failed to send welcome newsletter email: {e}")
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


def send_newsletter_email(to_email: str, base_url: str, subject: str,
                          intro: str, updates: list[dict], cta_text: str = "Check It Out",
                          month_label: str = "",
                          banner_image: str = "dramatic-skies-leah-may.jpg",
                          photo_credit_url: str = "",
                          notable_events: list[dict] | None = None) -> bool:
    """
    Send a monthly newsletter email.

    Args:
        to_email: Recipient email address
        base_url: Base URL of the application
        subject: Email subject line
        intro: Intro paragraph text
        updates: List of dicts with 'icon' (html entity), 'title', and 'description'
        cta_text: Call-to-action button text
        month_label: Date subtitle shown under the Monthly Update heading
        banner_image: Filename of the banner image in /static/
        photo_credit_url: URL for photo credit link shown below the banner (optional)

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Build plain text
        plain_updates = "\n".join(
            f"- {u['title']} — {u['description']}" for u in updates
        )
        plain_notable = ""
        if notable_events:
            plain_notable = "\n\nNotable Events\n" + "\n".join(
                f"- {e['title']} — {e['description']}" for e in notable_events
            )

        plain_body = f"""{intro}

{plain_updates}{plain_notable}

Visit {base_url} to check it out.
Follow @yieldlife_xyz on X for updates between newsletters.

- The YieldLife Team
"""

        # Build optional photo credit row
        photo_credit_row = ""
        if photo_credit_url:
            photo_credit_row = f"""<tr>
                        <td align="right" style="padding: 4px 12px 0;">
                            <a href="{photo_credit_url}" style="color: #aaa; font-size: 11px; text-decoration: none;">Photo credit</a>
                        </td>
                    </tr>"""

        # Build optional notable events section
        notable_events_section = ""
        if notable_events:
            event_rows = ""
            for e in notable_events:
                image_row = ""
                if e.get('image'):
                    image_row = f"""
                    <tr>
                        <td style="padding: 0 40px 12px; line-height: 0;">
                            <img src="{base_url}/static/{e['image']}" alt="" width="520" style="display: block; width: 100%; height: auto; border-radius: 8px; border: none;">
                        </td>
                    </tr>"""
                event_rows += f"""
                    <tr>
                        <td style="padding: 0 40px 4px;">
                            <p style="margin: 0 0 2px; font-weight: 600; color: #1a1a2e; font-size: 15px;">{e['title']}</p>
                            <p style="margin: 0 0 10px; color: #555; font-size: 14px; line-height: 1.6;">{e['description']}</p>
                        </td>
                    </tr>{image_row}"""
            notable_events_section = f"""
                    <!-- Divider -->
                    <tr>
                        <td style="padding: 0 40px;">
                            <div style="border-top: 1px solid #e8e4dc; margin: 8px 0 16px;"></div>
                        </td>
                    </tr>

                    <!-- Notable events heading -->
                    <tr>
                        <td style="padding: 8px 40px 20px;">
                            <h2 style="color: #1a1a2e; font-size: 20px; font-weight: 700; margin: 0;">Notable Events</h2>
                        </td>
                    </tr>
{event_rows}"""

        # Build HTML update rows
        update_rows = ""
        for u in updates:
            update_rows += f"""
                    <tr>
                        <td style="padding: 0 40px 24px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td width="40" valign="top" style="padding-top: 2px;">
                                        <div style="width: 32px; height: 32px; background: #0e8749; border-radius: 8px; text-align: center; line-height: 32px; font-size: 16px;">{u['icon']}</div>
                                    </td>
                                    <td style="padding-left: 12px;">
                                        <p style="margin: 0 0 4px; font-weight: 600; color: #1a1a2e; font-size: 15px;">{u['title']}</p>
                                        <p style="margin: 0; color: #555; font-size: 14px; line-height: 1.6;">{u['description']}</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>"""

        html_body = f"""
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f5f1eb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f1eb;">
        <tr>
            <td align="center" style="padding: 40px 20px;">

                <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">

                    <!-- Logo + tagline -->
                    <tr>
                        <td style="padding: 24px 40px 16px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td width="100" valign="middle">
                                        <img src="{base_url}/static/YieldLife_Logo_tp_560x560.png" alt="YieldLife" width="100" height="100" style="display: block; border: none;">
                                    </td>
                                    <td valign="middle" style="padding-left: 20px;">
                                        <p style="margin: 0; font-size: 13px; color: #666; line-height: 1.6;">Cardano DeFi analytics &mdash; tracking historical APYs across Minswap, SundaeSwap, WingRiders, and Liqwid.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Banner photo -->
                    <tr>
                        <td style="padding: 0; line-height: 0;">
                            <img src="{base_url}/static/{banner_image}" alt="" width="600" style="display: block; width: 100%; height: auto; border: none;">
                        </td>
                    </tr>
                    {photo_credit_row}

                    <!-- Title -->
                    <tr>
                        <td align="center" style="padding: 24px 40px 8px;">
                            <h1 style="color: #1a1a2e; font-size: 28px; font-weight: 700; margin: 0 0 4px; letter-spacing: -0.5px;">Monthly Update</h1>
                            <p style="color: #555; font-size: 14px; margin: 0;">{month_label}</p>
                        </td>
                    </tr>

                    <!-- Intro -->
                    <tr>
                        <td style="padding: 32px 40px 16px;">
                            <p style="color: #333; font-size: 15px; line-height: 1.7; margin: 0;">{intro}</p>
                        </td>
                    </tr>

                    <!-- Divider -->
                    <tr>
                        <td style="padding: 0 40px;">
                            <div style="border-top: 1px solid #e8e4dc; margin: 16px 0;"></div>
                        </td>
                    </tr>

                    <!-- Section heading -->
                    <tr>
                        <td style="padding: 8px 40px 20px;">
                            <h2 style="color: #1a1a2e; font-size: 20px; font-weight: 700; margin: 0;">What's New</h2>
                        </td>
                    </tr>

                    <!-- Update items -->
{update_rows}
{notable_events_section}
                    <!-- CTA -->
                    <tr>
                        <td align="center" style="padding: 8px 40px 32px;">
                            <a href="{base_url}" style="display: inline-block; background: #0e8749; color: #ffffff; padding: 14px 36px; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px;">{cta_text}</a>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f7f3; padding: 24px 40px; border-top: 1px solid #e8e4dc;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center">
                                        <p style="margin: 0 0 8px; color: #888; font-size: 13px;">
                                            Follow us on <a href="https://x.com/yieldlife_xyz" style="color: #0e8749; text-decoration: none; font-weight: 600;">@yieldlife_xyz</a>
                                        </p>
                                        <p style="margin: 0; color: #aaa; font-size: 12px;">
                                            You're receiving this because you signed up at yieldlife.xyz
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>

            </td>
        </tr>
    </table>

</body>
</html>
"""

        msg = Message(
            subject=subject,
            recipients=[to_email],
            body=plain_body,
            html=html_body
        )

        mail.send(msg)
        return True

    except Exception as e:
        print(f"Failed to send newsletter email: {e}")
        return False

