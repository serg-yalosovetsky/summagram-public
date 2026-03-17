"""Reverse-proxy middleware for the model orchestrator.

Provides ``ProxyMiddleware`` which intercepts proxied requests. Route handlers
set ``request.state.proxy_url`` to the full upstream URL; the middleware then
streams the upstream response back to the client.
"""

import logging

import httpx
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from config import VLLM_API_KEY

logger = logging.getLogger("orchestrator")


class ProxyMiddleware(BaseHTTPMiddleware):
    """Stream-proxy middleware.

    Route handlers that want proxying must:
    1. Cache the raw body on ``request.state.proxy_body``.
    2. Set ``request.state.proxy_url`` to the full upstream URL.
    3. Return a sentinel ``Response(status_code=204)`` — the middleware
       will replace it with the proxied upstream response.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Read body BEFORE call_next so the route handler can also access it
        body = await request.body()
        request.state.proxy_body = body

        response = await call_next(request)

        proxy_url: str | None = getattr(request.state, "proxy_url", None)
        if proxy_url is None:
            return response

        return await self._stream_proxy(request, body, proxy_url)

    @staticmethod
    async def _stream_proxy(request: Request, body: bytes, url: str) -> Response:
        headers = ProxyMiddleware._build_proxy_headers(request)
        headers.pop("host", None)
        headers.pop("content-length", None)

        client = httpx.AsyncClient()
        req = client.build_request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            timeout=300.0,
        )
        try:
            resp = await client.send(req, stream=True)

            async def stream_generator():
                async for chunk in resp.aiter_raw():
                    yield chunk
                await resp.aclose()
                await client.aclose()

            return StreamingResponse(
                stream_generator(),
                status_code=resp.status_code,
                headers={
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower()
                    not in (
                        "content-length",
                        "content-encoding",
                        "transfer-encoding",
                    )
                },
            )
        except Exception as e:
            logger.error(f"Error proxying to {url}: {e}")
            await client.aclose()
            return Response(status_code=502, content="Bad Gateway")

    @staticmethod
    def _build_proxy_headers(request: Request) -> dict[str, str]:
        """Build upstream headers and enforce internal auth for model backends."""
        headers = dict(request.headers)
        headers["authorization"] = f"Bearer {VLLM_API_KEY}"
        return headers
