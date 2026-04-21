# /// script
# requires-python = ">=3.12"
# ///
from core.plugins.base import PluginBase
from core.plugins.decorators import on_setup, on_run


class GraphPlugin(PluginBase):
    @on_setup
    def setup(self):
        self.state = {"counter": 0}
        return {"output": "Graph plugin ready"}

    @on_run
    def run(self, input=None):
        import json as _json
        input = input or {}
        line_values = input.get("line_values", [1, 2, 3, 4, 5])
        bar_values = input.get("bar_values", [10, 20, 30, 40])
        self.state["counter"] = self.state.get("counter", 0) + 1
        return {
            "html": """
            <div class="graph-container">
              <h3 class="text">Line Graph</h3>
              <canvas class="line-graph" data-values='{line}'></canvas>
            </div>
            <div class="graph-container">
              <h3 class="text">Bar Chart</h3>
              <canvas class="bar-chart" data-values='{bar}'></canvas>
            </div>
            """.format(line=_json.dumps(line_values), bar=_json.dumps(bar_values))
        }


if __name__ == "__main__":
    plugin = GraphPlugin()
    plugin.start()
