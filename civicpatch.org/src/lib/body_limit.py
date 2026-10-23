"""A request-body cap for one path and everything under it, counted as the bytes arrive, before
FastAPI reads the body.

A route dependency cannot do this: FastAPI parses the body before it runs dependencies, and a
chunked request declares no length to check.
"""

from mcp.server.transport_security import RequestBodyLimitMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class PathBodyLimit:
    def __init__(self, app: ASGIApp, path: str, max_body_size: int) -> None:
        self.app = app
        self.path = path
        self.limited = RequestBodyLimitMiddleware(app, max_body_size=max_body_size)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] == "http" and (path == self.path or path.startswith(self.path + "/")):
            await self.limited(scope, receive, send)
            return
        await self.app(scope, receive, send)
