from httpx import AsyncClient


async def test_login_endpoint_is_rate_limited(client: AsyncClient) -> None:
    # rate_limit_auth defaults to 10/minute in tests (see .env.example); one
    # extra request past the limit must be rejected with 429.
    for _ in range(10):
        await client.post(
            "/v1/auth/login", json={"email": "flood@example.com", "password": "irrelevant-1"}
        )

    response = await client.post(
        "/v1/auth/login", json={"email": "flood@example.com", "password": "irrelevant-1"}
    )

    assert response.status_code == 429
