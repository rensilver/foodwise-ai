"""Framework-independent failures. Codes, never exception text, cross boundaries."""

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    INTERNAL_ERROR = "internal_error"


class ApplicationError(Exception):
    """Raise a stable code; retain sensitive adapter causes only in memory."""

    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)
