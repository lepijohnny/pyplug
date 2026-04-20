import logging
import sys
import json
import signal
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Any, Callable
from inspect import getmembers

_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)


class PluginBase:
    def __init__(self):
        self.state: Dict[str, Any] = {}
        self._rpc_methods = self._discover_rpc_methods()
        self._shutdown = False
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        name = self.__class__.__name__
        logger = logging.getLogger(f"plugin.{name}")
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            handler = RotatingFileHandler(
                _LOG_DIR / "pyplug.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
            )
            handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            logger.addHandler(handler)
        return logger

    def log(self, level: str, message: str):
        """Log a message. level: 'debug', 'info', 'error'."""
        getattr(self._logger, level, self._logger.info)(message)

    def _handle_rpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle JSON-RPC requests."""
        if self._shutdown:
            return self._error(request, -32000, "Plugin is shutting down")

        if request.get("jsonrpc") != "2.0":
            return self._error(request, -32600, "Invalid JSON-RPC")

        method = request.get("method")
        if method not in self._rpc_methods:
            return self._error(request, -32601, "Method not found")

        try:
            result = self._rpc_methods[method]()
            html = result.get("html") if isinstance(result, dict) else None
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "payload": result,
                    "state": self.state,
                    "html": html,
                },
            }
        except Exception as e:
            self._logger.error(str(e))
            return self._error(request, -32603, str(e))

    def _error(self, request: Dict[str, Any], code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": code, "message": message},
        }

    def _default_teardown(self):
        return {"output": "teardown"}

    def _default_kill(self):
        self._shutdown = True
        return {"status": "shutting_down"}

    def _discover_rpc_methods(self) -> Dict[str, Callable]:
        """Discover methods marked with decorators, with defaults for teardown/kill."""
        methods = {}
        for name, method in getmembers(self, predicate=callable):
            if hasattr(method, "_rpc_method"):
                methods[method._rpc_method] = method
        methods.setdefault("teardown", self._default_teardown)
        methods.setdefault("kill", self._default_kill)
        return methods

    def start(self):
        """Start the RPC server with signal handling."""

        def handle_sigterm(signum, frame):
            self._shutdown = True
            sys.exit(0)

        signal.signal(signal.SIGTERM, handle_sigterm)

        for line in sys.stdin:
            if self._shutdown:
                break

            try:
                request = json.loads(line)
                response = self._handle_rpc(request)
                print(json.dumps(response))
                sys.stdout.flush()
            except json.JSONDecodeError:
                continue
            except Exception as e:
                error = self._error({}, -32603, f"Internal error: {str(e)}")
                print(json.dumps(error))
                sys.stdout.flush()
