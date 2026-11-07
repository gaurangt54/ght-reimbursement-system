"""Typed API errors. Every error is returned as:
{"error": {"code": "...", "message": "...", "fields": {...}}}
"""


class ApiError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, fields: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        self.fields = fields or {}
        if code:
            self.code = code


class Unauthorized(ApiError):
    status_code = 401
    code = "UNAUTHORIZED"


class Forbidden(ApiError):
    status_code = 403
    code = "FORBIDDEN"


class NotFound(ApiError):
    status_code = 404
    code = "NOT_FOUND"


class Conflict(ApiError):
    status_code = 409
    code = "CONFLICT"


class Unprocessable(ApiError):
    status_code = 422
    code = "VALIDATION_ERROR"