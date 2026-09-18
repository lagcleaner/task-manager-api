class AppError(Exception):
    """Base class for application-level errors surfaced to the HTTP layer."""


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: object) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} with id={identifier!r} not found")
