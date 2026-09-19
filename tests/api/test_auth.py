from httpx import AsyncClient

_PASSWORD = "correct-horse-1"


async def test_register_returns_201_and_never_echoes_password(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/register", json={"email": "new@example.com", "password": _PASSWORD}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_rejects_weak_password(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/register", json={"email": "weak@example.com", "password": "short"}
    )

    assert response.status_code == 422


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    await client.post("/v1/auth/register", json={"email": "dup@example.com", "password": _PASSWORD})

    response = await client.post(
        "/v1/auth/register", json={"email": "dup@example.com", "password": _PASSWORD}
    )

    assert response.status_code == 409


async def test_login_returns_access_and_refresh_token(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/register", json={"email": "login@example.com", "password": _PASSWORD}
    )

    response = await client.post(
        "/v1/auth/login", json={"email": "login@example.com", "password": _PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_refresh_rotates_tokens_and_old_refresh_token_is_rejected(
    client: AsyncClient,
) -> None:
    await client.post(
        "/v1/auth/register", json={"email": "rotate@example.com", "password": _PASSWORD}
    )
    login_response = await client.post(
        "/v1/auth/login", json={"email": "rotate@example.com", "password": _PASSWORD}
    )
    old_refresh_token = login_response.json()["refresh_token"]

    refresh_response = await client.post(
        "/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert refresh_response.status_code == 200
    new_body = refresh_response.json()
    assert new_body["access_token"]
    assert new_body["refresh_token"] != old_refresh_token

    replay_response = await client.post(
        "/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert replay_response.status_code == 401
    assert replay_response.json()["detail"]["code"] == "invalid_refresh_token"


async def test_refresh_rejects_forged_token(client: AsyncClient) -> None:
    response = await client.post("/v1/auth/refresh", json={"refresh_token": "not-a-real-jwt"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_refresh_token"


async def test_logout_revokes_access_token(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/register", json={"email": "logout@example.com", "password": _PASSWORD}
    )
    login_response = await client.post(
        "/v1/auth/login", json={"email": "logout@example.com", "password": _PASSWORD}
    )
    tokens = login_response.json()

    logout_response = await client.post(
        "/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert logout_response.status_code == 204

    protected_response = await client.get(
        "/v1/tasks", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert protected_response.status_code == 401
    assert protected_response.json()["detail"]["code"] == "token_revoked"


async def test_logout_also_revokes_provided_refresh_token(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/register", json={"email": "logout2@example.com", "password": _PASSWORD}
    )
    login_response = await client.post(
        "/v1/auth/login", json={"email": "logout2@example.com", "password": _PASSWORD}
    )
    tokens = login_response.json()

    await client.post(
        "/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    refresh_response = await client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 401


async def test_logout_without_bearer_token_returns_401(client: AsyncClient) -> None:
    response = await client.post("/v1/auth/logout", json={})

    assert response.status_code == 401


async def test_login_wrong_password_returns_401_generic_message(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/register", json={"email": "wrongpw@example.com", "password": _PASSWORD}
    )

    response = await client.post(
        "/v1/auth/login", json={"email": "wrongpw@example.com", "password": "not-the-password-1"}
    )

    assert response.status_code == 401
    assert response.json()["detail"]["message"] == "Invalid email or password"


async def test_login_unknown_email_returns_same_generic_message(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": _PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["detail"]["message"] == "Invalid email or password"


async def test_protected_endpoint_rejects_forged_token(client: AsyncClient) -> None:
    response = await client.get("/v1/tasks", headers={"Authorization": "Bearer not-a-real-jwt"})

    assert response.status_code == 401
