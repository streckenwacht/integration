"""Provider interface. Providers are pure Python and must not import Home Assistant.

Each provider fetches everything the configured observation areas need in one
poll cycle (one coordinator per provider). Filtering events per area happens
afterwards via ObservationArea.contains().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

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

    @abstractmethod
    async def async_fetch(
        self, areas: Sequence[ObservationArea]
    ) -> list[StreckenwachtEvent]:
        """Fetch all events needed for the given areas.

        Raises ProviderError if the source is unreachable or its data unusable.
        Single malformed records must be skipped, not fail the whole fetch.
        """

    async def _get_json(self, url: str, params: Mapping[str, str] | None = None) -> Any:
        """GET a URL and decode JSON, mapping every failure to ProviderError."""
        try:
            async with self._session.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except TimeoutError as err:
            raise ProviderError(f"Timeout fetching {url}") from err
        except aiohttp.ClientResponseError as err:
            raise ProviderError(f"HTTP {err.status} fetching {url}") from err
        except aiohttp.ClientError as err:
            raise ProviderError(f"Error fetching {url}: {err}") from err
        except ValueError as err:
            raise ProviderError(f"Invalid JSON from {url}") from err
