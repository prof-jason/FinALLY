"""Service-layer error type, mapped to `{"error": message}` by the API layer."""

from __future__ import annotations


class ServiceError(Exception):
    """A user-facing failure with an HTTP status (400, 404 or 503)."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
