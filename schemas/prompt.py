import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


KEY_MAX_LENGTH = 120
REVISION_SUFFIX_PATTERN = re.compile(r"_v\d+$", re.IGNORECASE)
NonEmptyText = Annotated[str, StringConstraints(min_length=1)]
VariantStatus = Literal["draft", "available", "archived"]


def validate_stable_key(value: str) -> str:
    """Validate a schema-backed stable key without normalizing it."""
    if not value.strip():
        raise ValueError("Key must not be empty or whitespace-only.")
    if value != value.strip():
        raise ValueError("Key must not contain surrounding whitespace.")
    if len(value) > KEY_MAX_LENGTH:
        raise ValueError(f"Key must not exceed {KEY_MAX_LENGTH} characters.")
    if REVISION_SUFFIX_PATTERN.search(value):
        raise ValueError("Revision suffixes must not be encoded in stable keys.")
    return value


def validate_optional_stable_key(value: str | None) -> str | None:
    if value is None:
        return None
    return validate_stable_key(value)


def reject_null(value):
    if value is None:
        raise ValueError("Field must not be null.")
    return value


StableKey = Annotated[str, AfterValidator(validate_stable_key)]


def validate_display_name(value: str) -> str:
    """Reject display names that contain no visible characters."""
    if not value.strip():
        raise ValueError("Display name must not be empty or whitespace-only.")
    return value


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MutableBoundaryModel(BoundaryModel):
    @model_validator(mode="after")
    def require_update_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        return self


class FamilyCreate(BoundaryModel):
    family_key: StableKey
    display_name: NonEmptyText
    description: str = ""

    _validate_name = field_validator("display_name")(validate_display_name)


class FamilyUpdate(MutableBoundaryModel):
    display_name: NonEmptyText | None = None
    description: str | None = None

    _reject_nulls = field_validator(
        "display_name",
        "description",
        mode="before",
    )(reject_null)
    _validate_name = field_validator("display_name")(validate_display_name)


class FamilyResponse(BoundaryModel):
    family_key: str
    display_name: str
    description: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class FamilyListResponse(BoundaryModel):
    items: list[FamilyResponse]
    count: int = Field(ge=0)


class PromptCreate(BoundaryModel):
    prompt_key: StableKey
    display_name: NonEmptyText
    description: str = ""
    category: str = ""
    family_key: str | None = None

    _validate_name = field_validator("display_name")(validate_display_name)
    _validate_family_key = field_validator("family_key")(
        validate_optional_stable_key
    )


class PromptUpdate(MutableBoundaryModel):
    display_name: NonEmptyText | None = None
    description: str | None = None
    category: str | None = None
    family_key: str | None = None

    _reject_nulls = field_validator(
        "display_name",
        "description",
        "category",
        mode="before",
    )(reject_null)
    _validate_name = field_validator("display_name")(validate_display_name)
    _validate_family_key = field_validator("family_key")(
        validate_optional_stable_key
    )


class PromptResponse(BoundaryModel):
    prompt_key: str
    display_name: str
    description: str
    category: str
    family_key: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class PromptListResponse(BoundaryModel):
    items: list[PromptResponse]
    count: int = Field(ge=0)


class VariantCreate(BoundaryModel):
    variant_key: StableKey
    display_name: NonEmptyText
    description: str = ""
    status: VariantStatus = "draft"

    _validate_name = field_validator("display_name")(validate_display_name)


class VariantUpdate(MutableBoundaryModel):
    display_name: NonEmptyText | None = None
    description: str | None = None
    status: VariantStatus | None = None

    _reject_nulls = field_validator(
        "display_name",
        "description",
        "status",
        mode="before",
    )(reject_null)
    _validate_name = field_validator("display_name")(validate_display_name)


class VariantResponse(BoundaryModel):
    prompt_key: str
    variant_key: str
    display_name: str
    description: str
    status: VariantStatus
    created_at: datetime
    updated_at: datetime


class VariantListResponse(BoundaryModel):
    items: list[VariantResponse]
    count: int = Field(ge=0)


class PromptRevisionCreate(BoundaryModel):
    system_prompt: str
    change_note: str = ""

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "System prompt must not be empty or whitespace-only."
            )
        return value


class PromptRevisionResponse(BoundaryModel):
    prompt_key: str
    variant_key: str
    revision_number: int = Field(ge=1)
    system_prompt: str
    change_note: str
    created_at: datetime


class PrompRevisionListResponse(BoundaryModel):
    items: list[PromptRevisionResponse]
    count: int = Field(ge=0)
