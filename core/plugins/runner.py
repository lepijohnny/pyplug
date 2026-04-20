import asyncio
import os
import json
import platform
from pathlib import Path
from typing import Dict, Any, Optional

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
UV_BINARY = _BASE_DIR / "vendor" / ("uv.exe" if platform.system() == "Windows" else "uv")


class PluginRunner:
    def __init__(self, plugin_path: Path):
        self.plugin_path = plugin_path
        self.plugin_id = plugin_path.name
        self.name = plugin_path.name
        self.status = "uninitialized"
        self.state: Dict[str, Any] = {}
        self.process: Optional[asyncio.subprocess.Process] = None

    async def _ensure_process(self):
        """Start the subprocess if not already running."""
        if self.process is None or self.process.returncode is not None:
            env = os.environ.copy()
            env["UV_CACHE_DIR"] = str(self.plugin_path / ".uv-cache")
            env["PYTHONPATH"] = str(_BASE_DIR)
            self.process = await asyncio.create_subprocess_exec(
                str(UV_BINARY), "run", str(self.plugin_path / "__init__.py"),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

    async def send_rpc(self, method: str, params: Dict = None) -> Dict:
        """Send a JSON-RPC request."""
        await self._ensure_process()
        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": method,
            "params": params or {},
        }
        self.process.stdin.write((json.dumps(request) + "\n").encode())
        await self.process.stdin.drain()

        line = await self.process.stdout.readline()
        if not line:
            raise EOFError("Plugin process terminated")
        response = json.loads(line)

        if "error" in response:
            raise Exception(f"RPC Error: {response['error']['message']}")
        return response["result"]

    def get_status(self) -> Dict[str, Any]:
        """Get plugin status and state."""
        return {
            "id": self.plugin_id,
            "name": self.name,
            "status": self.status,
            "state": self.state,
        }

    async def kill(self, timeout: int = 5):
        """Gracefully terminate the plugin."""
        if self.process and self.process.returncode is None:
            try:
                await asyncio.wait_for(self.send_rpc("kill"), timeout=2)
            except Exception:
                pass
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                self.process.kill()
        self.status = "killed"
        self.process = None
