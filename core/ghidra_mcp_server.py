import os
import sys
from typing import Any, Union
from dotenv import load_dotenv
import requests
import argparse
import logging
from urllib.parse import urljoin
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)



mcp = FastMCP("ghidra-mcp")

def safe_get(endpoint: str, params: Union[dict[str, Any],None] = None) -> list:
    """
    Perform a GET request with optional query parameters.
    """
    if params is None:
        params = {}

    url = urljoin(mcp.ghidra_url, endpoint)

    try:
        response = requests.get(url, params=params, timeout=5)
        response.encoding = 'utf-8'
        if response.ok:
            return response.text.splitlines()
        else:
            return [f"Error {response.status_code}: {response.text.strip()}"]
    except Exception as e:
        return [f"Request failed: {str(e)}"]

def safe_post(endpoint: str, data: dict | str) -> str:
    try:
        url = urljoin(mcp.ghidra_url, endpoint)
        if isinstance(data, dict):
            response = requests.post(url, data=data, timeout=5)
        else:
            response = requests.post(url, data=data.encode("utf-8"), timeout=5)
        response.encoding = 'utf-8'
        if response.ok:
            return response.text.strip()
        else:
            return f"Error {response.status_code}: {response.text.strip()}"
    except Exception as e:
        return f"Request failed: {str(e)}"

@mcp.tool()
def list_methods(offset: int = 0, limit: int = 100) -> list:
    """
    List all function names in the program with pagination.
    """
    return safe_get("methods", {"offset": offset, "limit": limit})

@mcp.tool()
def list_classes(offset: int = 0, limit: int = 100) -> list:
    """
    List all namespace/class names in the program with pagination.
    """
    return safe_get("classes", {"offset": offset, "limit": limit})

@mcp.tool()
def decompile_function(name: str) -> str:
    """
    Decompile a specific function by name and return the decompiled C code.
    """
    return safe_post("decompile", name)

@mcp.tool()
def rename_function(old_name: str, new_name: str) -> str:
    """
    Rename a function by its current name to a new user-defined name.
    """
    return safe_post("renameFunction", {"oldName": old_name, "newName": new_name})

@mcp.tool()
def rename_data(address: str, new_name: str) -> str:
    """
    Rename a data label at the specified address.
    """
    return safe_post("renameData", {"address": address, "newName": new_name})

@mcp.tool()
def list_segments(offset: int = 0, limit: int = 100) -> list:
    """
    List all memory segments in the program with pagination.
    """
    return safe_get("segments", {"offset": offset, "limit": limit})

@mcp.tool()
def list_imports(offset: int = 0, limit: int = 100) -> list:
    """
    List imported symbols in the program with pagination.
    """
    return safe_get("imports", {"offset": offset, "limit": limit})

@mcp.tool()
def list_exports(offset: int = 0, limit: int = 100) -> list:
    """
    List exported functions/symbols with pagination.
    """
    return safe_get("exports", {"offset": offset, "limit": limit})

@mcp.tool()
def list_namespaces(offset: int = 0, limit: int = 100) -> list:
    """
    List all non-global namespaces in the program with pagination.
    """
    return safe_get("namespaces", {"offset": offset, "limit": limit})

@mcp.tool()
def list_data_items(offset: int = 0, limit: int = 100) -> list:
    """
    List defined data labels and their values with pagination.
    """
    return safe_get("data", {"offset": offset, "limit": limit})

@mcp.tool()
def search_functions_by_name(query: str, offset: int = 0, limit: int = 100) -> list:
    """
    Search for functions whose name contains the given substring.
    """
    if not query:
        return ["Error: query string is required"]
    return safe_get("searchFunctions", {"query": query, "offset": offset, "limit": limit})

@mcp.tool()
def rename_variable(function_name: str, old_name: str, new_name: str) -> str:
    """
    Rename a local variable within a function.
    """
    return safe_post("renameVariable", {
        "functionName": function_name,
        "oldName": old_name,
        "newName": new_name
    })

