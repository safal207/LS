from __future__ import annotations

import json
import sys
from typing import Any

from .mcp_resources import MCPResourceRegistry
from .mcp_tools import MCPToolRegistry, MCPValidationError


class LSMCPServer:
    """Minimal MCP-compatible façade for stdio integration."""

    def __init__(self, tool_registry: MCPToolRegistry | None = None) -> None:
        self.tools = tool_registry or MCPToolRegistry()
        self.resources = MCPResourceRegistry(self.tools.task_manager)

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        action = request.get("action")
        if action == "tools/list":
            return {"tools": self.tools.list_tools()}
        if action == "tools/call":
            name = str(request["name"])
            arguments = request.get("arguments", {})
            return {"result": self.tools.call_tool(name, arguments)}
        if action == "resources/list":
            return {
                "resources": [
                    {"uri": ref.uri, "name": ref.name}
                    for ref in self.resources.list_resources()
                ]
            }
        if action == "resources/read":
            uri = str(request["uri"])
            return {"resource": self.resources.read_resource(uri)}
        raise MCPValidationError(f"Unsupported action: {action}")


def run_stdio_server() -> int:
    server = LSMCPServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = {"ok": True, **server.handle(request)}
        except Exception as exc:  # deliberate boundary for protocol errors
            response = {"ok": False, "error": str(exc)}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_stdio_server())
