"""Test PluginBase JSON-RPC handling."""

import json
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MY_PLUGIN = PROJECT_ROOT / "plugins" / "my_plugin" / "__init__.py"
GRAPH_PLUGIN = PROJECT_ROOT / "plugins" / "graph_plugin" / "__init__.py"
UV = PROJECT_ROOT / "vendor" / "uv"


def rpc_request(method, id="1"):
    return json.dumps({"jsonrpc": "2.0", "id": id, "method": method, "params": {}})


def run_plugin(plugin_path, *requests):
    """Send RPC requests to a plugin and return parsed responses."""
    stdin = "\n".join(requests) + "\n"
    env = {"UV_CACHE_DIR": str(plugin_path.parent / ".uv-cache"), "PYTHONPATH": str(PROJECT_ROOT)}
    # Inherit PATH so uv can find python
    import os
    env["PATH"] = os.environ["PATH"]
    env["HOME"] = os.environ.get("HOME", "")

    result = subprocess.run(
        [str(UV), "run", str(plugin_path)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


class TestMyPluginRPC:
    def test_setup(self):
        responses = run_plugin(MY_PLUGIN, rpc_request("setup"))
        assert len(responses) == 1
        r = responses[0]
        assert r["id"] == "1"
        assert r["result"]["state"]["counter"] == 0
        assert r["result"]["payload"]["output"] == "Plugin initialized"

    def test_setup_then_run(self):
        responses = run_plugin(
            MY_PLUGIN,
            rpc_request("setup", "1"),
            rpc_request("run", "2"),
        )
        assert len(responses) == 2
        assert responses[1]["result"]["state"]["counter"] == 1
        assert "html" in responses[1]["result"]["payload"]

    def test_multiple_runs_increment(self):
        responses = run_plugin(
            MY_PLUGIN,
            rpc_request("setup", "1"),
            rpc_request("run", "2"),
            rpc_request("run", "3"),
            rpc_request("run", "4"),
        )
        assert len(responses) == 4
        assert responses[1]["result"]["state"]["counter"] == 1
        assert responses[2]["result"]["state"]["counter"] == 2
        assert responses[3]["result"]["state"]["counter"] == 3

    def test_teardown(self):
        responses = run_plugin(
            MY_PLUGIN,
            rpc_request("setup", "1"),
            rpc_request("run", "2"),
            rpc_request("teardown", "3"),
        )
        assert len(responses) == 3
        assert responses[2]["result"]["state"]["message"] == "Goodbye!"
        assert responses[2]["result"]["payload"]["output"] == "Plugin torn down"

    def test_unknown_method(self):
        responses = run_plugin(MY_PLUGIN, rpc_request("nonexistent"))
        assert len(responses) == 1
        assert "error" in responses[0]
        assert responses[0]["error"]["code"] == -32601

    def test_invalid_jsonrpc_version(self):
        bad_request = json.dumps({"jsonrpc": "1.0", "id": "1", "method": "setup"})
        responses = run_plugin(MY_PLUGIN, bad_request)
        assert len(responses) == 1
        assert "error" in responses[0]
        assert responses[0]["error"]["code"] == -32600


class TestGraphPluginRPC:
    def test_setup_and_run(self):
        responses = run_plugin(
            GRAPH_PLUGIN,
            rpc_request("setup", "1"),
            rpc_request("run", "2"),
        )
        assert len(responses) == 2
        html = responses[1]["result"]["html"]
        assert "line-graph" in html
        assert "bar-chart" in html
        assert "scatter-plot" in html

    def test_default_teardown(self):
        """Graph plugin doesn't define teardown — should use default."""
        responses = run_plugin(
            GRAPH_PLUGIN,
            rpc_request("setup", "1"),
            rpc_request("teardown", "2"),
        )
        assert len(responses) == 2
        assert responses[1]["result"]["payload"]["output"] == "teardown"

    def test_default_kill(self):
        """Graph plugin doesn't define kill — should use default."""
        responses = run_plugin(
            GRAPH_PLUGIN,
            rpc_request("setup", "1"),
            rpc_request("kill", "2"),
        )
        assert len(responses) == 2
        assert responses[1]["result"]["payload"]["status"] == "shutting_down"