@mcp.tool()
def get_function_by_address(address: str) -> str:
    """
    Get a function by its address.
    """
    return "\n".join(safe_get("get_function_by_address", {"address": address}))

@mcp.tool()
def get_current_address() -> str:
    """
    Get the address currently selected by the user.
    """
    return "\n".join(safe_get("get_current_address"))

@mcp.tool()
def get_current_function() -> str:
    """
    Get the function currently selected by the user.
    """
    return "\n".join(safe_get("get_current_function"))

@mcp.tool()
def list_functions() -> list:
    """
    List all functions in the database.
    """
    return safe_get("list_functions")

@mcp.tool()
def decompile_function_by_address(address: str) -> str:
    """
    Decompile a function at the given address.
    """
    return "\n".join(safe_get("decompile_function", {"address": address}))

@mcp.tool()
def disassemble_function(address: str) -> list:
    """
    Get assembly code (address: instruction; comment) for a function.
    """
    return safe_get("disassemble_function", {"address": address})

@mcp.tool()
def set_decompiler_comment(address: str, comment: str) -> str:
    """
    Set a comment for a given address in the function pseudocode.
    """
    return safe_post("set_decompiler_comment", {"address": address, "comment": comment})

@mcp.tool()
def set_disassembly_comment(address: str, comment: str) -> str:
    """
    Set a comment for a given address in the function disassembly.
    """
    return safe_post("set_disassembly_comment", {"address": address, "comment": comment})

@mcp.tool()
def rename_function_by_address(function_address: str, new_name: str) -> str:
    """
    Rename a function by its address.
    """
    return safe_post("rename_function_by_address", {"function_address": function_address, "new_name": new_name})

@mcp.tool()
def set_function_prototype(function_address: str, prototype: str) -> str:
    """
    Set a function's prototype.
    """
    return safe_post("set_function_prototype", {"function_address": function_address, "prototype": prototype})

@mcp.tool()
def set_local_variable_type(function_address: str, variable_name: str, new_type: str) -> str:
    """
    Set a local variable's type.
    """
    return safe_post("set_local_variable_type", {"function_address": function_address, "variable_name": variable_name, "new_type": new_type})

@mcp.tool()
def get_xrefs_to(address: str, offset: int = 0, limit: int = 100) -> list:
    """
    Get all references to the specified address (xref to).
    
    Args:
        address: Target address in hex format (e.g. "0x1400010a0")
        offset: Pagination offset (default: 0)
        limit: Maximum number of references to return (default: 100)
        
    Returns:
        List of references to the specified address
    """
    return safe_get("xrefs_to", {"address": address, "offset": offset, "limit": limit})

@mcp.tool()
def get_xrefs_from(address: str, offset: int = 0, limit: int = 100) -> list:
    """
    Get all references from the specified address (xref from).
    
    Args:
        address: Source address in hex format (e.g. "0x1400010a0")
        offset: Pagination offset (default: 0)
        limit: Maximum number of references to return (default: 100)
        
    Returns:
        List of references from the specified address
    """
    return safe_get("xrefs_from", {"address": address, "offset": offset, "limit": limit})

@mcp.tool()
def get_function_xrefs(name: str, offset: int = 0, limit: int = 100) -> list:
    """
    Get all references to the specified function by name.
    
    Args:
        name: Function name to search for
        offset: Pagination offset (default: 0)
        limit: Maximum number of references to return (default: 100)
        
    Returns:
        List of references to the specified function
    """
    return safe_get("function_xrefs", {"name": name, "offset": offset, "limit": limit})

@mcp.tool()
def list_strings(offset: int = 0, limit: int = 2000, filter: Union[str,None] = None) -> list:
    """
    List all defined strings in the program with their addresses.
    
    Args:
        offset: Pagination offset (default: 0)
        limit: Maximum number of strings to return (default: 2000)
        filter: Optional filter to match within string content
        
    Returns:
        List of strings with their addresses
    """
    params: dict[str, Any]= {"offset": offset, "limit": limit}
    if filter:
        params["filter"] = filter
    return safe_get("strings", params)



