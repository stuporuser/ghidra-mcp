from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import requests

try:  # Optional Claude support – kept for backwards compatibility.
    from core.claude import Claude  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Claude = object  # type: ignore[misc,assignment]

from core.ghidra_mcp_client import MCPClient
from core.tools import ToolManager


class ChatOllama:
    """
    Ollama-backed chat loop with MCP tool calling.

    This class maintains a conversation history compatible with Ollama's
    /api/chat endpoint and uses ToolManager to advertise and execute MCP
    tools whenever the model issues tool calls.
    """

    def __init__(
        self,
        ollama_url: str,
        ollama_model: str,
        clients: Dict[str, MCPClient],
    ):
        self.ollama_url: str = ollama_url.rstrip("/")
        self.ollama_model: str = ollama_model
        self.clients: Dict[str, MCPClient] = clients
        self.messages: List[Dict[str, Any]] = []

        # Cached tool metadata for Ollama tool calling
        self._ollama_tools: Optional[List[Dict[str, Any]]] = None
        self._tool_clients: Optional[Dict[str, MCPClient]] = None

    async def _ensure_tools_loaded(self) -> None:
        if self._ollama_tools is None or self._tool_clients is None:
            tools, tool_clients = await ToolManager.build_ollama_tools(self.clients)
            self._ollama_tools = tools
            self._tool_clients = tool_clients

    async def _process_query(self, query: str) -> None:
        self.messages.append({"role": "user", "content": query})

    def _chat_sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous helper for calling Ollama's HTTP chat API.
        """
        response = requests.post(
            f"{self.ollama_url}/api/chat", json=payload, timeout=60
        )
        response.raise_for_status()
        return response.json()

    async def _chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Run the blocking HTTP request in a thread so we don't block the event loop.
        return await asyncio.to_thread(self._chat_sync, payload)

    async def run(self, query: str) -> str:
        """
        Run an agentic chat loop for a single user query.

        The loop continues calling Ollama while the model requests tools,
        executing those tools via MCP and feeding the results back into the
        conversation until no further tool calls are requested.
        """
        await self._process_query(query)
        await self._ensure_tools_loaded()

        assert self._ollama_tools is not None
        assert self._tool_clients is not None

        final_text_response = ""

        while True:
            payload: Dict[str, Any] = {
                "model": self.ollama_model,
                "messages": self.messages,
                "tools": self._ollama_tools,
                "stream": False,
            }

            raw = await self._chat(payload)
            message = raw.get("message", {}) if isinstance(raw, dict) else {}

            thinking = message.get("thinking") or ""
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or []

            # Record the assistant's message (including any thinking/tool_calls)
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": content,
            }
            if thinking:
                assistant_msg["thinking"] = thinking
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            self.messages.append(assistant_msg)

            if not tool_calls:
                # No more tools requested – we're done.
                final_text_response = content
                break

            # Execute requested tools via MCP and append their outputs.
            tool_messages = await ToolManager.execute_tool_calls(
                tool_calls, self._tool_clients
            )
            self.messages.extend(tool_messages)

        return final_text_response


class Chat:
    """
    Legacy Claude-based chat wrapper.

    This path is kept only for backwards compatibility. It is not wired into
    the current CLI and will raise if instantiated without Claude support.
    """

    def __init__(self, claude_service: Claude, clients: Dict[str, MCPClient]):
        if Claude is object:
            raise RuntimeError(
                "Claude-based Chat is not available because anthropic/Claude "
                "dependencies are not installed. Use ChatOllama instead."
            )

        self.claude_service: Claude = claude_service
        self.clients: Dict[str, MCPClient] = clients
        self.messages: List[Dict[str, Any]] = []

    async def _process_query(self, query: str) -> None:
        self.messages.append({"role": "user", "content": query})

    async def run(self, query: str) -> str:
        raise RuntimeError(
            "Claude-based Chat.run is no longer supported in this project. "
            "Please migrate to ChatOllama."
        )
