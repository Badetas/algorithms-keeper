import pytest
from aiohttp import web

from algorithms_keeper import __main__ as main
from algorithms_keeper.constants import SOURCE_CODE_URL

from .utils import number


@pytest.fixture
def client(loop, aiohttp_client):  # type: ignore
    app = web.Application()
    app.router.add_get("/", main.index)
    app.router.add_get("/health", main.health)
    app.router.add_post("/", main.main)
    return loop.run_until_complete(aiohttp_client(app))


@pytest.mark.asyncio
async def test_ping(client):  # type: ignore
    headers = {"X-GitHub-Event": "ping", "X-GitHub-Delivery": "1234"}
    data = {"zen": "testing is good"}
    response = await client.post("/", headers=headers, json=data)
    assert response.status == 200


@pytest.mark.asyncio
async def test_failure(client):  # type: ignore
    # Even in the face of an exception, the server should not crash.
    # Missing key headers.
    response = await client.post("/", headers={})
    assert response.status == 500


@pytest.mark.asyncio
async def test_success(client):  # type: ignore
    headers = {"X-GitHub-Event": "project", "X-GitHub-Delivery": "1234"}
    # Sending a payload that shouldn't trigger any networking, but no errors
    # either.
    data = {"action": "created", "installation": {"id": number}}
    response = await client.post("/", headers=headers, json=data)
    assert response.status == 200


@pytest.mark.asyncio
async def test_redirect(client):  # type: ignore
    response = await client.get("/", allow_redirects=False)
    assert response.status == 302
    assert response.headers["Location"] == SOURCE_CODE_URL
    response = await client.get("/", allow_redirects=True)
    assert response.status == 200
    assert str(response.url) == SOURCE_CODE_URL


@pytest.mark.asyncio
async def test_health(client):  # type: ignore
    response = await client.get("/health")
    assert response.status == 200
    assert await response.text() == "OK"
