from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import UserOut


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    display_name: str = Field(default="", max_length=120)
    password: str = Field(min_length=1, max_length=200)
    role: Literal["admin", "member"] = "member"

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    role: Literal["admin", "member"] | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=1, max_length=200)


class UserList(BaseModel):
    items: list[UserOut]
