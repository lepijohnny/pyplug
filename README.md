# PyPlug

A pluggable core application where plugins are Python scripts with inline dependencies, run in isolated subprocesses via `uv`, and managed through a FastAPI REST API with a Svelte frontend.

## Quick Start

### 1. Download uv

```bash
python3 scripts/download_uv.py
```

This downloads the `uv` binary for your platform into `vendor/`.

### 2. Install dependencies

```bash
uv sync
```

### 3. Run

**Development** (auto-reload, localhost only):

```bash
uv run python -m core.app --dev
```

**Production**:

```bash
uv run python -m core.app
```

Open http://localhost:8000 in your browser.

## CLI Options

```bash
uv run python -m core.app [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--dev` | | Localhost, local `plugins/` folder, auto-reload |
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8000` | Port |
| `--plugins` | `/plugins` | Plugin folders (comma-separated) |

Examples:

```bash
uv run python -m core.app --dev
uv run python -m core.app --plugins ~/.pyplug/plugins
uv run python -m core.app --host 0.0.0.0 --port 9000 --plugins /opt/plugins,~/my-plugins
```

## Logging

Plugins can log via `self.log(level, message)` where level is `debug`, `info`, or `error`. All logs (core + plugins) write to `logs/pyplug.log` (rolling, 5 MB x 5 backups).

## Writing Plugins

Create a folder in the plugins directory with an `__init__.py`:

```
plugins/
  my_plugin/
    __init__.py
```

Declare dependencies using PEP 723 inline metadata and use lifecycle decorators:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy"]
# ///
from core.plugins.base import PluginBase
from core.plugins.decorators import on_setup, on_run, on_teardown

import numpy as np


class MyPlugin(PluginBase):
    @on_setup
    def setup(self):
        self.state = {"values": [1, 2, 3]}
        return {"output": "Ready"}

    @on_run
    def run(self):
        arr = np.array(self.state["values"])
        return {"output": f"mean={arr.mean()}"}

    @on_teardown
    def teardown(self):
        return {"output": "Done"}


if __name__ == "__main__":
    plugin = MyPlugin()
    plugin.start()
```

### Lifecycle

```
setup -> run, run, run, ... -> teardown
```

- `@on_setup` and `@on_run` are required
- `@on_teardown` and `@on_kill` are optional (defaults provided)
- Plugins can return `html` in the run response to render UI (see `Skill.md`)

### Plugin Dependencies

Dependencies declared in the `# /// script` block are automatically installed by `uv` on first run. Each plugin caches its dependencies in its own `.uv-cache/` folder.

## Docker

```bash
docker build -t pyplug .
docker run -p 8000:8000 -v ./plugins:/plugins pyplug
```

Mount your plugins folder to `/plugins` inside the container.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plugins` | List all plugins |
| POST | `/api/plugins/{id}/setup` | Initialize a plugin |
| POST | `/api/plugins/{id}/run` | Run a plugin (repeatable) |
| POST | `/api/plugins/{id}/teardown` | Tear down a plugin |
| POST | `/api/plugins/{id}/kill` | Kill a plugin process |
| POST | `/reload` | Rescan and reload all plugins |
