"""Shared fixtures for the manual e2e flow scripts in scripts/e2e/.

These scripts talk to a real, already-running instance of the API over plain HTTP
(no ASGITransport, no test DB) — see scripts/e2e/README.md for how to run them.
Not collected by default `uv run pytest` (testpaths = ["tests"] in pyproject.toml).
"""

import ipaddress
import os
from collections.abc import AsyncGenerator, Callable
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from httpx import AsyncClient

UniqueValueFactory = Callable[[str], str]

E2E_BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")
_ALLOW_REMOTE_ENV = "E2E_ALLOW_REMOTE"

# Cache across the whole pytest session (module-level, not fixture-scoped) so a full
# `uv run pytest scripts/e2e` run only logs in as the admin once, keeping the total hit
# count against /v1/auth/* low across files, not just within a single one.
_admin_headers_cache: dict[str, str] | None = None

# Same pattern as _admin_headers_cache above, but for the one shared non-admin actor
# account that test_tasks_flow.py, test_task_lists_flow.py, and test_invitations_flow.py
# use instead of each registering+logging in their own user.
_actor_cache: tuple[dict[str, str], str] | None = None


def _looks_like_safe_host(hostname: str) -> bool:
    """True for localhost/loopback/private-network/dev-style hostnames."""
    if hostname in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:  # noqa: S104
        return True
    if hostname.endswith((".localhost", ".local", ".test", ".internal")):
        return True
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return address.is_private or address.is_loopback


def _guard_base_url(base_url: str) -> None:
    if os.environ.get(_ALLOW_REMOTE_ENV) == "1":
        return
    hostname = urlparse(base_url).hostname or ""
    if not _looks_like_safe_host(hostname):
        raise RuntimeError(
            f"E2E_BASE_URL={base_url!r} does not look like a localhost/loopback/private "
            f"dev host. Refusing to run e2e scripts against it. If this is intentional, "
            f"set {_ALLOW_REMOTE_ENV}=1 to opt in explicitly."
        )


# Runs once at collection time (module import), before any test in this directory executes.
_guard_base_url(E2E_BASE_URL)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(base_url=E2E_BASE_URL, timeout=10.0) as http_client:
        yield http_client


@pytest.fixture
def unique_email() -> UniqueValueFactory:
    """Factory for a uuid4-suffixed email, unique per call: unique_email("prefix")."""

    def _make(prefix: str = "e2e") -> str:
        return f"{prefix}-{uuid4().hex[:12]}@example.com"

    return _make


@pytest.fixture
def unique_title() -> UniqueValueFactory:
    """Factory for a uuid4-suffixed title/name, unique per call: unique_title("prefix")."""

    def _make(prefix: str = "E2E") -> str:
        return f"{prefix} {uuid4().hex[:8]}"

    return _make


@pytest.fixture
async def admin_headers(client: AsyncClient) -> dict[str, str] | None:
    """Bearer headers for a pre-provisioned admin account, or None if unavailable.

    `DELETE /v1/tasks/{id}` and `DELETE /v1/task-lists/{id}` require the admin role, and this
    API has no self-service promotion endpoint (see README.md: "promote via a direct DB write").
    Set E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD to a pre-provisioned admin account's credentials to
    exercise those steps; flows that need them skip (not fail) when the vars are unset.
    """
    global _admin_headers_cache
    if _admin_headers_cache is not None:
        return _admin_headers_cache

    email = os.environ.get("E2E_ADMIN_EMAIL")
    password = os.environ.get("E2E_ADMIN_PASSWORD")
    if not email or not password:
        return None

    response = await client.post("/v1/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        raise RuntimeError(
            "E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD are set but login failed with "
            f"{response.status_code}. Check the credentials, or the auth rate limit may be "
            "exhausted — see scripts/e2e/README.md."
        )

    token: str = response.json()["access_token"]
    _admin_headers_cache = {"Authorization": f"Bearer {token}"}
    return _admin_headers_cache


@pytest.fixture
async def actor(client: AsyncClient) -> tuple[dict[str, str], str]:
    """Bearer headers + user id for one shared user account, registered+logged in exactly
    once per pytest session (cached the same way as `admin_headers` above).

    test_tasks_flow.py, test_task_lists_flow.py, and test_invitations_flow.py don't need
    per-flow user isolation — any authenticated user can create/read/update/delete its own
    task lists and tasks — so they share this one account instead of each doing its own
    register+login. That keeps the combined register/login hit count against /v1/auth/* low
    enough to stay under rate_limit_auth (10/minute, app/core/rate_limit.py) even when the
    whole scripts/e2e directory runs, or reruns back to back. test_auth_flow.py keeps its own
    register/login — that's what it tests — and doesn't use this fixture.
    """
    global _actor_cache
    if _actor_cache is not None:
        return _actor_cache

    email = f"actor-{uuid4().hex[:12]}@example.com"
    # Test-only fixed password satisfying UserCreate's strength rule (12+ chars, letter + digit).
    password = "correct-horse-e2e-actor1"

    register_response = await client.post(
        "/v1/auth/register", json={"email": email, "password": password}
    )
    if register_response.status_code != 201:
        raise RuntimeError(
            f"actor fixture: register failed with {register_response.status_code} (expected "
            "201) — the auth rate limit may be exhausted, or the API isn't reachable at "
            f"E2E_BASE_URL={E2E_BASE_URL!r}. See scripts/e2e/README.md."
        )
    user_id: str = register_response.json()["id"]

    login_response = await client.post(
        "/v1/auth/login", json={"email": email, "password": password}
    )
    if login_response.status_code != 200:
        raise RuntimeError(
            f"actor fixture: login failed with {login_response.status_code} (expected 200) "
            "— the auth rate limit may be exhausted, or the credentials are wrong. See "
            "scripts/e2e/README.md."
        )

    token: str = login_response.json()["access_token"]
    _actor_cache = ({"Authorization": f"Bearer {token}"}, user_id)
    return _actor_cache
