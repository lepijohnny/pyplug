# PyPlug: Pluggable Core Application with FastAPI and Svelte

## Overview
A Python-based pluggable core application where plugins are loaded as scripts with PEP 723 dependencies, run in isolated subprocesses using `uv`, and managed via a FastAPI REST API. Includes a Svelte frontend with a component library for UI consistency and JSON-RPC IPC for plugin communication.

---

## Phase 1: Project Setup

### 1.1 Directory Structure
```bash
pyplug/
├── core/                  # FastAPI backend
│   ├── app.py             # Main FastAPI app
│   ├── plugins/           # Plugin management
│   │   ├── base.py        # PluginBase with IPC
│   │   ├── decorators.py  # @on_setup, @on_run, etc.
│   │   ├── loader.py      # Plugin discovery
│   │   └── runner.py      # Process management
│   └── config.py          # Configuration
├── vendor/               # Portable uv binary
├── plugins/              # Default plugin folder
│   └── my_plugin/        # Example plugin
│       └── __init__.py
├── frontend/             # Svelte UI
│   ├── src/              # Svelte source
│   │   ├── App.svelte     # Main app
│   │   ├── PluginDetails.svelte  # Plugin details view
│   │   └── styles/       # CSS
│   │       ├── base.css   # Theme/variables
│   │       ├── components.css  # Component library
│   │       └── main.css   # Entry point
│   └── dist/              # Built UI (served by FastAPI)
└── Skill.md              # Plugin HTML documentation
```

### 1.2 Initialize Project
```bash
mkdir -p ~/Code/pyplug/{core,vendor,plugins,frontend/src/styles}
cd ~/Code/pyplug
```

---

## Phase 2: Backend (FastAPI)

### 2.1 Install Dependencies
```bash
uv add fastapi uvicorn python-multipart pydantic
```

### 2.2 Core FastAPI App (`core/app.py`)
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import subprocess
from pathlib import Path
from .plugins.runner import PluginRunner

app = FastAPI()

# Plugin state management
plugins: Dict[str, PluginRunner] = {}

class Plugin(BaseModel):
    id: str
    name: str
    status: str  # "uninitialized", "setup", "running", "teardown"
    state: Dict[str, Any] = {}

@app.get("/api/plugins", response_model=Dict[str, Plugin])
def list_plugins():
    return {id: runner.get_status() for id, runner in plugins.items()}

@app.post("/api/plugins/{plugin_id}/setup")
def setup_plugin(plugin_id: str):
    runner = plugins.get(plugin_id)
    if not runner or runner.get_status()["status"] not in ["uninitialized", "teardown"]:
        raise HTTPException(409, "Plugin must be uninitialized or teardown to setup")
    result = runner.send_rpc("setup")
    return {
        "payload": result.get("payload", {}),
        "state": result.get("state", {})
    }

@app.post("/api/plugins/{plugin_id}/run")
def run_plugin(plugin_id: str):
    runner = plugins.get(plugin_id)
    if not runner or runner.get_status()["status"] != "setup":
        raise HTTPException(409, "Plugin must be in setup state to run")
    result = runner.send_rpc("run")
    return {
        "payload": result.get("payload", {}),
        "state": result.get("state", {}),
        "html": result.get("html", "")  # Include HTML if present
    }

@app.post("/api/plugins/{plugin_id}/teardown")
def teardown_plugin(plugin_id: str):
    runner = plugins.get(plugin_id)
    if not runner or runner.get_status()["status"] != "running":
        raise HTTPException(409, "Plugin must be running to teardown")
    result = runner.send_rpc("teardown")
    return {
        "payload": result.get("payload", {}),
        "state": result.get("state", {})
    }

@app.post("/api/plugins/{plugin_id}/kill")
def kill_plugin(plugin_id: str):
    runner = plugins.get(plugin_id)
    if not runner:
        raise HTTPException(404, "Plugin not found")
    runner.kill()
    del plugins[plugin_id]
    return {"status": "killed"}

