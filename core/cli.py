from typing import List, Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.document import Document
from prompt_toolkit.buffer import Buffer

from core.cli_chat import CliChatOllama


class CommandAutoSuggest(AutoSuggest):
    def __init__(self, prompts: List):
        self.prompts = prompts
        self.prompt_dict = {prompt.name: prompt for prompt in prompts}

    def get_suggestion(
        self, buffer: Buffer, document: Document
    ) -> Optional[Suggestion]:
        text = document.text

        if not text.startswith("/"):
            return None

        parts = text[1:].split()

        if len(parts) == 1:
            cmd = parts[0]

            if cmd in self.prompt_dict:
                prompt = self.prompt_dict[cmd]
                return Suggestion(f" {prompt.arguments[0].name}")

        return None


class UnifiedCompleter(Completer):
    def __init__(self):
        self.prompts = []
        self.prompt_dict = {}
        self.resources = []

    def update_prompts(self, prompts: List):
        self.prompts = prompts
        self.prompt_dict = {prompt.name: prompt for prompt in prompts}

    def update_resources(self, resources: List):
        self.resources = resources

    def get_completions(self, document, complete_event):
        text = document.text
        text_before_cursor = document.text_before_cursor

        # if "@" in text_before_cursor:
        #     last_at_pos = text_before_cursor.rfind("@")
        #     prefix = text_before_cursor[last_at_pos + 1 :]

        #     for resource_id in self.resources:
        #         if resource_id.lower().startswith(prefix.lower()):
        #             yield Completion(
        #                 resource_id,
        #                 start_position=-len(prefix),
        #                 display=resource_id,
        #                 display_meta="Resource",
        #             )
        #     return

        if text.startswith("/"):
            parts = text[1:].split()

            if len(parts) <= 1 and not text.endswith(" "):
                cmd_prefix = parts[0] if parts else ""

                for prompt in self.prompts:
                    if prompt.name.startswith(cmd_prefix):
                        yield Completion(
                            prompt.name,
                            start_position=-len(cmd_prefix),
                            display=f"/{prompt.name}",
                            display_meta=prompt.description or "",
                        )
                return

            if len(parts) == 1 and text.endswith(" "):
                cmd = parts[0]

                if cmd in self.prompt_dict:
                    for id in self.resources:
                        yield Completion(
                            id,
                            start_position=0,
                            display=id,
                        )
                return

            # if len(parts) >= 2:
            #     doc_prefix = parts[-1]

            #     for resource in self.resources:
            #         if "id" in resource and resource["id"].lower().startswith(
            #             doc_prefix.lower()
            #         ):
            #             yield Completion(
            #                 resource["id"],
            #                 start_position=-len(doc_prefix),
            #                 display=resource["id"],
            #             )
            #     return


class CliApp:
    def __init__(self, agent: CliChatOllama):
        self.agent = agent
        self.resources = []
        self.prompts = []

        self.completer = UnifiedCompleter()

        self.command_autosuggester = CommandAutoSuggest([])

        self.kb = KeyBindings()

        @self.kb.add("/")
        def _(event):
            buffer = event.app.current_buffer
            if buffer.document.is_cursor_at_the_end and not buffer.text:
                buffer.insert_text("/")
                buffer.start_completion(select_first=False)
            else:
                buffer.insert_text("/")

        #@self.kb.add("@")
        #def _(event):
        #    buffer = event.app.current_buffer
        #    buffer.insert_text("@")
        #    if buffer.document.is_cursor_at_the_end:
        #        buffer.start_completion(select_first=False)

        #@self.kb.add(" ")
        #def _(event):
        #    buffer = event.app.current_buffer
        #    text = buffer.text
        #
        #    buffer.insert_text(" ")
        #
        #    if text.startswith("/"):
        #        parts = text[1:].split()
        #
        #        if len(parts) == 1:
        #            buffer.start_completion(select_first=False)
        #        elif len(parts) == 2:
        #            arg = parts[1]
        #            if (
        #                "doc" in arg.lower()
        #                or "file" in arg.lower()
        #                or "id" in arg.lower()
        #            ):
        #                buffer.start_completion(select_first=False)

        self.history = InMemoryHistory()
        self.session = PromptSession(
            completer=self.completer,
            history=self.history,
            key_bindings=self.kb,
            style=Style.from_dict(
                {
                    "prompt": "#aaaaaa",
                    "completion-menu.completion": "bg:#222222 #ffffff",
                    "completion-menu.completion.current": "bg:#444444 #ffffff",
                }
            ),
            complete_while_typing=True,
            complete_in_thread=True,
            auto_suggest=self.command_autosuggester,
        )

    async def initialize(self):
        await self.refresh_resources()
        await self.refresh_prompts()

        # Show initial help so users know how to interact with the CLI.
        await self.print_help()

    async def print_help(self):
        print("\n=== Ghidra MCP Chat CLI ===")

        # List MCP tools exposed by the Ghidra MCP server
        try:
            tool_names = await self.agent.ghidra_client.list_tools()
            if tool_names:
                print("\nMCP tools available (callable by the LLM):")
                for name in sorted(tool_names):
                    print(f"  - {name}")
            else:
                print("\nNo MCP tools reported by the server.")
        except Exception as e:
            print(f"\nError listing MCP tools: {e}")

        # List slash-style prompt commands, if any are defined by the MCP server
        if self.prompts:
            print("\nSlash commands (MCP prompts):")
            for prompt in self.prompts:
                arg_hint = ""
                try:
                    if getattr(prompt, "arguments", None):
                        first_arg = prompt.arguments[0]
                        arg_name = getattr(first_arg, "name", "arg")
                        arg_hint = f" <{arg_name}>"
                except Exception:
                    pass

                desc = getattr(prompt, "description", "") or ""
                if desc:
                    print(f"  /{prompt.name}{arg_hint} - {desc}")
                else:
                    print(f"  /{prompt.name}{arg_hint}")
        else:
            print("\nNo slash commands (MCP prompts) defined by the server.")

        print("\nAnything else you type is sent as a natural language prompt to the LLM.\n")

    async def refresh_resources(self):
        # The current Ghidra MCP server does not expose document resources,
        # so we treat this as a no-op and keep an empty resources list.
        self.resources = []
        self.completer.update_resources(self.resources)

    async def refresh_prompts(self):
        # The current Ghidra MCP server does not define prompts, so we keep
        # this empty and disable command autosuggestions based on prompts.
        self.prompts = []
        self.completer.update_prompts(self.prompts)
        self.command_autosuggester = CommandAutoSuggest(self.prompts)
        self.session.auto_suggest = self.command_autosuggester

    async def run(self):
        # Cache the known MCP tool names for quick command detection.
        try:
            tool_names = await self.agent.list_tools()
        except Exception:
            tool_names = []

        while True:
            try:
                user_input = await self.session.prompt_async("> ")
                if not user_input.strip():
                    continue
 
                text = user_input.strip()

                # If the user types an MCP tool name (optionally with empty
                # parentheses), call the MCP tool directly and show raw output.
                base = text
                if base.endswith("()"):
                    base = base[:-2].strip()

                if base in tool_names:
                    print(f"Processing MCP tool '{base}' via direct call...")
                    output = await self.agent.call_tool(base, {})
                    if output:
                        print(f"\nTool output:\n{output}")
                    else:
                        print("\nTool returned no textual output.")
                    continue

                # Otherwise, treat the input as a natural-language prompt to
                # the LLM, which can autonomously decide to call tools.
                response = await self.agent.run(user_input)
                print(f"\nResponse:\n{response}")

            except KeyboardInterrupt:
                break
