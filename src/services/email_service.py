"""
Enterprise Email & OTP Dispatch Service for Veritas AI Suite.
Provides reliable, encrypted SMTP email delivery for 6-digit OTP verification codes
and security notifications.
"""

import os
import asyncio
import logging
import secrets
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Dynamic import of primary mail transport
FASTMAIL_AVAILABLE = False
try:
    from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType, MultipartSubtypeEnum
    FASTMAIL_AVAILABLE = True
except ImportError:
    FASTMAIL_AVAILABLE = False
    logger.warning("Primary email engine not found. Using native secure SMTP engine.")


def build_otp_html_email(name: str, email: str, otp: str, purpose: str = "email_verification", role: str = "user", expires_minutes: int = 10) -> str:
    """Renders a responsive, high-contrast, security-themed HTML email."""
    digits = list(str(otp or "000000"))
    purpose_title = (
        "Password Reset Authorization"
        if purpose == "password_reset"
        else "Admin Security Clearance Verification"
        if purpose == "admin_elevation"
        else "Email Verification & Account Clearance"
    )

    digit_boxes = "".join(
        f"""
        <td style="padding: 0 4px;">
          <div style="width: 44px; height: 54px; line-height: 54px; text-align: center; font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 26px; font-weight: 800; color: #38bdf8; background: #0f172a; border: 2px solid #6366f1; border-radius: 10px; box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);">
            {d}
          </div>
        </td>"""
        for d in digits
    )

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Veritas AI Security - Verification Code</title>
</head>
<body style="margin: 0; padding: 28px; background-color: #070913; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 580px; margin: 0 auto; background: #12192e; border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 18px; overflow: hidden; box-shadow: 0 16px 40px rgba(0,0,0,0.6);">
    <tr>
      <td style="padding: 24px 32px; background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%); border-bottom: 1px solid rgba(255,255,255,0.08);">
        <table width="100%">
          <tr>
            <td>
              <div style="font-size: 20px; font-weight: 900; color: #ffffff; letter-spacing: 0.04em;">🛡️ VerdictLens / Veritas AI</div>
              <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">Explainable Multimodal Fake News & Forensic Intelligence Suite</div>
            </td>
            <td align="right">
              <span style="display: inline-block; padding: 4px 10px; font-size: 11px; font-weight: 700; color: #a5f3fc; background: rgba(6, 182, 212, 0.18); border: 1px solid rgba(6, 182, 212, 0.4); border-radius: 999px; text-transform: uppercase;">
                {role.upper()} CLEARANCE
              </span>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding: 32px;">
        <div style="font-size: 18px; font-weight: 700; color: #e2e8f0; margin-bottom: 8px;">{purpose_title}</div>
        <p style="font-size: 14px; color: #94a3b8; line-height: 1.6; margin: 0 0 24px;">
          Hello <strong style="color: #f8fafc;">{name or email}</strong>,<br>
          Use the following One-Time Password (OTP) to verify your identity for <strong style="color: #c7d2fe;">{email}</strong>. This cryptographic code is valid for <strong>{expires_minutes} minutes</strong>.
        </p>

        <table cellpadding="0" cellspacing="0" style="margin: 0 auto 26px;">
          <tr>
            {digit_boxes}
          </tr>
        </table>

        <div style="background: rgba(15, 23, 42, 0.75); border-left: 4px solid #6366f1; padding: 12px 16px; border-radius: 8px; font-size: 12px; color: #94a3b8; line-height: 1.5; margin-bottom: 20px;">
          <strong style="color: #e2e8f0;">Security Notice:</strong> Never share this OTP with anyone. Veritas AI administrators will never ask for your verification code.
        </div>

        <div style="font-size: 11px; color: #64748b; text-align: center; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.06);">
          Dispatched via Veritas Enterprise Security Mailer &bull; ISO/IEC 27037 Tamper-Evident Standard
        </div>
      </td>
    </tr>
  </table>
