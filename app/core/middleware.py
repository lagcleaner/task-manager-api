import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

_request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id_ctx_var.get()


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Trust only our own previously-issued IDs; a client-supplied value could otherwise
    # be used to inject arbitrary content into logs correlated by this header.
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    token = _request_id_ctx_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        _request_id_ctx_var.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # Swagger/Redoc load their assets from a CDN, so they need a looser policy than the
    # rest of this JSON-only API, which serves no HTML/JS and can stay locked to 'none'.
    # script-src needs 'unsafe-inline' too: FastAPI's generated /docs and /redoc HTML embeds
    # the SwaggerUIBundle/Redoc init call as an inline <script>, not a separate file — without
    # it the browser silently blocks that script and the page renders blank.
    if request.url.path.startswith(_DOCS_PATHS):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "img-src 'self' data: fastapi.tiangolo.com"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    # HSTS only makes sense once TLS terminates in front of this app (reverse proxy/ingress);
    # sending it over plain HTTP is a no-op but harmless, so it's always set here.
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response
