import mimetypes
from urllib.parse import unquote

from config import STATIC_DIR
from errors import PromptAdminError


def resolve_static_file(relative_path):
    static_root = STATIC_DIR.resolve()
    file_path = (static_root / unquote(relative_path).lstrip("/")).resolve()

    if file_path != static_root and static_root not in file_path.parents:
        raise PromptAdminError("Static file path is not allowed.")
    if not file_path.is_file():
        raise FileNotFoundError("Static file not found.")

    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return file_path.read_bytes(), content_type
