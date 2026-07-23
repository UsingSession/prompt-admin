from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from schemas.prompt import (
    FamilyCreate,
    FamilyListResponse,
    FamilyResponse,
    FamilyUpdate,
    PromptCreate,
    PromptListResponse,
    PromptResponse,
    PromptRevisionCreate,
    PromptRevisionListResponse,
    PromptRevisionResponse,
    PromptUpdate,
    StableKey,
    VariantCreate,
    VariantListResponse,
    VariantResponse,
    VariantUpdate,
)
from services import prompt_service


router = APIRouter(prefix="/api/v1", tags=["Prompt management"])
IncludeDeleted = Annotated[bool, Query(description="Include soft-deleted rows.")]
RevisionNumber = Annotated[int, Path(ge=1)]


@router.get("/families", response_model=FamilyListResponse)
def list_families(include_deleted: IncludeDeleted = False) -> dict:
    items = prompt_service.list_families(include_deleted=include_deleted)
    return {"items": items, "count": len(items)}


@router.post(
    "/families",
    response_model=FamilyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_family(data: FamilyCreate) -> dict:
    return prompt_service.create_family(data)


@router.get("/families/{family_key}", response_model=FamilyResponse)
def get_family(family_key: StableKey) -> dict:
    return prompt_service.get_family(family_key)


@router.patch("/families/{family_key}", response_model=FamilyResponse)
def update_family(family_key: StableKey, data: FamilyUpdate) -> dict:
    return prompt_service.update_family(family_key, data)


@router.delete(
    "/families/{family_key}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_family(family_key: StableKey) -> Response:
    prompt_service.delete_family(family_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/families/{family_key}/restore",
    response_model=FamilyResponse,
)
def restore_family(family_key: StableKey) -> dict:
    return prompt_service.restore_family(family_key)


@router.get("/prompts", response_model=PromptListResponse)
def list_prompts(
    family_key: StableKey | None = None,
    category: str | None = None,
    include_deleted: IncludeDeleted = False,
) -> dict:
    items = prompt_service.list_prompts(
        family_key=family_key,
        category=category,
        include_deleted=include_deleted,
    )
    return {"items": items, "count": len(items)}


@router.post(
    "/prompts",
    response_model=PromptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt(data: PromptCreate) -> dict:
    return prompt_service.create_prompt(data)


@router.get("/prompts/{prompt_key}", response_model=PromptResponse)
def get_prompt(prompt_key: StableKey) -> dict:
    return prompt_service.get_prompt(prompt_key)


@router.patch("/prompts/{prompt_key}", response_model=PromptResponse)
def update_prompt(prompt_key: StableKey, data: PromptUpdate) -> dict:
    return prompt_service.update_prompt(prompt_key, data)


@router.delete(
    "/prompts/{prompt_key}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_prompt(prompt_key: StableKey) -> Response:
    prompt_service.delete_prompt(prompt_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/prompts/{prompt_key}/restore",
    response_model=PromptResponse,
)
def restore_prompt(prompt_key: StableKey) -> dict:
    return prompt_service.restore_prompt(prompt_key)


@router.get(
    "/prompts/{prompt_key}/variants",
    response_model=VariantListResponse,
)
def list_variants(prompt_key: StableKey) -> dict:
    items = prompt_service.list_variants(prompt_key)
    return {"items": items, "count": len(items)}


@router.post(
    "/prompts/{prompt_key}/variants",
    response_model=VariantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_variant(prompt_key: StableKey, data: VariantCreate) -> dict:
    return prompt_service.create_variant(prompt_key, data)


@router.get(
    "/prompts/{prompt_key}/variants/{variant_key}",
    response_model=VariantResponse,
)
def get_variant(prompt_key: StableKey, variant_key: StableKey) -> dict:
    return prompt_service.get_variant(prompt_key, variant_key)


@router.patch(
    "/prompts/{prompt_key}/variants/{variant_key}",
    response_model=VariantResponse,
)
def update_variant(
    prompt_key: StableKey,
    variant_key: StableKey,
    data: VariantUpdate,
) -> dict:
    return prompt_service.update_variant(prompt_key, variant_key, data)


@router.get(
    "/prompts/{prompt_key}/variants/{variant_key}/revisions",
    response_model=PromptRevisionListResponse,
)
def list_revisions(
    prompt_key: StableKey,
    variant_key: StableKey,
) -> dict:
    items = prompt_service.list_revisions(prompt_key, variant_key)
    return {"items": items, "count": len(items)}


@router.post(
    "/prompts/{prompt_key}/variants/{variant_key}/revisions",
    response_model=PromptRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_revision(
    prompt_key: StableKey,
    variant_key: StableKey,
    data: PromptRevisionCreate,
) -> dict:
    return prompt_service.create_revision(prompt_key, variant_key, data)


@router.get(
    "/prompts/{prompt_key}/variants/{variant_key}/revisions/{revision}",
    response_model=PromptRevisionResponse,
)
def get_revision(
    prompt_key: StableKey,
    variant_key: StableKey,
    revision: RevisionNumber,
) -> dict:
    return prompt_service.get_revision(prompt_key, variant_key, revision)
