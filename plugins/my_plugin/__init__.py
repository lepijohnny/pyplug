# /// script
# requires-python = ">=3.12"
# ///
from core.plugins.base import PluginBase
from core.plugins.decorators import on_setup, on_run, on_teardown, on_kill


class MyPlugin(PluginBase):
    @on_setup
    def setup(self):
        self.state = {"counter": 0, "message": "Hello, PyPlug!"}
        self.log("info", "Plugin setup complete")
        return {"output": "Plugin initialized"}

    @on_run
    def run(self):
        self.state["counter"] += 1
        self.log("debug", f"Counter incremented to {self.state['counter']}")
        return {
            "output": f"Counter: {self.state['counter']}",
            "html": """
            <div class="card">
              <h3 class="text">Plugin Output</h3>
              <p class="text">Counter: {counter}</p>
              <button class="btn btn-primary">Click Me</button>
            </div>
            """.format(counter=self.state["counter"]),
        }

    @on_teardown
    def teardown(self):
        self.state["message"] = "Goodbye!"
        return {"output": "Plugin torn down"}

    @on_kill
    def kill(self):
        self.log("info", "Plugin received kill signal")
        return {"status": "shutting_down"}


if __name__ == "__main__":
    plugin = MyPlugin()
    plugin.start()
