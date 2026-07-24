from fastapi import Request

from services import hook_ui_service


EMPTY_HOOK_SUMMARY = {
    "active_count": 0,
    "no_revision_count": 0,
    "disabled_count": 0,
}


def dashboard_context(request: Request) -> dict:
    if request.url.path != "/":
        return {}
    if not request.app.state.initialize_database:
        return {"hook_summary": EMPTY_HOOK_SUMMARY}
    return {"hook_summary": hook_ui_service.dashboard_summary()}
