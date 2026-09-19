from httpx import AsyncClient


async def test_docs_csp_allows_inline_script(client: AsyncClient) -> None:
    response = await client.get("/docs")

    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net" in csp


async def test_api_routes_keep_strict_csp(client: AsyncClient) -> None:
    response = await client.get("/v1/health")

    assert (
        response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
