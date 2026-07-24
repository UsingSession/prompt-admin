from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from schemas.hook import (
    HookCreate,
    HookListResponse,
    HookResponse,
    HookRevisionCreate,
    HookRevisionListResponse,
    HookRevisionResponse,
    HookUpdate,
)
from schemas.prompt import StableKey
from services import hook_service


router = APIRouter(prefix="/api/v1/hooks", tags=["Hook management"])
IncludeDeleted = Annotated[bool, Query(description="Include soft-deleted rows.")]
RevisionNumber = Annotated[int, Path(ge=1)]


@router.get("", response_model=HookListResponse)
def list_hooks(
    category: str | None = None,
    include_deleted: IncludeDeleted = False,
) -> dict:
    items = hook_service.list_hooks(
        category=category,
        include_deleted=include_deleted,
    )
    return {"items": items, "count": len(items)}


@router.post(
    "",
    response_model=HookResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hook(data: HookCreate) -> dict:
    return hook_service.create_hook(data)


@router.get("/{hook_key}", response_model=HookResponse)
def get_hook(
    hook_key: StableKey,
    include_deleted: IncludeDeleted = False,
) -> dict:
    return hook_service.get_hook(
        hook_key,
        include_deleted=include_deleted,
    )


@router.patch("/{hook_key}", response_model=HookResponse)
def update_hook(hook_key: StableKey, data: HookUpdate) -> dict:
    return hook_service.update_hook(hook_key, data)


@router.delete(
    "/{hook_key}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_hook(hook_key: StableKey) -> Response:
    hook_service.delete_hook(hook_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{hook_key}/restore", response_model=HookResponse)
def restore_hook(hook_key: StableKey) -> dict:
    return hook_service.restore_hook(hook_key)


@router.get(
    "/{hook_key}/revisions",
    response_model=HookRevisionListResponse,
)
def list_revisions(hook_key: StableKey) -> dict:
    items = hook_service.list_revisions(hook_key)
    return {"items": items, "count": len(items)}


@router.post(
    "/{hook_key}/revisions",
    response_model=HookRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_revision(
    hook_key: StableKey,
    data: HookRevisionCreate,
) -> dict:
    return hook_service.create_revision(hook_key, data)


@router.get(
    "/{hook_key}/revisions/{revision}",
    response_model=HookRevisionResponse,
)
def get_revision(
    hook_key: StableKey,
    revision: RevisionNumber,
) -> dict:
    return hook_service.get_revision(hook_key, revision)
