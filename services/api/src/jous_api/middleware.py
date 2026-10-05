"""Pure ASGI correlation and generic unexpected-error boundary."""

import re
from uuid import uuid4

from starlette.responses import JSONResponse

from .observability import request_id

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class RequestBoundary:
    def __init__(self, app, logger, id_factory=lambda: uuid4().hex):
        self.app = app
        self.logger = logger
        self.id_factory = id_factory

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = [value for name, value in scope.get("headers", [])
                    if name.lower() == b"x-request-id"]
        candidate = (incoming[0].decode("ascii", errors="replace")
                     if len(incoming) == 1 and len(incoming[0]) <= 64 else "")
        identity = candidate if SAFE_ID.fullmatch(candidate) else self.id_factory()
        token = request_id.set(identity)
        scope.setdefault("state", {})["request_id"] = identity
        started = False
        completed = False
        status = 500

        async def correlated_send(message):
            nonlocal started, completed, status
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                headers = [(k, v) for k, v in message.get("headers", [])
                           if k.lower() != b"x-request-id"]
                message = {**message, "headers": headers + [(b"x-request-id", identity.encode("ascii"))]}
            elif message["type"] == "http.response.body":
                completed = not message.get("more_body", False)
            await send(message)

        try:
            await self.app(scope, receive, correlated_send)
            self.logger.info("", extra={"event": "request_complete", "status_code": status})
        except Exception:
            # Exclude exception text/traceback: either can contain customer data or secrets.
            self.logger.error("", extra={"event": "request_failed", "status_code": 500})
            if not started:
                response = JSONResponse(
                    {"error": {"code": "internal_error", "message": "Internal server error"},
                     "request_id": identity}, status_code=500,
                )
                await response(scope, receive, correlated_send)
            elif not completed:
                # Headers cannot be replaced after streaming starts. Terminate without details.
                await send({"type": "http.response.body", "body": b"", "more_body": False})
        finally:
            request_id.reset(token)