def build_runtime_config() -> str:

    # Main config
    load_dotenv()
    GHIDRA_SERVER_HOST = os.getenv("GHIDRA_SERVER_HOST", "127.0.0.1")
    GHIDRA_SERVER_PORT = os.getenv("GHIDRA_SERVER_PORT", "8080")
    #OLLAMA_SERVER_HOST = os.getenv("OLLAMA_SERVER_HOST", "127.0.0.1")
    #OLLAMA_SERVER_PORT = os.getenv("OLLAMA_SERVER_PORT", "11434")
    #OLLAMA_SERVER_MODEL = os.getenv("OLLAMA_MODEL", "")
    #CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "")
    #ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # Config overrides and other args
    parser = argparse.ArgumentParser(description="Chat-based MCP tools for Ghidra")
    #parser.add_argument(
    #    "--ollama",
    #    action="store_true",
    #    help="Use Ollama (the default setting)",
    #)
    #parser.add_argument(
    #    "--claude",
    #    action="store_true",
    #    help="Use Claude in the cloud",
    #)
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
    #parser.add_argument(
    #    "--oh",
    #    "--ollama-host",
    #    dest="ollama_host",
    #    type=str,
    #    default=OLLAMA_SERVER_HOST,
    #    help=f"Hostname or IP address of Ollama server, default: {OLLAMA_SERVER_HOST}",
    #)
    #parser.add_argument(
    #    "--op",
    #    "--ollama-port",
    #    dest="ollama_port",
    #    type=str,
    #    default=OLLAMA_SERVER_PORT,
    #    help=f"Port number of Ollama server, default: {OLLAMA_SERVER_PORT}",
    #)
    #parser.add_argument(
    #    "--om",
    #    "--ollama-model",
    #    dest="ollama_model",
    #    type=str,
    #    default=OLLAMA_SERVER_MODEL if OLLAMA_SERVER_MODEL != "" else "(None)",
    #    help="Model to run on Ollama server",
    #)
    #parser.add_argument(
    #    "--cm",
    #    "--claude-model",
    #    dest="claude_model",
    #    type=str,
    #    default=CLAUDE_MODEL if CLAUDE_MODEL != "" else "(None)",
    #    help="Model to run on Claude in the cloud",
    #)
    args = parser.parse_args()
    
    config_failed = False
    #llm_server = ""
    ghidra_url = ""
    #ollama_url = ""
    #ollama_model = ""
    #claude_model = ""
    #anthropic_api_key = ""

    if args.ghidra_host: GHIDRA_SERVER_HOST = args.ghidra_host
    if args.ghidra_port: GHIDRA_SERVER_PORT = args.ghidra_port

    if GHIDRA_SERVER_HOST.strip() == "" or GHIDRA_SERVER_PORT.strip() == "":
        print(f"[!] Host and port to Ghidra MCP plugin are both required.")
        config_failed = True
    
    ghidra_url = f"http://{GHIDRA_SERVER_HOST.strip()}:{GHIDRA_SERVER_PORT.strip()}"

    # if (args.ollama and args.claude) or (not args.ollama and not args.claude):
    #     print(f"[!] Select either Ollama or Claude, but not both.")
    #     config_failed = True

    # if args.ollama or not args.claude:

    #     if args.ollama_host: OLLAMA_SERVER_HOST = args.ollama_host
    #     if args.ollama_port: OLLAMA_SERVER_PORT = args.ollama_port
    #     if OLLAMA_SERVER_HOST.strip() == "" or OLLAMA_SERVER_PORT.strip() == "":
    #         print(f"[!] Host and port to Ollama server are both required.")
    #         config_failed = True

    #     if args.ollama_model: OLLAMA_SERVER_MODEL = args.ollama_model
    #     if OLLAMA_SERVER_MODEL.strip() == "" or OLLAMA_SERVER_MODEL.strip() == "(None)":
    #         print(f"[!] Must specify the model to run on Ollama.")
    #         config_failed = True

    #     llm_server = "ollama"
    #     ollama_url = f"http://{OLLAMA_SERVER_HOST.strip()}:{OLLAMA_SERVER_PORT.strip()}"
    #     ollama_model = f"{OLLAMA_SERVER_MODEL.strip()}"

    # if args.claude:
    #     if args.claude_model: CLAUDE_MODEL = args.claude_model
    #     if CLAUDE_MODEL.strip() == "" or CLAUDE_MODEL.strip() == "(None)":
    #         print(f"[!] Must specify the model to run on Claude.")
    #         config_failed = True

    #     if ANTHROPIC_API_KEY == "":
    #         print(f"[!] Must specify Anthropic API key in .env file--no CLI option.")
    #         config_failed = True

    #     llm_server = "claude"
    #     claude_model = f"{CLAUDE_MODEL.strip()}"
    #     anthropic_api_key = f"{ANTHROPIC_API_KEY.strip()}"
    
    if config_failed:
        parser.print_usage()
        sys.exit(1)
    else:
        # conf: dict[str, str] = dict()

        # if llm_server == "ollama":
        #     conf["ghidra_url"] = ghidra_url
        #     conf["ollama_url"] = ollama_url
        #     conf["ollama_model"] = ollama_model
            
        #     return llm_server, conf

        # elif llm_server == "claude":
        #     conf["claude_model"] = claude_model
        #     conf["anthropic_api_key"] = anthropic_api_key

        #     return llm_server, conf
        
        # else:
        #     print(f"[!] Error setting runtime config.")
        #     sys.exit(2)
        return ghidra_url
        



