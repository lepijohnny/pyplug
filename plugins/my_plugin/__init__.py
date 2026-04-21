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
    def run(self, input=None):
        input = input or {}
        increment = input.get("increment", 1)
        message = input.get("message", self.state["message"])
        self.state["counter"] += increment
        self.state["message"] = message
        self.log("debug", f"Counter incremented by {increment} to {self.state['counter']}")
        return {
            "output": f"{message} (counter: {self.state['counter']})",
            "html": """
            <div class="card">
              <h3 class="text">{message}</h3>
              <p class="text">Counter: {counter}</p>
            </div>
            """.format(message=message, counter=self.state["counter"]),
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
