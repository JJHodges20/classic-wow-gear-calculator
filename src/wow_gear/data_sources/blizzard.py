"""Blizzard Battle.net Game Data API client for WoW Classic Era items.

Fetches only; normalization is ``wow_gear.processing.blizzard``. Classic Era uses the
``static-classic1x-{region}`` namespace (docs/research/DATA_SOURCES.md). Credentials are the
player's own client id and secret, from the environment or ``.env``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from wow_gear.core.errors import NotFoundError, ProviderNotConfigured, ProviderUnavailable

TOKEN_URL = "https://oauth.battle.net/token"
REGIONS = ("us", "eu", "kr", "tw")


class BlizzardClient:
    def __init__(
        self,
        client_id: str | None,
        client_secret: str | None,
        *,
        region: str = "us",
        locale: str = "en_US",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not client_id or not client_secret:
            raise ProviderNotConfigured(
                "Blizzard API credentials are not set (WOWGEAR_BLIZZARD_CLIENT_ID and "
                "WOWGEAR_BLIZZARD_CLIENT_SECRET in .env)"
            )
        if region not in REGIONS:
            raise ProviderNotConfigured(f"Blizzard region must be one of {', '.join(REGIONS)}")
        self._credentials = (client_id, client_secret)
        self.region = region
        self.locale = locale
        self._clock = clock
        self._token: tuple[str, float] | None = None
        self._http = httpx.Client(timeout=timeout, transport=transport)

    @property
    def namespace(self) -> str:
        return f"static-classic1x-{self.region}"

    @property
    def base_url(self) -> str:
        return f"https://{self.region}.api.blizzard.com"

    def close(self) -> None:
        self._http.close()

    def _access_token(self) -> str:
        if self._token is not None and self._token[1] > self._clock():
            return self._token[0]
        try:
            response = self._http.post(
                TOKEN_URL, data={"grant_type": "client_credentials"}, auth=self._credentials
            )
        except httpx.HTTPError as error:
            raise ProviderUnavailable(f"could not reach Battle.net: {error}") from error
        if response.status_code in (400, 401, 403):
            raise ProviderNotConfigured("Battle.net rejected the client id and secret")
        if response.status_code != 200:
            raise ProviderUnavailable(f"Battle.net token request failed ({response.status_code})")
        body = response.json()
        token = body.get("access_token")
        if not token:
            raise ProviderUnavailable("Battle.net returned no access token")
        lifetime = float(body.get("expires_in", 3600))
        self._token = (str(token), self._clock() + max(60.0, lifetime - 60.0))
        return self._token[0]

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = {"namespace": self.namespace, "locale": self.locale, **params}
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        try:
            response = self._http.get(f"{self.base_url}{path}", params=query, headers=headers)
        except httpx.TimeoutException as error:
            raise ProviderUnavailable("the Blizzard API did not answer in time") from error
        except httpx.HTTPError as error:
            raise ProviderUnavailable(f"could not reach the Blizzard API: {error}") from error
        if response.status_code == 401:
            self._token = None
            raise ProviderUnavailable("the Blizzard API refused the access token")
        if response.status_code == 404:
            raise NotFoundError(f"Blizzard has no item at {path}")
        if response.status_code == 429:
            raise ProviderUnavailable("the Blizzard API rate limit was reached; try again shortly")
        if response.status_code != 200:
            raise ProviderUnavailable(f"the Blizzard API answered {response.status_code}")
        try:
            body = response.json()
        except ValueError as error:
            raise ProviderUnavailable(
                "the Blizzard API sent a response that is not JSON"
            ) from error
        if not isinstance(body, dict):
            raise ProviderUnavailable("the Blizzard API sent an unexpected response")
        return body

    def item(self, item_id: int) -> dict[str, Any]:
        """``GET /data/wow/item/{id}``: one item with its tooltip preview."""
        return self._get(f"/data/wow/item/{int(item_id)}", {})

    def search(self, name: str, page_size: int = 10) -> dict[str, Any]:
        """``GET /data/wow/search/item``: items whose name matches, a page of results."""
        return self._get(
            "/data/wow/search/item",
            {
                f"name.{self.locale}": name,
                "orderby": "id",
                "_page": 1,
                "_pageSize": max(1, min(page_size, 100)),
            },
        )