@app.post("/reload")
def reload_plugins():
    # Rescan plugin folders and reload
    return {"status": "reloaded"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
```

---

## Phase 3: Plugin System

### 3.1 Plugin Base Class (`core/plugins/base.py`)
```python
import sys
import json
import signal
from typing import Dict, Any, Callable
from inspect import getmembers

class PluginBase:
    def __init__(self):
        self.state: Dict[str, Any] = {}
        self._rpc_methods = self._discover_rpc_methods()
        self._shutdown = False

    def _discover_rpc_methods(self) -> Dict[str, Callable]:
        """Discover methods marked with decorators."""
        methods = {}
        for name, method in getmembers(self, predicate=callable):
            if hasattr(method, "_rpc_method"):
                methods[method._rpc_method] = method
        return methods

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
            # Check if result contains HTML
            html = result.get("html") if isinstance(result, dict) else None
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "payload": result,
                    "state": self.state,
                    "html": html  # Include HTML if present
                }
            }
        except Exception as e:
            return self._error(request, -32603, str(e))

    def _error(self, request: Dict[str, Any], code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": code, "message": message},
        }

    def on_kill(self):
        """Override this for cleanup on kill."""
        self._shutdown = True
        return {"status": "shutting_down"}

    def run(self):
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
```

### 3.2 Decorators (`core/plugins/decorators.py`)
```python
from typing import Callable

def on_setup(func: Callable):
    func._rpc_method = "setup"
    return func

def on_run(func: Callable):
    func._rpc_method = "run"
    return func

def on_teardown(func: Callable):
    func._rpc_method = "teardown"
    return func

def on_kill(func: Callable):
    func._rpc_method = "kill"
    return func
```

### 3.3 Plugin Loader (`core/plugins/loader.py`)
```python
from pathlib import Path
from .base import PluginBase
import importlib.util

