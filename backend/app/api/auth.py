"""Auth routes: register, login, profile, password change & reset."""

import re

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, bearer_scheme
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Trip, User
from app.schemas.trip_schema import TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])

PASSWORD_POLICY = (
    "Password must be at least 8 characters and contain a letter and a number"
)


def validate_password_strength(password: str) -> str:
    if (
        len(password) < 8
        or not re.search(r"[A-Za-z]", password)
        or not re.search(r"\d", password)
    ):
        raise ValueError(PASSWORD_POLICY)
    return password


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validate_password_strength(v)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class MeOut(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: str
    trip_count: int = 0


class MeUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validate_password_strength(v)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validate_password_strength(v)


def _me_out(db, user: User) -> MeOut:
    trip_count = (
        db.scalar(select(func.count()).select_from(Trip).where(Trip.owner_id == user.id))
        or 0
    )
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=str(user.created_at),
        trip_count=trip_count,
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: DbSession) -> TokenOut:
    existing = db.scalar(select(User).where(User.email == body.email.lower()))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbSession) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser, db: DbSession) -> MeOut:
    return _me_out(db, user)


@router.put("/me", response_model=MeOut)
def update_me(body: MeUpdate, user: CurrentUser, db: DbSession) -> MeOut:
    user.display_name = body.display_name.strip()
    db.commit()
    db.refresh(user)
    return _me_out(db, user)


@router.post("/change-password")
def change_password(body: ChangePasswordIn, user: CurrentUser, db: DbSession) -> dict:
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")
    if verify_password(body.new_password, user.hashed_password):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "New password must be different from the current one",
        )
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"status": "changed"}


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordIn, db: DbSession) -> dict:
    """Always 200 (no account-existence leak). Emails a code when SMTP is
    configured; otherwise returns the code with an explicit dev notice so the
    flow works without mail infrastructure."""
    from app.models.password_reset import issue_code, send_reset_email

    user = db.scalar(select(User).where(User.email == body.email.lower()))
    response: dict = {
        "status": "sent",
        "message": "If that email exists, a reset code is on its way.",
    }
    if user is not None:
        code = issue_code(db, body.email.lower())
        sent = send_reset_email(body.email.lower(), code)
        if not sent:
            response["dev_code"] = code
            response["message"] += (
                " No email service is configured on this deployment, so the "
                "code is shown here — set SMTP_HOST/SMTP_USER/SMTP_PASSWORD to "
                "deliver it by email instead."
            )
    return response


@router.post("/reset-password")
def reset_password(body: ResetPasswordIn, db: DbSession) -> dict:
    from app.models.password_reset import verify_code

    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Same error for unknown email / bad code (no existence leak)
    if user is None or not verify_code(db, body.email.lower(), body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"status": "reset"}


__all__ = ["router", "bearer_scheme"]
