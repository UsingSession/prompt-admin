class PromptAdminError(Exception):
    """Stable application error exposed through the HTTP API."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        status_code: int = 400,
    ) -> None:
        if message is None:
            message = code
            code = "bad_request"
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DatabaseUnavailableError(PromptAdminError):
    """Raised when PostgreSQL cannot serve a domain operation."""

    def __init__(self) -> None:
        super().__init__(
            "database_unavailable",
            "Database is unavailable.",
            503,
        )
