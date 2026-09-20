import logging
from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient

from app.main import app

_PROBE_PATH = "/__unhandled_exception_probe__"


@pytest.fixture
def _probe_route(monkeypatch: pytest.MonkeyPatch) -> Generator[list[str | None]]:
    # The generic Exception handler is only wired on the real `app` instance
    # (app.main.app), so probing it means adding a route that raises a plain,
    # undeclared Exception to that instance, then tearing it down afterward
    # so it doesn't leak into other tests.
    #
    # Starlette's ServerErrorMiddleware only calls the registered Exception
    # handler when `app.debug` is False; with it True (e.g. a local `.env`
    # setting DEBUG=true, picked up by Settings' env_file loading) it instead
    # renders a debug traceback page and never touches our handler. Force
    # debug off here so this test exercises the handler regardless of the
    # environment it runs in, and clear the cached middleware stack so the
    # rebuilt stack picks up the new value.
    monkeypatch.setattr(app, "debug", False)
    monkeypatch.setattr(app, "middleware_stack", None)

    # request_id_middleware's response header is never set on this path (the exception
    # propagates out of call_next before that assignment runs), so the only way to know
    # the request's actual request_id is to capture request.state.request_id set by that
    # middleware before call_next — the same attribute the handler under test reads.
    captured_request_ids: list[str | None] = []

    @app.get(_PROBE_PATH)
    async def _raise_unhandled(request: Request) -> None:
        captured_request_ids.append(request.state.request_id)
        raise RuntimeError("boom")

    yield captured_request_ids

    app.router.routes[:] = [
        route for route in app.router.routes if getattr(route, "path", None) != _PROBE_PATH
    ]
    app.middleware_stack = None


@pytest.fixture
async def unraising_client(client: AsyncClient) -> AsyncGenerator[AsyncClient]:
    # Starlette's ServerErrorMiddleware sends the handler's response *and* then
    # re-raises, so a real ASGI server can still log the crash — httpx's
    # ASGITransport mirrors that by re-raising into the test by default. A live
    # deployment behind uvicorn never surfaces that re-raise to the caller, so
    # disable it here to observe the actual client-facing response. Reuses the
    # `client` fixture's db/redis dependency overrides on the same `app`.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_unhandled_exception_returns_generic_500_body(
    unraising_client: AsyncClient, _probe_route: list[str | None]
) -> None:
    response = await unraising_client.get(_PROBE_PATH)

    assert response.status_code == 500
    assert response.json() == {
        "detail": {"code": "internal_server_error", "message": "An unexpected error occurred"}
    }


async def test_unhandled_exception_logs_exception(
    unraising_client: AsyncClient, _probe_route: list[str | None], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = await unraising_client.get(_PROBE_PATH)

    assert response.status_code == 500
    assert any(
        record.name == "app.main" and record.getMessage() == "Unhandled exception"
        for record in caplog.records
    )


async def test_unhandled_exception_logs_actual_request_id(
    unraising_client: AsyncClient, _probe_route: list[str | None], caplog: pytest.LogCaptureFixture
) -> None:
    # Regression test: the catch-all handler runs after request_id_middleware's `finally`
    # has already reset the request_id contextvar, so the log record must get its
    # request_id from request.state.request_id (passed via `extra`), not the contextvar —
    # otherwise it silently logs "request_id": null for every server crash.
    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = await unraising_client.get(_PROBE_PATH)

    assert response.status_code == 500
    log_record = next(
        record
        for record in caplog.records
        if record.name == "app.main" and record.getMessage() == "Unhandled exception"
    )

    actual_request_id = _probe_route[0]
    assert actual_request_id is not None
    assert log_record.request_id == actual_request_id  # type: ignore[attr-defined]
