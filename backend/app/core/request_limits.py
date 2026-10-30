from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException


class RequestSizeLimit:
    """Bound multipart input before Starlette finishes spooling it to disk."""
    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
        if declared > self.max_bytes:
            return await JSONResponse({"detail": "Request exceeds maximum upload size"}, status_code=413)(scope, receive, send)
        consumed = 0

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > self.max_bytes:
                raise HTTPException(413, "Request exceeds maximum upload size")
            return message

        await self.app(scope, limited_receive, send)
