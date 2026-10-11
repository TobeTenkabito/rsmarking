"""Bound Shapefile request bodies before the multipart parser spools uploads."""

import re

from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from services.annotation_service.utils.shapefile_importer import MAX_SHAPEFILE_BYTES


class ShapefileUploadLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_SHAPEFILE_BYTES + 1024 * 1024):
        self.app = app
        self.max_bytes = max_bytes  # Allow a bounded amount of multipart framing.

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or scope["method"] != "POST" or not re.fullmatch(
            r"/layers/[^/]+/import/shapefile/?", scope["path"]
        ):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            declared_size = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared_size = 0
        if declared_size > self.max_bytes:
            await JSONResponse(status_code=413, content={"detail": "Shapefile upload body is too large"})(scope, receive, send)
            return
        received = 0
        exceeded = False

        async def bounded_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    # Let Starlette close partial upload files on parser failure.
                    raise MultiPartException("Shapefile upload body is too large")
            return message

        async def bounded_send(message):
            if not exceeded:
                await send(message)
            elif message["type"] == "http.response.start":
                # Multipart errors normally become 400; this one is a size limit.
                await JSONResponse(status_code=413, content={"detail": "Shapefile upload body is too large"})(scope, receive, send)

        await self.app(scope, bounded_receive, bounded_send)
