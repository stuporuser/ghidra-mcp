from typing import Any, Dict, List

from mcp.types import CallToolResult, TextContent

from core.chat import ChatOllama
from core.ghidra_mcp_client import MCPClient


class CliChatOllama(ChatOllama):
    """
    CLI-facing chat agent for the Ghidra MCP server.

    This class focuses on MCP tools and the LLM:
    - Exposes convenience methods to list and call MCP tools.
    - Delegates natural-language handling to ChatOllama, which can
      autonomously decide when to call tools via Ollama's tool-calling.
    """

    def __init__(
        self,
        ghidra_client: MCPClient,
        clients: Dict[str, MCPClient],
        ollama_url: str,
        ollama_model: str,
    ):
        super().__init__(
            ollama_url=ollama_url,
            ollama_model=ollama_model,
            clients=clients,
        )

        self.ghidra_client: MCPClient = ghidra_client

    async def list_prompts(self) -> list:
        """
        Placeholder for MCP prompts (unused by the current Ghidra server).
        """
        return []

    async def list_tools(self) -> list[str]:
        """
        Return the list of MCP tool names exposed by the Ghidra server.
        """
        return await self.ghidra_client.list_tools()

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any] | None = None,
    ) -> str:
        """
        Call a single MCP tool directly and return its textual output.

        This is useful for explicit tool invocations from the CLI when you
        want raw Ghidra output in addition to, or instead of, an LLM-mediated
        summary.
        """
        session = self.ghidra_client.session()
        result: CallToolResult | None = await session.call_tool(
            tool_name, arguments or {}
        )

        text_parts: List[str] = []
        if result and getattr(result, "content", None):
            for item in result.content:
                if isinstance(item, TextContent):
                    text_parts.append(item.text)

        if not text_parts:
            return ""

        return "\n".join(text_parts)
