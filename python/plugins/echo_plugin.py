from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _EchoEvent:
    type: str
    payload: dict


class EchoPlugin:
    name = "echo_plugin"

    def __init__(self):
        self._handler = None

    def setup(self, ctx):
        def on_echo(event):
            text = event.payload.get("text", "")
            ctx.event_bus.publish(_EchoEvent("echo_response", {"text": text}))

        self._handler = on_echo
        ctx.event_bus.subscribe("echo_request", on_echo)
        ctx.services.register("echo_plugin_status", {"state": "ready"})

    def shutdown(self, ctx):
        if self._handler is not None:
            ctx.event_bus.unsubscribe("echo_request", self._handler)
        ctx.services.unregister("echo_plugin_status")


plugin = EchoPlugin()
