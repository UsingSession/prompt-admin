from typing import Annotated

from fastapi import APIRouter, Path

from schemas.compiler import CompiledPromptPreviewResponse
from schemas.prompt import StableKey
from services import compiler


router = APIRouter(prefix="/api/v1", tags=["Prompt compilation"])
RevisionNumber = Annotated[int, Path(ge=1)]


@router.get(
    "/prompts/{prompt_key}/variants/{variant_key}/revisions/"
    "{revision}/compiled-preview",
    response_model=CompiledPromptPreviewResponse,
    summary="Preview a Prompt Revision with current effective Hooks",
    description=(
        "Mutable administration preview compiled against current effective "
        "Hook Revisions. This response is not a published or reproducible "
        "runtime artifact."
    ),
)
def compiled_preview(
    prompt_key: StableKey,
    variant_key: StableKey,
    revision: RevisionNumber,
) -> dict:
    return compiler.preview_prompt_revision(
        prompt_key,
        variant_key,
        revision,
    )
