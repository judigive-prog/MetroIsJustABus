"""The one outbound HTTP client: timeouts, correlation id and service token (conventions.md, Calls)."""

from typing import Any

import httpx
from metro_common.correlation import HEADER, get_correlation_id

CONNECT_TIMEOUT_SECONDS = 1.0
READ_TIMEOUT_SECONDS = 3.0


class ServiceHttpClient:
    def __init__(
        self,
        base_url: str,
        service_token: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._service_token = service_token
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
            transport=transport,
        )

    def post_json(self, path: str, *, json: dict[str, Any], headers: dict[str, str] | None = None) -> httpx.Response:
        """One attempt, no retries. Raises `httpx.HTTPError` on timeouts and connection errors."""
        request_headers = {"Authorization": f"Bearer {self._service_token}", **(headers or {})}
        correlation_id = get_correlation_id()
        if correlation_id:
            request_headers[HEADER] = correlation_id
        return self._client.post(path, json=json, headers=request_headers)
