"""
Legacy Claude wrapper.

This module is retained for backwards compatibility only. The current
project wiring uses Ollama exclusively for the chat CLI, so Claude is
not required at runtime. The import of anthropic is guarded so that the
rest of the project can run without the Anthropic SDK installed.
"""

from __future__ import annotations

from typing import Any, List

try:  # pragma: no cover - optional dependency
    from anthropic import Anthropic
    from anthropic.types import Message
except Exception:  # pragma: no cover - optional dependency
    Anthropic = None  # type: ignore[assignment]

    class Message:  # type: ignore[no-redef]
        pass


class Claude:
    def __init__(self, model: str):
        if Anthropic is None:
            raise RuntimeError(
                "Anthropic/Claude support is not available. "
                "Install the 'anthropic' package to use this class."
            )
        self.client = Anthropic()
        self.model = model

    def add_user_message(self, messages: List[dict], message: Any) -> None:
        from anthropic.types import Message as AnthropicMessage  # type: ignore

        user_message = {
            "role": "user",
            "content": message.content
            if isinstance(message, AnthropicMessage)
            else message,
        }
        messages.append(user_message)

    def add_assistant_message(self, messages: List[dict], message: Any) -> None:
        from anthropic.types import Message as AnthropicMessage  # type: ignore

        assistant_message = {
            "role": "assistant",
            "content": message.content
            if isinstance(message, AnthropicMessage)
            else message,
        }
        messages.append(assistant_message)

    def text_from_message(self, message: Message) -> str:
        return "\n".join(
            [block.text for block in message.content if getattr(block, "type", "") == "text"]
        )

    def chat(
        self,
        messages,
        system=None,
        temperature: float = 1.0,
        stop_sequences=None,
        tools=None,
        thinking: bool = False,
        thinking_budget: int = 1024,
    ) -> Message:
        if stop_sequences is None:
            stop_sequences = []

        params = {
            "model": self.model,
            "max_tokens": 8000,
            "messages": messages,
            "temperature": temperature,
            "stop_sequences": stop_sequences,
        }

        if thinking:
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }

        if tools:
            params["tools"] = tools

        if system:
            params["system"] = system

        return self.client.messages.create(**params)
