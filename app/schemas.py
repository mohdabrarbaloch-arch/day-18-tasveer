"""Pydantic request/response models.

Every input is bounded: prompt length, seed range, aspect ratio whitelist. That
is the first line of defence — a request that cannot be expressed cannot be
abused.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.engine.renderer import ASPECT_RATIOS
from app.engine.styles import STYLES

AspectRatio = Literal["1:1", "3:2", "2:3", "16:9", "9:16", "4:5"]


# --- Auth ---


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v.isdigit() or v.isalpha():
            raise ValueError("password must mix letters and numbers")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    credits: int
    is_admin: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Generation ---


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=800)
    negative_prompt: str = Field(default="", max_length=400)
    style: str | None = Field(default=None, max_length=40)
    aspect_ratio: AspectRatio = "1:1"
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    count: int = Field(default=4, ge=1, le=4)
    is_public: bool = False

    @field_validator("style")
    @classmethod
    def known_style(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v.strip().lower() not in STYLES:
            raise ValueError(f"unknown style '{v}'. valid: {', '.join(sorted(STYLES))}")
        return v.strip().lower()

    @field_validator("prompt")
    @classmethod
    def prompt_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt cannot be blank")
        return v.strip()


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    width: int
    height: int
    seed: int
    index: int
    upscaled: bool
    url: str = ""


class GenerationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt: str
    negative_prompt: str
    style: str
    aspect_ratio: str
    seed: int
    credits_spent: int
    is_public: bool
    provider: str
    created_at: datetime
    images: list[ImageOut] = []
    author: str = ""


class GalleryPage(BaseModel):
    items: list[GenerationOut]
    total: int
    page: int
    page_size: int
    has_more: bool


class StyleOut(BaseModel):
    key: str
    label: str
    palette: list[str]


class HealthOut(BaseModel):
    status: str
    version: str
    environment: str
    provider: str
    styles: int
    aspect_ratios: list[str]


def valid_aspects() -> list[str]:
    return list(ASPECT_RATIOS.keys())
