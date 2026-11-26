"""Request correlation and access logging (pure ASGI so context vars propagate correctly)."""

import re
import time
import uuid
from contextvars import ContextVar

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._\-]{1,128}$")

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = structlog.get_logger("app.access")


def get_request_id() -> str | None:
    return request_id_ctx.get()


class RequestContextMiddleware:
    """Assigns a request ID, echoes it in the response, and writes one access log per request.

    A client-supplied ``X-Request-ID`` is reused if it is a safe token; otherwise a UUID is
    generated. Query strings are never logged because they may carry tokens.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _header(scope, REQUEST_ID_HEADER)
        request_id = (
            incoming if incoming and _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        )

        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_ctx.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)

        status_code = 500
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            logger.info(
                "request",
                method=scope["method"],
                path=scope["path"],
                status_code=status_code,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            structlog.contextvars.unbind_contextvars("request_id")
            request_id_ctx.reset(token)


def _header(scope: Scope, name: str) -> str | None:
    target = name.lower().encode("latin-1")
    for key, value in scope.get("headers", []):
        if key.lower() == target:
            return str(value.decode("latin-1"))
    return None
