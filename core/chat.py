from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

import requests

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
        # Start each conversation with a system message that nudges the model
        # toward actually using tools to modify the Ghidra project rather than
        # just suggesting tool calls.
        self.messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are an assistant working with a reverse engineer in Ghidra. "
                    "You have access to MCP tools that can query and modify the loaded "
                    "program (for example: listing functions, decompiling, renaming "
                    "functions or variables, setting comments, etc.). "
                    "When the user asks you to perform an action that can be done with "
                    "these tools, you should CALL THE TOOLS directly and continue "
                    "calling additional tools as needed to accomplish the task, rather "
                    "than only describing JSON examples of tool calls. "
                    "After you run tools, summarize what you did and the key results in "
                    "clear natural language. Do not show raw tool JSON back to the user "
                    "unless they explicitly ask for it."
                ),
            }
        ]

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

        # Some Ollama deployments may still stream multiple JSON objects or
        # server-sent events even when stream=False, which breaks response.json().
        # To be robust, always parse the raw text ourselves and take the last
        # non-empty JSON line.
        text = response.text.strip()
        if not text:
            raise RuntimeError("Empty response from Ollama /api/chat")

        raw_lines = [
            line
            for line in text.splitlines()
            if line.strip() and line.strip() != "[DONE]"
        ]
        if not raw_lines:
            raise RuntimeError(f"Unexpected response from Ollama: {text!r}")

        # Handle possible SSE-style 'data: {...}' lines.
        cleaned_lines: List[str] = []
        for line in raw_lines:
            line = line.strip()
            if line.startswith("data:"):
                line = line[len("data:") :].strip()
            cleaned_lines.append(line)

        return json.loads(cleaned_lines[-1])

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

            # Some models may emit the tool call structure directly as JSON in
            # `content` (often inside ```json fences) instead of using the
            # `tool_calls` field. Detect that pattern and synthesize a
            # tool_call so we still execute the tool.
            if not tool_calls and isinstance(content, str):
                json_candidate: Optional[str] = None

                # Prefer the last fenced ```json block if present.
                fence_matches = list(
                    re.finditer(r"```(?:json)?\s*([\s\S]*?)```", content, re.IGNORECASE)
                )
                if fence_matches:
                    json_candidate = fence_matches[-1].group(1).strip()
                else:
                    json_candidate = content.strip()

                try:
                    maybe_call = json.loads(json_candidate)

                    def _calls_from_obj(obj: Any) -> List[Dict[str, Any]]:
                        calls: List[Dict[str, Any]] = []
                        if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
                            name = obj["name"]
                            if name in self._tool_clients:
                                calls.append(
                                    {
                                        "function": {
                                            "name": name,
                                            "arguments": obj.get("arguments", {}) or {},
                                        }
                                    }
                                )
                        elif isinstance(obj, list):
                            for item in obj:
                                calls.extend(_calls_from_obj(item))
                        return calls

                    synthesized = _calls_from_obj(maybe_call)
                    if synthesized:
                        tool_calls = synthesized
                        # Clear the content so we don't just echo the JSON back.
                        content = ""
                except Exception:
                    # If parsing fails, just treat it as normal content.
                    pass

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



