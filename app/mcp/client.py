"""
app/mcp/client.py
-----------------
Model Context Protocol (MCP) Client.
Spawns the local MCP server as a subprocess and queries the Medium tool.
"""

import asyncio
import sys
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from app.core.logging import get_logger

logger = get_logger("MediumMCP_Client")

async def run_medium_query(query: str, is_user: bool = False, limit: int = 3):
    """Start the MCP server using stdio and call the Medium tool."""
    
    # Path to our built-in MCP server
    server_script = os.path.join(os.path.dirname(__file__), "server.py")
    
    # We specify how to spawn the server. 
    # Since it's a python script, we use the active sys.executable
    # Create a custom environment specifying UTF-8 to prevent Windows cp1252 encoding crashes
    custom_env = os.environ.copy()
    custom_env["PYTHONIOENCODING"] = "utf-8"
    # Ensure the root directory is in PYTHONPATH so imports work in the subprocess
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    custom_env["PYTHONPATH"] = root_dir
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=custom_env
    )
    
    logger.info(f"🚀 Starting MCP Client -> {server_script}")
    
    try:
        # stdio_client is an async context manager that handles the sub-process pipes
        async with stdio_client(server_params) as (read_stream, write_stream):
            logger.debug("🔗 Transports connected. Initializing session...")
            
            # ClientSession negotiates the actual JSON-RPC protocol
            async with ClientSession(read_stream, write_stream) as session:
                
                # 1. Initialize the connection
                await session.initialize()
                logger.info("✅ MCP Session initialized.")
                
                # 2. Discover available tools
                tools = await session.list_tools()
                
                # 3. Call the target tool by name
                logger.debug(f"🛠️ Calling 'get_medium_posts' (query={query})")
                result = await session.call_tool(
                    "get_medium_posts", 
                    {"query": query, "is_user": is_user, "limit": limit}
                )
                
                # 4. Return the result
                output_text = ""
                if hasattr(result, "content") and result.content:
                    for content_block in result.content:
                        output_text += content_block.text + "\n"
                else:
                    output_text = "No content returned."
                    
                return output_text.strip()
    except Exception as e:
        import traceback
        # Recursively log all exceptions in an ExceptionGroup (Python 3.11+)
        def log_exception_recursive(exc, level=0):
            indent = "  " * level
            if hasattr(exc, "exceptions"):
                for sub_e in exc.exceptions:
                    log_exception_recursive(sub_e, level + 1)
            else:
                logger.error(f"❌ MCP Leaf Error: {indent}{exc}")
                # Also log the traceback for the leaf error
                tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
                for line in tb_lines:
                    logger.debug(f"TRACE: {line.strip()}")

        logger.error(f"❌ MCP Connection Failed: {e}")
        log_exception_recursive(e)
        raise e

if __name__ == "__main__":
    if sys.platform == "win32":
        # Required for async subprocesses on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    asyncio.run(run_medium_query("artificial-intelligence", is_user=False))
