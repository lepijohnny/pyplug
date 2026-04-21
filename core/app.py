import json
import logging
import platform
import sys

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any

from logging.handlers import RotatingFileHandler

_log_dir = Path(__file__).resolve().parent.parent / "logs"
_log_dir.mkdir(exist_ok=True)

_handler = RotatingFileHandler(
    _log_dir / "pyplug.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=5,
)
_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

logging.basicConfig(level=logging.DEBUG, handlers=[
    _handler,
    logging.StreamHandler(),
])

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from .plugins.loader import discover_plugins
from .plugins.runner import PluginRunner

BASE_DIR = Path(__file__).resolve().parent.parent
UV_BINARY = BASE_DIR / "vendor" / ("uv.exe" if platform.system() == "Windows" else "uv")

# Defaults
HOST = "0.0.0.0"
PORT = 8000
PLUGIN_FOLDERS = [Path("/plugins")]

# Parse CLI args
_args = sys.argv[1:]
for i, arg in enumerate(_args):
    if arg == "--host" and i + 1 < len(_args):
        HOST = _args[i + 1]
    elif arg == "--port" and i + 1 < len(_args):
        PORT = int(_args[i + 1])
    elif arg == "--plugins" and i + 1 < len(_args):
        PLUGIN_FOLDERS = [Path(p).expanduser() for p in _args[i + 1].split(",")]
    elif arg == "--dev":
        HOST = "127.0.0.1"
        PLUGIN_FOLDERS = [BASE_DIR / "plugins"]

plugins: Dict[str, PluginRunner] = {}


@asynccontextmanager
async def lifespan(app):
    plugins.update(discover_plugins(PLUGIN_FOLDERS))
    yield
    for runner in plugins.values():
        await runner.kill()

app = FastAPI(title="PyPlug", lifespan=lifespan)


@app.get("/api/plugins")
def list_plugins() -> Dict[str, Any]:
    return {pid: runner.get_status() for pid, runner in plugins.items()}


@app.post("/api/plugins/{plugin_id}/setup")
async def setup_plugin(plugin_id: str):
    runner = plugins.get(plugin_id)
    if not runner:
        raise HTTPException(404, "Plugin not found")
    if runner.status not in ("uninitialized", "teardown"):
        raise HTTPException(409, "Plugin must be uninitialized or teardown to setup")
    result = await runner.send_rpc("setup")
    runner.status = "setup"
    runner.state = result.get("state", {})
    return {"payload": result.get("payload", {}), "state": result.get("state", {})}


@app.get("/api/plugins/{plugin_id}/defaults")
async def get_plugin_defaults(plugin_id: str):
    runner = plugins.get(plugin_id)
    if not runner:
        raise HTTPException(404, "Plugin not found")
    defaults_file = runner.plugin_path / "default.json"
    if not defaults_file.exists():
        return {}
    return json.loads(defaults_file.read_text())


@app.post("/api/plugins/{plugin_id}/run")
async def run_plugin(plugin_id: str, request: Request):
    runner = plugins.get(plugin_id)
    if not runner:
        raise HTTPException(404, "Plugin not found")
    if runner.status != "setup":
        raise HTTPException(409, "Plugin must be in setup state to run")
    body = await request.body()
    params = json.loads(body) if body else {}
    result = await runner.send_rpc("run", params)
    runner.state = result.get("state", {})
    return {
        "payload": result.get("payload", {}),
        "state": result.get("state", {}),
        "html": result.get("html", ""),
    }


@app.post("/api/plugins/{plugin_id}/teardown")
async def teardown_plugin(plugin_id: str):
    runner = plugins.get(plugin_id)
    if not runner:
        raise HTTPException(404, "Plugin not found")
    if runner.status != "setup":
        raise HTTPException(409, "Plugin must be in setup state to teardown")
    result = await runner.send_rpc("teardown")
    runner.status = "teardown"
    runner.state = result.get("state", {})
    return {"payload": result.get("payload", {}), "state": result.get("state", {})}


@app.post("/api/plugins/{plugin_id}/kill")
async def kill_plugin(plugin_id: str):
    runner = plugins.get(plugin_id)
    if not runner:
        raise HTTPException(404, "Plugin not found")
    await runner.kill()
    del plugins[plugin_id]
    return {"status": "killed"}


@app.post("/reload")
async def reload_plugins():
    for runner in plugins.values():
        await runner.kill()
    plugins.clear()
    plugins.update(discover_plugins(PLUGIN_FOLDERS))
    return {"status": "reloaded", "count": len(plugins)}


# Serve frontend if built
dist = BASE_DIR / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=str(dist), html=True))

if __name__ == "__main__":
    import uvicorn

    dev = "--dev" in sys.argv
    uvicorn.run("core.app:app", host=HOST, port=PORT, reload=dev)
