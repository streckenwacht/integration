"""Provider interface. Providers are pure Python and must not import Home Assistant.

Each provider fetches everything the configured observation areas need in one
poll cycle (one coordinator per provider). Filtering events per area happens
afterwards via ObservationArea.contains().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any, ClassVar
from urllib.parse import urlencode

import aiohttp

from ..const import REQUEST_TIMEOUT, USER_AGENT, Source
from ..model import ObservationArea, StreckenwachtEvent


class ProviderError(Exception):
    """A provider could not fetch or parse its data."""


class Provider(ABC):
    """Base class for a data source."""

    source: ClassVar[Source]

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        # Conditional requests: request key -> (ETag, decoded JSON). Both APIs
        # answer "304 Not Modified" with an empty body if nothing changed, which
        # saves most of the traffic (Autobahn sends ~750 KB uncompressed per poll).
        self._etags: dict[str, tuple[str, Any]] = {}

    @abstractmethod
    async def async_fetch(
        self, areas: Sequence[ObservationArea]
    ) -> list[StreckenwachtEvent]:
        """Fetch all events needed for the given areas.

        Raises ProviderError if the source is unreachable or its data unusable.
        Single malformed records must be skipped, not fail the whole fetch.
        """

    async def _get_json(self, url: str, params: Mapping[str, str] | None = None) -> Any:
        """GET a URL and decode JSON, mapping every failure to ProviderError.

        Sends If-None-Match when the URL was fetched before and reuses the
        cached data on "304 Not Modified".
        """
        key = f"{url}?{urlencode(sorted(params.items()))}" if params else url
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        cached = self._etags.get(key)
        if cached:
            headers["If-None-Match"] = cached[0]
        try:
            async with self._session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                if response.status == HTTPStatus.NOT_MODIFIED and cached:
                    return cached[1]
                response.raise_for_status()
                data = await response.json(content_type=None)
                if etag := response.headers.get("ETag"):
                    self._etags[key] = (etag, data)
                return data
        except TimeoutError as err:
            raise ProviderError(f"Timeout fetching {url}") from err
        except aiohttp.ClientResponseError as err:
            raise ProviderError(f"HTTP {err.status} fetching {url}") from err
        except aiohttp.ClientError as err:
            raise ProviderError(f"Error fetching {url}: {err}") from err
        except ValueError as err:
            raise ProviderError(f"Invalid JSON from {url}") from err
