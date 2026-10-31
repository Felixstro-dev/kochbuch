from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WishCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=300)
    note: str = Field(default="", max_length=1000)


class WishUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=300)
    note: str | None = Field(default=None, max_length=1000)
    status: Literal["open", "done"] | None = None


class WishOut(BaseModel):
    id: str
    text: str
    note: str = ""
    status: str = "open"
    created_by: str | None = None
    created_at: str
    updated_at: str
    done_at: str | None = None
