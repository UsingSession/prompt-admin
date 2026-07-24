import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, Field, field_validator

from schemas.prompt import (
    BoundaryModel,
    KEY_MAX_LENGTH,
    MutableBoundaryModel,
    NonEmptyText,
    StableKey,
    reject_null,
    validate_display_name,
)


HOOK_GROUP_PATTERN = re.compile(r"hook_[A-Za-z0-9_.-]+\Z")


def validate_hook_group(value: str) -> str:
    """Validate a stored Hook group without normalizing it."""
    if value != value.strip():
        raise ValueError("Hook group must not contain surrounding whitespace.")
    if len(value) > KEY_MAX_LENGTH:
        raise ValueError(
            f"Hook group must not exceed {KEY_MAX_LENGTH} characters."
        )
    if not HOOK_GROUP_PATTERN.fullmatch(value):
        raise ValueError(
            "Hook group must match hook_[A-Za-z0-9_.-]+ without a leading #."
        )
    return value


HookGroup = Annotated[str, AfterValidator(validate_hook_group)]


class HookCreate(BoundaryModel):
    hook_key: StableKey
    display_name: NonEmptyText
    description: str = ""
    category: str = ""

    _validate_name = field_validator("display_name")(validate_display_name)


class HookUpdate(MutableBoundaryModel):
    display_name: NonEmptyText | None = None
    description: str | None = None
    category: str | None = None

    _reject_nulls = field_validator(
        "display_name",
        "description",
        "category",
        mode="before",
    )(reject_null)
    _validate_name = field_validator("display_name")(validate_display_name)


class HookResponse(BoundaryModel):
    hook_key: str
    display_name: str
    description: str
    category: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class HookListResponse(BoundaryModel):
    items: list[HookResponse]
    count: int = Field(ge=0)


class HookRevisionCreate(BoundaryModel):
    hook_group: HookGroup
    hook_content: str
    priority: int = Field(default=100, ge=0)
    is_enabled: bool = True
    change_note: str = ""

    @field_validator("hook_content")
    @classmethod
    def validate_hook_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "Hook content must not be empty or whitespace-only."
            )
        return value


class HookRevisionResponse(BoundaryModel):
    hook_key: str
    revision_number: int = Field(ge=1)
    hook_group: str
    hook_content: str
    priority: int = Field(ge=0)
    is_enabled: bool
    change_note: str
    created_at: datetime


class HookRevisionListResponse(BoundaryModel):
    items: list[HookRevisionResponse]
    count: int = Field(ge=0)
