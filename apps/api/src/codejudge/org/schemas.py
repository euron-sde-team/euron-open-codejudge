"""Request and response models for organisation settings and self sign-up."""

from __future__ import annotations

from pydantic import Field, field_validator

from codejudge.core.net import check_url
from codejudge.core.schemas import ApiModel, Email


class PublicSettings(ApiModel):
    """What the sign-in page needs. No secrets, no AI endpoint."""

    site_name: str
    allow_signup: bool
    default_language: str
    ai_enabled: bool


class AdminSettings(ApiModel):
    site_name: str
    allow_signup: bool
    default_language: str
    ai_enabled: bool
    ai_base_url: str | None
    ai_model: str | None
    # The key itself is never returned, only whether one is stored.
    ai_has_key: bool
    ai_max_hints_per_problem: int
    ai_allowed_in_practice: bool
    ai_allowed_in_assignments: bool
    # Fixed by design, shown so the settings page can say so.
    ai_allowed_in_contests: bool = False
    ai_allowed_in_assessments: bool = False


class SettingsUpdate(ApiModel):
    site_name: str | None = Field(None, min_length=1, max_length=80)
    allow_signup: bool | None = None
    default_language: str | None = Field(None, max_length=32)
    ai_enabled: bool | None = None
    ai_base_url: str | None = Field(None, max_length=500)
    ai_model: str | None = Field(None, max_length=120)
    # A new key replaces the stored one; an empty string removes it.
    ai_api_key: str | None = Field(None, max_length=500)
    ai_max_hints_per_problem: int | None = Field(None, ge=0, le=50)
    ai_allowed_in_practice: bool | None = None
    ai_allowed_in_assignments: bool | None = None

    @field_validator("ai_base_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None if v is None else ""
        return check_url(v, "ai_base_url")


class SignupRequest(ApiModel):
    email: Email
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=256)