def load_plugin(plugin_path: Path) -> PluginBase:
    """Load a plugin from a folder."""
    plugin_name = plugin_path.name
    script_path = plugin_path / "__init__.py"

    if not script_path.exists():
        raise FileNotFoundError(f"Plugin {plugin_name} not found")

    spec = importlib.util.spec_from_file_location(plugin_name, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name, obj in vars(module).items():
        if isinstance(obj, type) and issubclass(obj, PluginBase):
            return obj()
    raise ValueError(f"No PluginBase subclass found in {plugin_name}")
```

### 3.4 Plugin Runner (`core/plugins/runner.py`)
```python
import subprocess
import json
import signal
from pathlib import Path
from typing import Dict, Any

class PluginRunner:
    def __init__(self, plugin_path: Path):
        self.process = subprocess.Popen(
            ["uv", "run", str(plugin_path / "__init__.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )

    def send_rpc(self, method: str, params: Dict = None) -> Dict:
        """Send a JSON-RPC request."""
        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": method,
            "params": params or {},
        }
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        response = self._read_response()

        if "error" in response:
            raise Exception(f"RPC Error: {response['error']['message']}")
        return response["result"]  # {"payload": {...}, "state": {...}, "html": "..."}

    def _read_response(self) -> Dict:
        """Read a JSON-RPC response."""
        line = self.process.stdout.readline()
        if not line:
            raise EOFError("Plugin process terminated")
        return json.loads(line)

    def get_status(self) -> Dict[str, Any]:
        """Get plugin status and state."""
        try:
            result = self.send_rpc("status")
            return {
                "status": "running",
                "state": result.get("state", {})
            }
        except Exception:
            return {"status": "error", "state": {}}

    def kill(self, timeout: int = 5):
        """Gracefully terminate the plugin."""
        try:
            self.send_rpc("kill")
        except Exception:
            pass

        try:
            self.process.terminate()
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
```

---

## Phase 4: Example Plugin

### 4.1 Custom Plugin (`plugins/my_plugin/__init__.py`)
```python
from core.plugins.base import PluginBase
from core.plugins.decorators import on_setup, on_run, on_teardown, on_kill

class MyPlugin(PluginBase):
    @on_setup
    def setup(self):
        self.state = {"counter": 0, "message": "Hello, PyPlug!"}
        return {
            "output": "Plugin initialized",
            "timestamp": "2023-01-01T00:00:00Z"
        }

    @on_run
    def run(self):
        self.state["counter"] += 1
        return {
            "output": f"Counter: {self.state['counter']}",
            "timestamp": "2023-01-01T00:00:00Z",
            "html": """
            <div class="card">
              <h3 class="text">Plugin Output</h3>
              <p class="text">Counter: {counter}</p>
              <button class="btn btn-primary">Click Me</button>
            </div>
            """.format(counter=self.state["counter"])
        }

    @on_teardown
    def teardown(self):
        self.state["message"] = "Goodbye!"
        return {
            "output": "Plugin torn down",
            "timestamp": "2023-01-01T00:00:00Z"
        }

    @on_kill
    def kill(self):
        print("Plugin received kill signal!", file=sys.stderr)
        return {"status": "shutting_down"}

if __name__ == "__main__":
    plugin = MyPlugin()
    plugin.run()
```

### 4.2 Graph Plugin (`plugins/graph_plugin/__init__.py`)
```python
from core.plugins.base import PluginBase
from core.plugins.decorators import on_run

class GraphPlugin(PluginBase):
    @on_run
    def run(self):
        self.state["counter"] = self.state.get("counter", 0) + 1
        return {
            "html": """
            <div class="graph-container">
              <h3 class="text">Line Graph</h3>
              <canvas class="line-graph" data-values="[1, 2, 3, 4, 5]"></canvas>
            </div>
            <div class="graph-container">
              <h3 class="text">Bar Chart</h3>
              <canvas class="bar-chart" data-values="[10, 20, 30, 40]"></canvas>
            </div>
            <div class="graph-container">
              <h3 class="text">Scatter Plot</h3>
              <canvas class="scatter-plot" data-points="[[1,2], [3,4], [5,6]]"></canvas>
            </div>
            <div class="graph-container">
              <h3 class="text">Image Graph</h3>
              <img class="image-graph" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==" alt="Graph" />
            </div>
            """
        }

if __name__ == "__main__":
    plugin = GraphPlugin()
    plugin.run()
```

---

## Phase 5: Frontend (Svelte)

### 5.1 Install Dependencies
```bash
cd frontend
npm create vite@latest . -- --template svelte
npm install chart.js dompurify
```

### 5.2 Component Library (`frontend/src/styles/components.css`)
```css
/* Base Components */
.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: opacity 0.2s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-primary {
  background: var(--color-accent);
  color: white;
}

.btn-success {
  background: var(--color-success);
  color: white;
}

.btn-error {
  background: var(--color-error);
  color: white;
}

.card {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 1rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.text {
  margin: 0.5rem 0;
  line-height: 1.5;
}

/* Graph Components */
.graph-container {
  background: white;
  border-radius: 4px;
  padding: 1rem;
  margin: 1rem 0;
}

.line-graph, .bar-chart, .scatter-plot {
  height: 300px;
  background: #f9f9f9;
  border-radius: 4px;
}

.image-graph {
  max-width: 100%;
  border-radius: 4px;
}

/* Dark Mode Overrides */
[data-theme="dark"] {
  .card {
    background: #1e1e1e;
    border: 1px solid #333;
  }
  .graph-container {
    background: #1e1e1e;
  }
  .line-graph, .bar-chart, .scatter-plot {
    background: #2d2d2d;
  }
}
```

### 5.3 Main App (`frontend/src/App.svelte`)
```svelte
<script>
  import { onMount } from 'svelte';
  import PluginDetails from './PluginDetails.svelte';
  import DOMPurify from 'dompurify';

  let plugins = [];
  let selectedPlugin = null;
  let theme = 'light';

  onMount(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    fetchPlugins();
  });

  function setTheme(newTheme) {
    theme = newTheme;
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
  }

  function toggleTheme() {
    setTheme(theme === 'light' ? 'dark' : 'light');
  }

  async function fetchPlugins() {
    const res = await fetch("/api/plugins");
    plugins = await res.json();
  }

  function selectPlugin(id) {
    selectedPlugin = plugins[id];
  }
</script>

<div class="container">
  <h1>PyPlug</h1>
  <div class="toolbar">
    <button class="btn btn-primary" on:click={fetchPlugins}>Reload Plugins</button>
    <button class="btn btn-primary" on:click={toggleTheme}>
      {theme === 'light' ? '🌙 Dark' : '☀️ Light'}
    </button>
  </div>

  <div class="layout">
    <div class="plugin-list">
      <h2>Plugins</h2>
      {#if Object.keys(plugins).length === 0}
        <p>No plugins found.</p>
      {:else}
        <ul>
          {#each Object.entries(plugins) as [id, plugin]}
            <li
              class="plugin-item"
              class:selected={selectedPlugin?.id === id}
              on:click={() => selectPlugin(id)}
            >
              <span class="plugin-name">{plugin.name}</span>
              <span class="status-badge status-{plugin.status}">
                {plugin.status}
              </span>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="plugin-details">
      {#if selectedPlugin}
        <PluginDetails plugin={selectedPlugin} />
      {:else}
        <p>Select a plugin to view details.</p>
      {/if}
    </div>
  </div>
</div>

<style>
  :root {
    --color-bg: #f5f5f5;
    --color-fg: #333;
    --color-accent: #3f51b5;
    --color-success: #4CAF50;
    --color-error: #F44336;
    --border-radius: 4px;
  }

  [data-theme="dark"] {
    --color-bg: #121212;
    --color-fg: #e0e0e0;
    --color-accent: #5d73dc;
    --color-success: #66bb6a;
    --color-error: #ef5350;
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.5;
    color: var(--color-fg);
    background: var(--color-bg);
    transition: background 0.3s, color 0.3s;
  }

  .container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1rem;
  }

  .toolbar {
    margin: 1rem 0;
    display: flex;
    gap: 0.5rem;
  }

  .layout {
    display: grid;
    grid-template-columns: 300px 1fr;
    gap: 1rem;
    margin-top: 1rem;
  }

  .plugin-list {
    background: var(--color-bg);
    border-radius: var(--border-radius);
    padding: 1rem;
  }

  .plugin-item {
    padding: 0.5rem;
    border-radius: var(--border-radius);
    cursor: pointer;
    transition: background 0.2s;
    display: flex;
    justify-content: space-between;
  }

  .plugin-item:hover {
    background: rgba(0, 0, 0, 0.1);
  }

  .plugin-item.selected {
    background: var(--color-accent);
    color: white;
  }

  .plugin-details {
    background: var(--color-bg);
    border-radius: var(--border-radius);
    padding: 1rem;
  }

  .status-badge {
    font-size: 0.8rem;
    padding: 0.2rem 0.5rem;
    border-radius: 1rem;
    color: white;
  }

  .status-uninitialized {
    background: var(--color-fg);
  }

  .status-setup {
    background: var(--color-accent);
  }

  .status-running {
    background: var(--color-success);
  }

  .status-teardown {
    background: var(--color-error);
  }
</style>
```

### 5.4 Plugin Details (`frontend/src/PluginDetails.svelte`)
```svelte
<script>
  import { onMount } from 'svelte';
  import { Chart } from 'chart.js/auto';
  import DOMPurify from 'dompurify';

  export let plugin;

  onMount(() => {
    renderGraphs();
  });

  async function setupPlugin() {
    const res = await fetch(`/api/plugins/${plugin.id}/setup`, { method: "POST" });
    const {payload, state} = await res.json();
    plugin = {...plugin, status: "setup", state};
  }

  async function runPlugin() {
    const res = await fetch(`/api/plugins/${plugin.id}/run`, { method: "POST" });
    const {payload, state, html} = await res.json();
    plugin = {...plugin, status: "running", state};
    // Sanitize and render HTML
    if (html) {
      const htmlContainer = document.querySelector('.html-container');
      if (htmlContainer) {
        htmlContainer.innerHTML = DOMPurify.sanitize(html);
        renderGraphs();  // Re-render graphs after HTML update
      }
    }
  }

  async function teardownPlugin() {
    const res = await fetch(`/api/plugins/${plugin.id}/teardown`, { method: "POST" });
    const {payload, state} = await res.json();
    plugin = {...plugin, status: "teardown", state};
  }

  async function killPlugin() {
    await fetch(`/api/plugins/${plugin.id}/kill`, { method: "POST" });
    plugin = null;
  }

  function renderGraphs() {
    // Line Graphs
    document.querySelectorAll('.line-graph').forEach(el => {
      const values = JSON.parse(el.dataset.values || '[]');
      new Chart(el, {
        type: 'line',
        data: {
          labels: values.map((_, i) => `Point ${i + 1}`),
          datasets: [{ data: values, borderColor: 'rgb(75, 192, 192)', tension: 0.1 }]
        }
      });
    });

    // Bar Charts
    document.querySelectorAll('.bar-chart').forEach(el => {
      const values = JSON.parse(el.dataset.values || '[]');
      new Chart(el, {
        type: 'bar',
        data: {
          labels: values.map((_, i) => `Bar ${i + 1}`),
          datasets: [{ data: values, backgroundColor: 'rgb(54, 162, 235)' }]
        }
      });
    });

    // Scatter Plots
    document.querySelectorAll('.scatter-plot').forEach(el => {
      const points = JSON.parse(el.dataset.points || '[]');
      new Chart(el, {
        type: 'scatter',
        data: {
          datasets: [{
            data: points.map(p => ({ x: p[0], y: p[1] })),
            backgroundColor: 'rgb(255, 99, 132)'
          }]
        }
      });
    });
  }
</script>

{#if plugin}
  <h2>{plugin.name}</h2>
  <div class="plugin-header">
    <span class="status-badge status-{plugin.status}">
      {plugin.status}
    </span>
  </div>

  <div class="plugin-state">
    <h3>State</h3>
    <pre>{JSON.stringify(plugin.state, null, 2)}</pre>
  </div>

  <div class="plugin-actions">
    <button
      class="btn btn-setup"
      on:click={setupPlugin}
      disabled={plugin.status !== "uninitialized" && plugin.status !== "teardown"}
    >
      Setup
    </button>
    <button
      class="btn btn-run"
      on:click={runPlugin}
      disabled={plugin.status !== "setup"}
    >
      Run
    </button>
    <button
      class="btn btn-teardown"
      on:click={teardownPlugin}
      disabled={plugin.status !== "running"}
    >
      Teardown
    </button>
    <button class="btn btn-kill" on:click={killPlugin}>
      Kill
    </button>
  </div>

  <div class="html-container"></div>
{/if}

<style>
  .plugin-header {
    margin: 1rem 0;
  }

  .plugin-state {
    margin: 1rem 0;
  }

  .plugin-state pre {
    background: var(--color-bg);
    padding: 0.5rem;
    border-radius: var(--border-radius);
    max-height: 300px;
    overflow: auto;
  }

  .plugin-actions {
    display: flex;
    gap: 0.5rem;
    margin: 1rem 0;
  }

  .html-container {
    margin-top: 1rem;
  }
</style>
```

### 5.5 Build and Serve UI
```bash
cd frontend
npm run build
```
Update FastAPI to serve the UI:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="../frontend/dist", html=True))
```

---

## Phase 6: Documentation

### 6.1 `Skill.md` (Plugin HTML Guide)
```markdown
# Plugin HTML Components

Plugins can return HTML to render in the PyPlug shell. Use the following components for consistency:

## Buttons
```html
<button class="btn btn-primary">Primary</button>
<button class="btn btn-success">Success</button>
<button class="btn btn-error">Error</button>
```

## Cards
```html
<div class="card">
  <h3>Card Title</h3>
  <p class="text">Card content</p>
</div>
```

## Graphs

### Line Graph
```html
<div class="graph-container">
  <h3 class="text">Line Graph</h3>
  <canvas class="line-graph" data-values="[1, 2, 3, 4, 5]"></canvas>
</div>
```

### Bar Chart
```html
<div class="graph-container">
  <h3 class="text">Bar Chart</h3>
  <canvas class="bar-chart" data-values="[10, 20, 30, 40]"></canvas>
</div>
```

### Scatter Plot
```html
<div class="graph-container">
  <h3 class="text">Scatter Plot</h3>
  <canvas class="scatter-plot" data-points="[[1,2], [3,4], [5,6]]"></canvas>
</div>
```

### Image Graph
```html
<div class="graph-container">
  <h3 class="text">Image Graph</h3>
  <img class="image-graph" src="data:image/png;base64,..." alt="Graph" />
</div>
```

## Rules
1. **No Inline Styles**: Use shell classes only.
2. **No Scripts**: Scripts are stripped for security.
3. **Sanitized**: HTML is sanitized before rendering.
```

---

## Phase 7: Testing

### 7.1 Test Plugin Lifecycle
1. Create a test plugin (`plugins/test_plugin/__init__.py`):
   ```python
   from core.plugins.base import PluginBase
   from core.plugins.decorators import on_setup, on_run, on_teardown, on_kill

   class TestPlugin(PluginBase):
       @on_setup
       def setup(self):
           self.state = {"counter": 0}
           return {"output": "Setup complete"}

       @on_run
       def run(self):
           self.state["counter"] += 1
           return {
               "output": f"Counter: {self.state['counter']}",
               "html": """
               <div class="card">
                 <h3 class="text">Plugin Output</h3>
                 <p class="text">Counter: {counter}</p>
               </div>
               """.format(counter=self.state["counter"])
           }

       @on_teardown
       def teardown(self):
           return {"output": "Teardown complete"}

       @on_kill
       def kill(self):
           return {"status": "shutting_down"}
   ```

2. Start FastAPI:
   ```bash
   cd core
   uvicorn app:app --reload
   ```

3. Test endpoints:
   - `GET /api/plugins`: List plugins.
   - `POST /api/plugins/test_plugin/setup`: Setup.
   - `POST /api/plugins/test_plugin/run`: Run (returns HTML).
   - `POST /api/plugins/test_plugin/kill`: Kill.

---

## Key Features

### 1. JSON-RPC IPC
- Plugins communicate via stdin/stdout with JSON-RPC 2.0.
- Each response includes `payload`, `state`, and `html` (if present).

### 2. Plugin Lifecycle
- **Setup → Run → Teardown**: Enforced by decorators.
- **Kill**: Graceful shutdown with cleanup.

### 3. Frontend
- **List View**: Compact list of plugins.
- **Details View**: Full plugin state and HTML output.
- **Dark Mode**: Toggle between light/dark themes.

### 4. Component Library
- Buttons, cards, graphs with consistent styling.
- Plugins use shell classes (no inline styles).

### 5. Graph Support
- Line, bar, scatter, and image graphs via Chart.js.

---

## Next Steps
1. Add plugin discovery (scan `PLUGIN_FOLDERS`).
2. Implement heartbeat for unresponsive plugins.
3. Add logging and monitoring.
4. Extend UI with logs and plugin metadata.