def main():
    ghidra_url = build_runtime_config()
    
    # parser = argparse.ArgumentParser(description="MCP server for Ghidra")
    # parser.add_argument("--ghidra-server", type=str, default=ghidra_url,
    #                     help=f"Ghidra server URL, default: {ghidra_url}")
    # parser.add_argument("--mcp-host", type=str, default="127.0.0.1",
    #                     help="Host to run MCP server on (only used for sse), default: 127.0.0.1")
    # parser.add_argument("--mcp-port", type=int,
    #                     help="Port to run MCP server on (only used for sse), default: 8081")
    # parser.add_argument("--transport", type=str, default="stdio", choices=["stdio", "sse"],
    #                     help="Transport protocol for MCP, default: stdio")
    # args = parser.parse_args()
    
    # if args.ghidra_server:
    #     ghidra_url = args.ghidra_server
    
    # if args.transport == "sse":
    #     try:
    #         # Set up logging
    #         log_level = logging.INFO
    #         logging.basicConfig(level=log_level)
    #         logging.getLogger().setLevel(log_level)

    #         # Configure MCP settings
    #         mcp.settings.log_level = "INFO"
    #         #if args.mcp_host:
    #         #    mcp.settings.host = args.mcp_host
    #         #else:
    #         #    mcp.settings.host = "127.0.0.1"

    #         #if args.mcp_port:
    #         #    mcp.settings.port = args.mcp_port
    #         #else:
    #         #    mcp.settings.port = 8081

    #         logger.info(f"Connecting to Ghidra server at {ghidra_url}")
    #         logger.info(f"Starting MCP server on http://{mcp.settings.host}:{mcp.settings.port}/sse")
    #         logger.info(f"Using transport: {args.transport}")

    #         mcp.run(transport="sse")
    #     except KeyboardInterrupt:
    #         logger.info("Server stopped by user")
    # else:
    #     mcp.run(transport="stdio")

    mcp.run(transport="stdio", ghidra_url=ghidra_url)
        
if __name__ == "__main__":
    main()

