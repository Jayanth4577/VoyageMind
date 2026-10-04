"""Single-use password-reset codes (forgot-password flow).

Codes are stored hashed with an expiry; plain codes only ever travel over
email (or, when no SMTP is configured, in the API response with an explicit
dev notice so the flow still works without mail infrastructure).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import hash_password, verify_password
from app.models.base import IdMixin, new_id

CODE_TTL_MINUTES = 15
MAX_ATTEMPTS = 5


def _new_code() -> str:
    return f"{int(new_id(), 16) % 1_000_000:06d}"


class PasswordResetCode(Base, IdMixin):
    __tablename__ = "password_reset_codes"

    email: Mapped[str] = mapped_column(String(320), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC) + timedelta(minutes=CODE_TTL_MINUTES)
    )
    used: Mapped[bool] = mapped_column(default=False)
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


def issue_code(db, email: str) -> str:
    """Invalidate previous codes for the email and issue a fresh one."""

    db.query(PasswordResetCode).filter(
        PasswordResetCode.email == email.lower(), PasswordResetCode.used.is_(False)
    ).update({"used": True})
    plain = _new_code()
    db.add(
        PasswordResetCode(
            email=email.lower(),
            code_hash=hash_password(plain),
        )
    )
    db.commit()
    return plain


def _as_utc(dt: datetime) -> datetime:
    """Treat naive datetimes (SQLite round-trip) as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def verify_code(db, email: str, code: str) -> bool:
    """Check a code: unused, unexpired, under attempt limit, value matches."""

    row = (
        db.query(PasswordResetCode)
        .filter(
            PasswordResetCode.email == email.lower(),
            PasswordResetCode.used.is_(False),
        )
        .order_by(PasswordResetCode.created_at.desc())
        .first()
    )
    if row is None:
        return False
    if row.attempts >= MAX_ATTEMPTS:
        return False
    row.attempts += 1
    db.commit()
    if datetime.now(UTC) > _as_utc(row.expires_at):
        return False
    if not verify_password(code.strip(), row.code_hash):
        return False
    row.used = True
    db.commit()
    return True


def send_reset_email(email: str, code: str) -> bool:
    """Email the code when SMTP is configured. Returns True if sent."""
    import os

    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        return False
    try:
        import smtplib
        from email.mime.text import MIMEText

        port = int(os.environ.get("SMTP_PORT", "587"))
        user = os.environ.get("SMTP_USER", "").strip()
        password = os.environ.get("SMTP_PASSWORD", "").strip()
        sender = os.environ.get("SMTP_FROM", user or "voyagemind@localhost")

        msg = MIMEText(
            f"Your VoyageMind password reset code is: {code}\n\n"
            f"It expires in {CODE_TTL_MINUTES} minutes. "
            "If you didn't request this, you can ignore this email."
        )
        msg["Subject"] = "VoyageMind password reset code"
        msg["From"] = sender
        msg["To"] = email

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(sender, [email], msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning("reset email failed: %s", exc)
        return False
