class DomainError(Exception):
    """Base class for domain-level failures raised by services."""


class TaskNotFoundError(DomainError):
    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        super().__init__(f"Task {task_id} not found")


class TaskListNotFoundError(DomainError):
    def __init__(self, task_list_id: int) -> None:
        self.task_list_id = task_list_id
        super().__init__(f"Task list {task_list_id} not found")


class UserNotFoundError(DomainError):
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")


class EmailAlreadyRegisteredError(DomainError):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__("Email already registered")


class InvalidCredentialsError(DomainError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class AuthenticationError(DomainError):
    """Missing, malformed, expired, or forged bearer token."""


class RevokedTokenError(DomainError):
    """Access token was explicitly revoked (logout) before its natural expiry."""


class InvalidRefreshTokenError(DomainError):
    """Refresh token is malformed, expired, already rotated, or revoked."""


class AuthorizationError(DomainError):
    def __init__(self, required_role: str) -> None:
        self.required_role = required_role
        super().__init__(f"Requires role '{required_role}'")
