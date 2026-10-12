"""The demo's tools over MCP, for the Claude Code CLI to call.

The CLI reaches custom tools only through an MCP server. The hrono server
answers MCP's streamable HTTP transport at one URL per conversation, with
each JSON-RPC message answered by one JSON body: the CLI needs only
``initialize``, ``tools/list`` and ``tools/call`` of it.
"""

from __future__ import annotations

from hrono.demo.tools import TOOLS, Library

NAME = "hrono"  # the CLI calls a tool mcp__<NAME>__<tool>
VERSION = "2025-06-18"

Message = dict[str, object]


def answer(message: Message, library: Library) -> Message | None:
    """The JSON-RPC reply to ``message``; None for a notification."""
    ident = message.get("id")
    if ident is None:
        return None
    method = message.get("method")
    params = message.get("params")
    params = params if isinstance(params, dict) else {}
    if method == "initialize":
        asked = params.get("protocolVersion")
        result: Message = {
            "protocolVersion": asked if isinstance(asked, str) else VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": NAME, "version": "1"},
        }
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.schema(),
                }
                for tool in TOOLS
            ]
        }
    elif method == "tools/call":
        args = params.get("arguments")
        text = library.call(
            str(params.get("name", "")), args if isinstance(args, dict) else {}
        )
        result = {"content": [{"type": "text", "text": text}]}
    elif method == "ping":
        result = {}
    else:
        return {
            "jsonrpc": "2.0",
            "id": ident,
            "error": {"code": -32601, "message": f"no method {method}"},
        }
    return {"jsonrpc": "2.0", "id": ident, "result": result}
