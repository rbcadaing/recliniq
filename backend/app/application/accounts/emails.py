"""Email templates for account flows. Plain functions returning text and HTML bodies."""

from html import escape
from urllib.parse import urlencode

from app.application.accounts.ports import EmailMessage


def verification_link(frontend_base_url: str, token: str) -> str:
    return f"{frontend_base_url.rstrip('/')}/verify-email?{urlencode({'token': token})}"


def verification_email(
    *, to: str, first_name: str, link: str, ttl_hours: int, app_name: str
) -> EmailMessage:
    text = (
        f"Hi {first_name},\n\n"
        f"Please confirm your email address to activate your {app_name} account:\n\n"
        f"{link}\n\n"
        f"This link expires in {ttl_hours} hours and can be used once. "
        "If you didn't sign up, you can ignore this email.\n"
    )
    html = (
        f"<p>Hi {escape(first_name)},</p>"
        f"<p>Please confirm your email address to activate your {escape(app_name)} account:</p>"
        f'<p><a href="{escape(link)}">Verify my email</a></p>'
        f"<p>This link expires in {ttl_hours} hours and can be used once. "
        "If you didn't sign up, you can ignore this email.</p>"
    )
    return EmailMessage(to=to, subject=f"Verify your {app_name} email", text=text, html=html)


def account_exists_email(*, to: str, first_name: str, app_name: str) -> EmailMessage:
    text = (
        f"Hi {first_name},\n\n"
        f"Someone tried to create a {app_name} account with this email address, "
        "but you already have one. You can sign in, or reset your password if you've "
        "forgotten it.\n\n"
        "If this wasn't you, no action is needed.\n"
    )
    html = (
        f"<p>Hi {escape(first_name)},</p>"
        f"<p>Someone tried to create a {escape(app_name)} account with this email address, "
        "but you already have one. You can sign in, or reset your password if you've "
        "forgotten it.</p><p>If this wasn't you, no action is needed.</p>"
    )
    return EmailMessage(
        to=to, subject=f"You already have a {app_name} account", text=text, html=html
    )


def password_reset_link(frontend_base_url: str, token: str) -> str:
    return f"{frontend_base_url.rstrip('/')}/reset-password?{urlencode({'token': token})}"


def password_reset_email(
    *, to: str, first_name: str, link: str, ttl_minutes: int, app_name: str
) -> EmailMessage:
    text = (
        f"Hi {first_name},\n\n"
        f"We received a request to reset your {app_name} password. Choose a new one here:\n\n"
        f"{link}\n\n"
        f"This link expires in {ttl_minutes} minutes and can be used once. Resetting your "
        "password signs you out on all devices.\n\n"
        "If you didn't ask for this, you can ignore this email; your password won't change.\n"
    )
    html = (
        f"<p>Hi {escape(first_name)},</p>"
        f"<p>We received a request to reset your {escape(app_name)} password.</p>"
        f'<p><a href="{escape(link)}">Choose a new password</a></p>'
        f"<p>This link expires in {ttl_minutes} minutes and can be used once. Resetting your "
        "password signs you out on all devices.</p>"
        "<p>If you didn't ask for this, you can ignore this email; your password won't "
        "change.</p>"
    )
    return EmailMessage(to=to, subject=f"Reset your {app_name} password", text=text, html=html)