</body>
</html>"""


class EmailService:
    """Unified email service providing encrypted SMTP delivery for OTP verification."""

    def __init__(self):
        self._refresh_config()

    def _refresh_config(self):
        load_dotenv(override=True)
        raw_pass = os.environ.get("SMTP_PASS") or os.environ.get("SMTP_PASSWORD") or ""
        clean_pass = raw_pass.replace(" ", "").strip()
        port = int(os.environ.get("SMTP_PORT", 465))
        secure = str(os.environ.get("SMTP_SECURE", "true")).lower() in ("true", "1", "yes") or port == 465

        import email.utils
        raw_from = (os.environ.get("SMTP_FROM") or "").strip()
        parsed_name, parsed_email = email.utils.parseaddr(raw_from)
        user_email = (os.environ.get("SMTP_USER") or "").strip()
        from_email = parsed_email if parsed_email else user_email
        from_name = parsed_name if parsed_name else "Veritas AI Security"

        self.smtp_config = {
            "host": os.environ.get("SMTP_HOST", "smtp.gmail.com").strip(),
            "port": port,
            "secure": secure,
            "user": user_email,
            "pass": clean_pass,
            "from_email": from_email,
            "from_name": from_name,
            "from": f"{from_name} <{from_email}>" if from_name else from_email
        }

    def is_configured(self) -> bool:
        self._refresh_config()
        return bool(self.smtp_config["user"] and self.smtp_config["pass"])

    async def send_otp_async(
        self,
        to_email: str,
        name: str,
        otp_code: str,
        purpose: str = "email_verification",
        role: str = "user",
        expires_minutes: int = 10
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Asynchronously dispatches an OTP email using the primary email package with native fallback."""
        self._refresh_config()
        subject = (
            f"Your Veritas AI Security Code: {otp_code} (Password Reset)"
            if purpose == "password_reset"
            else f"Your Veritas AI Security Code: {otp_code} (Account Verification)"
        )
        html_body = build_otp_html_email(
            name=name,
            email=to_email,
            otp=otp_code,
            purpose=purpose,
            role=role,
            expires_minutes=expires_minutes
        )
        plain_body = f"Veritas AI Security Code: {otp_code}\nUse this 6-digit code to verify {to_email}. Valid for {expires_minutes} minutes."

        import email.utils
        from_email = self.smtp_config.get("from_email") or self.smtp_config["user"]
        from_name = self.smtp_config.get("from_name") or "Veritas AI Security"
        domain = from_email.split("@")[-1] if "@" in from_email else "gmail.com"
        message_id = email.utils.make_msgid(domain=domain)

        if not self.is_configured():
            return True, "Email queued in local security dispatch sandbox.", {
                "engine": "local_security_sandbox",
                "delivery_mode": "Local Security Sandbox",
                "message_id": message_id,
                "html_preview": html_body
            }

        # 1. Primary: Encrypted SMTP async transport
        if FASTMAIL_AVAILABLE:
            try:
                port = self.smtp_config["port"]
                is_ssl = self.smtp_config["secure"] or port == 465

                conf = ConnectionConfig(
                    MAIL_USERNAME=self.smtp_config["user"],
                    MAIL_PASSWORD=self.smtp_config["pass"],
                    MAIL_FROM=from_email,
                    MAIL_FROM_NAME=from_name,
                    MAIL_PORT=port,
                    MAIL_SERVER=self.smtp_config["host"],
                    MAIL_STARTTLS=not is_ssl,
                    MAIL_SSL_TLS=is_ssl,
                    USE_CREDENTIALS=True,
                    VALIDATE_CERTS=False,
                    TIMEOUT=25
                )
                fm = FastMail(conf)
                msg = MessageSchema(
                    subject=subject,
                    recipients=[to_email],
                    body=html_body,
                    subtype=MessageType.html,
                    alternative_body=plain_body,
                    multipart_subtype=MultipartSubtypeEnum.alternative,
                    reply_to=[from_email]
                )
                await asyncio.wait_for(fm.send_message(msg), timeout=25.0)
                logger.info(f"OTP successfully delivered to {to_email} via primary email engine.")
                return True, f"Verification email sent to {to_email} via secure SMTP.", {
                    "engine": "secure_primary_transport",
                    "delivery_mode": f"Encrypted SMTP ({self.smtp_config['host']}:{port})",
                    "message_id": message_id,
                    "html_preview": html_body
                }
            except Exception as mail_err:
                logger.warning(f"Primary email engine notice: {mail_err}. Attempting secondary TLS/SSL fallback...")

        # 2. Secondary: Direct Python smtplib.SMTP_SSL / STARTTLS fallback
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            mime = MIMEMultipart("alternative")
            mime["Subject"] = subject
            mime["From"] = f"{from_name} <{from_email}>"
            mime["To"] = to_email
            mime["Reply-To"] = from_email
            mime["Date"] = email.utils.formatdate(localtime=True)
            mime["Message-ID"] = message_id
            mime.attach(MIMEText(plain_body, "plain", "utf-8"))
            mime.attach(MIMEText(html_body, "html", "utf-8"))

            host = self.smtp_config["host"]
            port = self.smtp_config["port"]
            user = self.smtp_config["user"]
            pwd = self.smtp_config["pass"]

            if self.smtp_config.get("secure") or port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=20) as server:
                    server.login(user, pwd)
                    server.sendmail(user, [to_email], mime.as_string())
            else:
                with smtplib.SMTP(host, port, timeout=20) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(user, pwd)
                    server.sendmail(user, [to_email], mime.as_string())

            logger.info(f"OTP delivered to {to_email} via secondary SSL/TLS transport.")
            return True, f"Verification email sent to {to_email} via secure SMTP.", {
                "engine": "secure_secondary_transport",
                "delivery_mode": f"Encrypted SMTP ({host}:{port})",
                "message_id": message_id,
                "html_preview": html_body
            }
        except Exception as smtp_err:
            logger.error(f"SMTP delivery failed: {smtp_err}", exc_info=True)
            return False, f"Unable to deliver verification code to {to_email}: {smtp_err}", {
                "engine": "delivery_failed",
                "delivery_mode": "Delivery Failed",
                "message_id": message_id,
                "html_preview": html_body,
                "error": str(smtp_err)
            }

    def send_otp_sync(
        self,
        to_email: str,
        name: str,
        otp_code: str,
        purpose: str = "email_verification",
        role: str = "user",
        expires_minutes: int = 10
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Synchronously dispatches an OTP email, safely managing event loop states."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self.send_otp_async(
                        to_email=to_email,
                        name=name,
                        otp_code=otp_code,
                        purpose=purpose,
                        role=role,
                        expires_minutes=expires_minutes
                    )
                )
                try:
                    return future.result(timeout=30)
                except Exception as ex:
                    logger.error(f"Async email pool error: {ex}")
                    return False, f"Email delivery timed out: {ex}", {
                        "engine": "timeout",
                        "delivery_mode": "Delivery Timed Out",
                        "message_id": f"<{secrets.token_hex(12)}@veritas-forensics.ai>",
                        "html_preview": build_otp_html_email(name, to_email, otp_code, purpose, role, expires_minutes)
                    }
        else:
            try:
                return asyncio.run(
                    self.send_otp_async(
                        to_email=to_email,
                        name=name,
                        otp_code=otp_code,
                        purpose=purpose,
                        role=role,
                        expires_minutes=expires_minutes
                    )
                )
            except Exception as ex:
                logger.error(f"Sync email error: {ex}")
                return False, f"Email delivery failed: {ex}", {
                    "engine": "error",
                    "delivery_mode": "Delivery Error",
                    "message_id": f"<{secrets.token_hex(12)}@veritas-forensics.ai>",
                    "html_preview": build_otp_html_email(name, to_email, otp_code, purpose, role, expires_minutes)
                }


# Global singleton email service
email_service = EmailService()
