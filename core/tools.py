from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from mcp.types import CallToolResult, TextContent

from core.ghidra_mcp_client import MCPClient


class ToolManager:
    """
    Helper for discovering MCP tools and executing tool calls for Ollama.

    This version is Anthropic-agnostic and is designed to work with Ollama's
    tool calling API. It exposes two main entry points:

    - build_ollama_tools: return JSON-schema tool definitions for Ollama.
    - execute_tool_calls: execute a list of tool calls against MCP clients and
      return 'tool' role chat messages to append to the conversation.
    """

    @classmethod
    async def build_ollama_tools(
        cls, clients: Dict[str, MCPClient]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, MCPClient]]:
        """
        Build Ollama-compatible JSON schema tool definitions from MCP tools.

        Returns:
            tools: List of objects in the form expected by Ollama's HTTP API:
                {
                    "type": "function",
                    "function": {
                        "name": str,
                        "description": str,
                        "parameters": { ... JSON Schema ... },
                    },
                }
            tool_clients: Mapping from tool name -> MCPClient that owns it.
        """
        tools: List[Dict[str, Any]] = []
        tool_clients: Dict[str, MCPClient] = {}

        for client in clients.values():
            # Use the underlying MCP session directly so we can access full
            # Tool metadata including JSON input schema.
            session = client.session()
            result = await session.list_tools()

            for tool in result.tools:
                # Ensure we always have a parameters object; fall back to a
                # generic schema if the server does not provide one.
                parameters: Dict[str, Any] = getattr(tool, "inputSchema", None) or {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                }

                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": getattr(tool, "description", "") or "",
                            "parameters": parameters,
                        },
                    }
                )
                # If multiple MCP clients expose the same tool name, the last
                # one wins. In practice tool names are expected to be unique.
                tool_clients[tool.name] = client

        return tools, tool_clients

    @classmethod
    async def execute_tool_calls(
        cls,
        tool_calls: List[Any],
        tool_clients: Dict[str, MCPClient],
    ) -> List[Dict[str, Any]]:
        """
        Execute Ollama tool_calls against MCP clients and return chat messages.

        Args:
            tool_calls: The list of tool call objects from an Ollama response.
                Each element is expected to have a `function` with `name` and
                `arguments` attributes (or dict keys), as documented in the
                Ollama tool calling docs.
            tool_clients: Mapping from tool name to MCPClient produced by
                build_ollama_tools.

        Returns:
            A list of messages like:
                {
                    "role": "tool",
                    "tool_name": <tool name>,
                    "content": <stringified result>,
                }
            suitable for appending to the Ollama conversation history.
        """

        def _get_attr_or_key(obj: Any, name: str, default: Any = None) -> Any:
            if hasattr(obj, name):
                return getattr(obj, name)
            if isinstance(obj, dict):
                return obj.get(name, default)
            return default

        tool_messages: List[Dict[str, Any]] = []

        for call in tool_calls:
            fn = _get_attr_or_key(call, "function")
            if fn is None:
                continue

            tool_name = _get_attr_or_key(fn, "name")
            if not tool_name:
                continue

            arguments = _get_attr_or_key(fn, "arguments", {}) or {}
            if not isinstance(arguments, dict):
                # Ollama should always send a dict of arguments, but we guard
                # against unexpected formats.
                try:
                    arguments = json.loads(arguments)
                except Exception:
                    arguments = {"raw": str(arguments)}

            client = tool_clients.get(tool_name)
            if client is None:
                # If we cannot find a client, surface this back to the model.
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": f"Error: no MCP client exposes tool '{tool_name}'.",
                    }
                )
                continue

            try:
                session = client.session()
                result: CallToolResult | None = await session.call_tool(
                    tool_name, arguments
                )
            except Exception as exc:  # pragma: no cover - defensive
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": f"Error executing tool '{tool_name}': {exc}",
                    }
                )
                continue

            # Normalise the MCP CallToolResult into a single text blob.
            text_parts: List[str] = []
            if result and getattr(result, "content", None):
                for item in result.content:
                    if isinstance(item, TextContent):
                        text_parts.append(item.text)

            if not text_parts:
                # Fall back to a JSON dump of the whole result if we didn't see
                # any TextContent items.
                safe_result = {
                    "isError": getattr(result, "isError", False),
                    "content": getattr(result, "content", []),
                }
                text_parts.append(json.dumps(safe_result, default=str))

            tool_messages.append(
                {
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": "\n".join(text_parts),
                }
            )

        return tool_messages
