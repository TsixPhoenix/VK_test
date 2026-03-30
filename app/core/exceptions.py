"""Domain-level exceptions exposed by the service layer."""


class ServiceError(Exception):
    """Base service exception mapped to an HTTP error."""

    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ConflictError(ServiceError):
    """Raised when operation conflicts with current state."""

    status_code = 409


class NotFoundError(ServiceError):
    """Raised when entity was not found."""

    status_code = 404


class UnauthorizedError(ServiceError):
    """Raised when authorization checks fail."""

    status_code = 401
