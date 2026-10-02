"""Tests for the shared provider HTTP helper, against a local aiohttp test server."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.streckenwacht.const import USER_AGENT, Source
from custom_components.streckenwacht.model import ObservationArea, StreckenwachtEvent
from custom_components.streckenwacht.providers import Provider, ProviderError


class DummyProvider(Provider):
    source = Source.MOBIDATA_BW

    async def async_fetch(
        self, areas: Sequence[ObservationArea]
    ) -> list[StreckenwachtEvent]:
        return []

    async def get(self, url: str) -> object:
        return await self._get_json(url)


async def echo_user_agent(request: web.Request) -> web.Response:
    return web.json_response({"user_agent": request.headers.get("User-Agent")})


async def wrong_content_type(request: web.Request) -> web.Response:
    return web.Response(text='{"ok": true}', content_type="text/plain")


async def not_json(request: web.Request) -> web.Response:
    return web.Response(text="<html>not json</html>", content_type="text/html")


async def server_error(request: web.Request) -> web.Response:
    return web.Response(status=500)


async def slow(request: web.Request) -> web.Response:
    await asyncio.sleep(1)
    return web.json_response({})


@pytest.fixture
async def server() -> AsyncIterator[TestServer]:
    app = web.Application()
    app.router.add_get("/ua", echo_user_agent)
    app.router.add_get("/text", wrong_content_type)
    app.router.add_get("/html", not_json)
    app.router.add_get("/500", server_error)
    app.router.add_get("/slow", slow)
    async with TestServer(app) as test_server:
        yield test_server


@pytest.fixture
async def provider() -> AsyncIterator[DummyProvider]:
    async with aiohttp.ClientSession() as session:
        yield DummyProvider(session)


async def test_sends_user_agent(server: TestServer, provider: DummyProvider) -> None:
    assert await provider.get(str(server.make_url("/ua"))) == {"user_agent": USER_AGENT}


async def test_accepts_wrong_content_type(
    server: TestServer, provider: DummyProvider
) -> None:
    assert await provider.get(str(server.make_url("/text"))) == {"ok": True}


@pytest.mark.parametrize("path", ["/html", "/500", "/missing"])
async def test_errors_become_provider_error(
    server: TestServer, provider: DummyProvider, path: str
) -> None:
    with pytest.raises(ProviderError):
        await provider.get(str(server.make_url(path)))


async def test_timeout_becomes_provider_error(
    server: TestServer, provider: DummyProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "custom_components.streckenwacht.providers.REQUEST_TIMEOUT", 0.1
    )
    with pytest.raises(ProviderError, match="Timeout"):
        await provider.get(str(server.make_url("/slow")))


async def test_connection_error_becomes_provider_error(
    provider: DummyProvider,
) -> None:
    # Port 1 on localhost is closed: connection refused.
    with pytest.raises(ProviderError):
        await provider.get("http://127.0.0.1:1/")
