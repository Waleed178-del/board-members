"""
Minimal MCP server over stdio (JSON-RPC 2.0, newline delimited). Python standard library only.
Implements: initialize, notifications/initialized, ping, tools/list, tools/call.
Each connector declares tools as {name: (description, input_schema, handler)}.
"""
from __future__ import annotations

import json
import sys
import traceback
from typing import Callable

PROTOCOL_VERSION = "2025-06-18"


class ToolError(Exception):
    """Expected, user facing failure. Returned as isError content, not a protocol error."""


Tool = tuple[str, dict, Callable[[dict], object]]


def serve(name: str, version: str, tools: dict[str, Tool], instructions: str = "") -> None:
    def reply(msg_id, result=None, error=None):
        out = {"jsonrpc": "2.0", "id": msg_id}
        if error is not None:
            out["error"] = error
        else:
            out["result"] = result
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply(None, error={"code": -32700, "message": "parse error"})
            continue
        method, msg_id, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if msg_id is None:  # notification
            continue
        if method == "initialize":
            reply(msg_id, {
                "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": name, "version": version},
                "instructions": instructions,
            })
        elif method == "ping":
            reply(msg_id, {})
        elif method == "tools/list":
            reply(msg_id, {"tools": [
                {"name": n, "description": d, "inputSchema": s} for n, (d, s, _) in tools.items()
            ]})
        elif method == "tools/call":
            tname = params.get("name")
            if tname not in tools:
                reply(msg_id, error={"code": -32602, "message": f"unknown tool {tname}"})
                continue
            try:
                result = tools[tname][2](params.get("arguments") or {})
                text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2)
                reply(msg_id, {"content": [{"type": "text", "text": text}], "isError": False})
            except ToolError as e:
                reply(msg_id, {"content": [{"type": "text", "text": f"REFUSED: {e}"}], "isError": True})
            except Exception as e:  # noqa: BLE001
                traceback.print_exc(file=sys.stderr)
                reply(msg_id, {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}],
                               "isError": True})
        else:
            reply(msg_id, error={"code": -32601, "message": f"method not found: {method}"})
