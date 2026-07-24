from typing import Literal

from pydantic import Field

from schemas.prompt import BoundaryModel


CompilationMode = Literal["preview", "strict"]


class ResolvedHookResponse(BoundaryModel):
    hook_key: str
    revision_number: int = Field(ge=1)
    hook_group: str
    priority: int = Field(ge=0)


class CompiledPromptPreviewResponse(BoundaryModel):
    mode: Literal["preview"]
    raw_prompt: str
    compiled_prompt: str
    detected_groups: list[str]
    resolved_hooks: list[ResolvedHookResponse]
    unresolved_groups: list[str]
