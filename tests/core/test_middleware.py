from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.responses import JSONResponse

from app.core.middleware import REQUEST_ID_HEADER, get_request_id, request_id_middleware


def _build_probe_app() -> FastAPI:
    probe_app = FastAPI()
    probe_app.middleware("http")(request_id_middleware)

    @probe_app.get("/probe")
    async def probe() -> JSONResponse:
        return JSONResponse({"request_id": get_request_id()})

    return probe_app


async def test_request_id_middleware_sets_contextvar_during_request() -> None:
    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/probe")

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] is not None
    assert response.headers[REQUEST_ID_HEADER] == body["request_id"]


async def test_request_id_middleware_resets_contextvar_after_request() -> None:
    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.get("/probe")

    assert get_request_id() is None


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
