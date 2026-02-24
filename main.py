import argparse
import asyncio
import sys
import os
from contextlib import AsyncExitStack

from dotenv import load_dotenv

from core.ghidra_mcp_client import MCPClient
from core.cli_chat import CliChatOllama
from core.cli import CliApp



def build_runtime_config() -> tuple[str, dict[str, str]]:

    # Main config
    load_dotenv()
    GHIDRA_SERVER_HOST = os.getenv("GHIDRA_SERVER_HOST", "127.0.0.1")
    GHIDRA_SERVER_PORT = os.getenv("GHIDRA_SERVER_PORT", "8080")
    OLLAMA_SERVER_HOST = os.getenv("OLLAMA_SERVER_HOST", "127.0.0.1")
    OLLAMA_SERVER_PORT = os.getenv("OLLAMA_SERVER_PORT", "11434")
    OLLAMA_SERVER_MODEL = os.getenv("OLLAMA_MODEL", "")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # Config overrides and other args
    parser = argparse.ArgumentParser(description="Chat-based MCP tools for Ghidra")
    parser.add_argument(
        "--ollama",
        action="store_true",
        help="Use Ollama (the default setting)",
    )
    parser.add_argument(
        "--claude",
        action="store_true",
        help="Use Claude in the cloud",
    )
    parser.add_argument(
        "--gh",
        "--ghidra-host",
        dest="ghidra_host",
        type=str,
        default=GHIDRA_SERVER_HOST,
        help=f"Hostname or IP address of Ghidra MCP plugin, default: {GHIDRA_SERVER_HOST}",
    )
    parser.add_argument(
        "--gp",
        "--ghidra-port",
        dest="ghidra_port",
        type=str,
        default=GHIDRA_SERVER_PORT,
        help=f"Port number of Ghidra MCP plugin, default: {GHIDRA_SERVER_PORT}",
    )
    parser.add_argument(
        "--oh",
        "--ollama-host",
        dest="ollama_host",
        type=str,
        default=OLLAMA_SERVER_HOST,
        help=f"Hostname or IP address of Ollama server, default: {OLLAMA_SERVER_HOST}",
    )
    parser.add_argument(
        "--op",
        "--ollama-port",
        dest="ollama_port",
        type=str,
        default=OLLAMA_SERVER_PORT,
        help=f"Port number of Ollama server, default: {OLLAMA_SERVER_PORT}",
    )
    parser.add_argument(
        "--om",
        "--ollama-model",
        dest="ollama_model",
        type=str,
        default=OLLAMA_SERVER_MODEL if OLLAMA_SERVER_MODEL != "" else "(None)",
        help="Model to run on Ollama server",
    )
    parser.add_argument(
        "--cm",
        "--claude-model",
        dest="claude_model",
        type=str,
        default=CLAUDE_MODEL if CLAUDE_MODEL != "" else "(None)",
        help="Model to run on Claude in the cloud",
    )
    args = parser.parse_args()
    
    config_failed = False
    llm_server = ""
    ghidra_url = ""
    ollama_url = ""
    ollama_model = ""
    claude_model = ""
    anthropic_api_key = ""

    if args.ghidra_host: GHIDRA_SERVER_HOST = args.ghidra_host
    if args.ghidra_port: GHIDRA_SERVER_PORT = args.ghidra_port

    if GHIDRA_SERVER_HOST.strip() == "" or GHIDRA_SERVER_PORT.strip() == "":
        print(f"[!] Host and port to Ghidra MCP plugin are both required.")
        config_failed = True
    
    ghidra_url = f"http://{GHIDRA_SERVER_HOST.strip()}:{GHIDRA_SERVER_PORT.strip()}"

    if (args.ollama and args.claude) or (not args.ollama and not args.claude):
        print(f"[!] Select either Ollama or Claude, but not both.")
        config_failed = True

    if args.ollama or not args.claude:

        if args.ollama_host: OLLAMA_SERVER_HOST = args.ollama_host
        if args.ollama_port: OLLAMA_SERVER_PORT = args.ollama_port
        if OLLAMA_SERVER_HOST.strip() == "" or OLLAMA_SERVER_PORT.strip() == "":
            print(f"[!] Host and port to Ollama server are both required.")
            config_failed = True

        if args.ollama_model: OLLAMA_SERVER_MODEL = args.ollama_model
        if OLLAMA_SERVER_MODEL.strip() == "" or OLLAMA_SERVER_MODEL.strip() == "(None)":
            print(f"[!] Must specify the model to run on Ollama.")
            config_failed = True

        llm_server = "ollama"
        ollama_url = f"http://{OLLAMA_SERVER_HOST.strip()}:{OLLAMA_SERVER_PORT.strip()}"
        ollama_model = f"{OLLAMA_SERVER_MODEL.strip()}"

    if args.claude:
        if args.claude_model: CLAUDE_MODEL = args.claude_model
        if CLAUDE_MODEL.strip() == "" or CLAUDE_MODEL.strip() == "(None)":
            print(f"[!] Must specify the model to run on Claude.")
            config_failed = True

        if ANTHROPIC_API_KEY == "":
            print(f"[!] Must specify Anthropic API key in .env file--no CLI option.")
            config_failed = True

        llm_server = "claude"
        claude_model = f"{CLAUDE_MODEL.strip()}"
        anthropic_api_key = f"{ANTHROPIC_API_KEY.strip()}"
    
    if config_failed:
        parser.print_usage()
        sys.exit(1)
    else:
        conf: dict[str, str] = dict()

        if llm_server == "ollama":
            conf["ghidra_url"] = ghidra_url
            conf["ghidra_host"] = GHIDRA_SERVER_HOST.strip()
            conf["ghidra_port"] = GHIDRA_SERVER_PORT.strip()
            conf["ollama_url"] = ollama_url
            conf["ollama_model"] = ollama_model
            
            return llm_server, conf
        
        else:
            print(f"[!] Error setting runtime config.")
            sys.exit(2)
        


async def main():

    
    llm_server, conf = build_runtime_config()

    clients: dict[str, MCPClient] = {}
    command, args = ("python", [
        "core/ghidra_mcp_server.py",
        "--ghidra-host", conf["ghidra_host"],
        "--ghidra-port", conf["ghidra_port"],
        ])

    async with AsyncExitStack() as stack:
        ghidra_client = await stack.enter_async_context(
            MCPClient(command=command, args=args)
        )
        clients["ghidra_client"] = ghidra_client

        # for i, server_script in enumerate(server_scripts):
        #    client_id = f"client_{i}_{server_script}"
        #    client = await stack.enter_async_context(
        #        MCPClient(command="uv", args=["run", server_script])
        #    )
        #    clients[client_id] = client

        if llm_server == "ollama":
            chat = CliChatOllama(
                ghidra_client=ghidra_client,
                clients=clients,
                ollama_url=conf["ollama_url"],
                ollama_model=conf["ollama_model"],
            )

            cli = CliApp(chat)
            await cli.initialize()
            await cli.run()

        else:
            print("[!] Only Ollama is currently supported for the chat CLI.")
            sys.exit(3)


        


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
