"""Application error hierarchy."""


class AppError(Exception):
    def __init__(self, message: str, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AppError): ...


class AuthenticationError(AppError): ...


class RateLimitError(AppError):
    def __init__(self, message: str, retry_after: int, details: dict | None = None) -> None:
        super().__init__(message, details)
        self.retry_after = retry_after


class ExternalServiceError(AppError):
    def __init__(self, service: str, message: str, details: dict | None = None) -> None:
        super().__init__(f"{service}: {message}", details)
        self.service = service


class GraphNodeError(AppError):
    def __init__(self, node: str, message: str, details: dict | None = None) -> None:
        super().__init__(f"Node {node}: {message}", details)
        self.node = node
