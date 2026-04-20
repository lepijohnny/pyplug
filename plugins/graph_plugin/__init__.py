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
            """
        }


if __name__ == "__main__":
    plugin = GraphPlugin()
    plugin.start()
