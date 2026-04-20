"""Test FastAPI endpoints and plugin lifecycle."""

import os
import sys

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Simulate --dev for arg parsing
os.environ["PYPLUG_ENV"] = "dev"
if "--dev" not in sys.argv:
    sys.argv.append("--dev")

from core.app import app, plugins, PLUGIN_FOLDERS
from core.plugins.loader import discover_plugins

pytestmark = pytest.mark.asyncio(loop_scope="function")


@pytest_asyncio.fixture(autouse=True)
async def reset_plugins():
    """Reset plugins before each test."""
    for runner in plugins.values():
        await runner.kill()
    plugins.clear()
    plugins.update(discover_plugins(PLUGIN_FOLDERS))
    yield
    for runner in plugins.values():
        await runner.kill()
    plugins.clear()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_list_plugins(client):
    resp = await client.get("/api/plugins")
    assert resp.status_code == 200
    data = resp.json()
    assert "my_plugin" in data
    assert "graph_plugin" in data
    assert data["my_plugin"]["status"] == "uninitialized"


async def test_setup(client):
    resp = await client.post("/api/plugins/my_plugin/setup")
    assert resp.status_code == 200
    data = resp.json()
    assert data["payload"]["output"] == "Plugin initialized"
    assert data["state"]["counter"] == 0


async def test_run_requires_setup(client):
    resp = await client.post("/api/plugins/my_plugin/run")
    assert resp.status_code == 409


async def test_setup_run_returns_html(client):
    await client.post("/api/plugins/my_plugin/setup")
    resp = await client.post("/api/plugins/my_plugin/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "payload" in data
    assert "state" in data
    assert "html" in data
    assert data["html"]


async def test_multiple_runs(client):
    await client.post("/api/plugins/my_plugin/setup")

    resp1 = await client.post("/api/plugins/my_plugin/run")
    resp2 = await client.post("/api/plugins/my_plugin/run")
    resp3 = await client.post("/api/plugins/my_plugin/run")

    assert resp1.json()["state"]["counter"] == 1
    assert resp2.json()["state"]["counter"] == 2
    assert resp3.json()["state"]["counter"] == 3


async def test_teardown_requires_setup(client):
    resp = await client.post("/api/plugins/my_plugin/teardown")
    assert resp.status_code == 409


async def test_full_lifecycle(client):
    resp = await client.post("/api/plugins/my_plugin/setup")
    assert resp.status_code == 200

    resp = await client.post("/api/plugins/my_plugin/run")
    assert resp.status_code == 200
    assert resp.json()["state"]["counter"] == 1

    resp = await client.post("/api/plugins/my_plugin/teardown")
    assert resp.status_code == 200
    assert resp.json()["state"]["message"] == "Goodbye!"

    resp = await client.get("/api/plugins")
    assert resp.json()["my_plugin"]["status"] == "teardown"

    # Can setup again after teardown
    resp = await client.post("/api/plugins/my_plugin/setup")
    assert resp.status_code == 200


async def test_kill(client):
    resp = await client.post("/api/plugins/my_plugin/kill")
    assert resp.status_code == 200

    resp = await client.get("/api/plugins")
    assert "my_plugin" not in resp.json()


async def test_reload_after_kill(client):
    await client.post("/api/plugins/my_plugin/kill")
    resp = await client.get("/api/plugins")
    assert "my_plugin" not in resp.json()

    resp = await client.post("/reload")
    assert resp.status_code == 200

    resp = await client.get("/api/plugins")
    assert "my_plugin" in resp.json()


async def test_plugin_not_found(client):
    resp = await client.post("/api/plugins/nonexistent/setup")
    assert resp.status_code == 404


async def test_double_setup_rejected(client):
    await client.post("/api/plugins/my_plugin/setup")
    resp = await client.post("/api/plugins/my_plugin/setup")
    assert resp.status_code == 409
