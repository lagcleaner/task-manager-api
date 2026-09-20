"""Manual e2e flow: register -> login -> use access token -> refresh (rotation) ->
logout -> access token rejected after logout. Plus one failure path (duplicate register).

Run: uv run pytest scripts/e2e/test_auth_flow.py --no-cov (requires a live stack, see README.md).

Hits /v1/auth/* six times total (register, duplicate register, login, refresh, replayed
refresh, logout) — comfortably under the 10/minute rate_limit_auth budget
(app/core/rate_limit.py) for a single run.
"""

from collections.abc import Callable

from httpx import AsyncClient

# Test-only fixed password satisfying UserCreate's strength rule (12+ chars, letter + digit).
# Not a real credential for anything — the account it authenticates only exists transiently
# in whatever disposable dev stack E2E_BASE_URL points at.
_PASSWORD = "correct-horse-e2e-1"


async def test_register_login_use_refresh_logout_flow(
    client: AsyncClient, unique_email: Callable[[str], str]
) -> None:
    email = unique_email("auth-flow")

    # register
    register_response = await client.post(
        "/v1/auth/register", json={"email": email, "password": _PASSWORD}
    )
    assert register_response.status_code == 201
    assert register_response.json()["email"] == email

    # failure path: duplicate registration is rejected
    duplicate_response = await client.post(
        "/v1/auth/register", json={"email": email, "password": _PASSWORD}
    )
    assert duplicate_response.status_code == 409

    # login: verify the token pair shape
    login_response = await client.post(
        "/v1/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    # use the access token on an authenticated endpoint
    authed_response = await client.get(
        "/v1/tasks", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert authed_response.status_code == 200

    # refresh: rotates the pair
    refresh_response = await client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    rotated_tokens = refresh_response.json()
    assert rotated_tokens["access_token"]
    assert rotated_tokens["refresh_token"] != tokens["refresh_token"]

    # the old (pre-rotation) refresh token is now rejected
    replay_response = await client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replay_response.status_code == 401

    # logout: revokes the current access token and the rotated refresh token
    logout_response = await client.post(
        "/v1/auth/logout",
        json={"refresh_token": rotated_tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {rotated_tokens['access_token']}"},
    )
    assert logout_response.status_code == 204

    # the access token is rejected after logout
    revoked_response = await client.get(
        "/v1/tasks", headers={"Authorization": f"Bearer {rotated_tokens['access_token']}"}
    )
    assert revoked_response.status_code == 401
