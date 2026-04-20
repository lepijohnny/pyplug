from pathlib import Path
from typing import Dict

from .runner import PluginRunner


def discover_plugins(plugin_dirs: list[Path]) -> Dict[str, PluginRunner]:
    """Scan plugin directories and return a dict of plugin_id -> PluginRunner."""
    plugins: Dict[str, PluginRunner] = {}
    for plugin_dir in plugin_dirs:
        if not plugin_dir.is_dir():
            continue
        for entry in sorted(plugin_dir.iterdir()):
            script = entry / "__init__.py"
            if entry.is_dir() and script.exists():
                plugin_id = entry.name
                if plugin_id not in plugins:
                    plugins[plugin_id] = PluginRunner(entry)
    return plugins
