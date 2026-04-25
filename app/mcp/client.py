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

async def run_mcp_tool(tool_name: str, arguments: dict):
    """Generic MCP client that spawns the server and calls a specific tool."""
    server_script = os.path.join(os.path.dirname(__file__), "server.py")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=None
    )
    
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            # Call the target tool
            result = await session.call_tool(tool_name, arguments)
            
            output_text = ""
            if hasattr(result, "content") and result.content:
                for content_block in result.content:
                    output_text += content_block.text + "\n"
            else:
                output_text = "No content returned."
                
            return output_text.strip()

async def run_medium_query(query: str, is_user: bool = False, limit: int = 3):
    """Legacy wrapper for Medium queries, now using the generic tool runner."""
    return await run_mcp_tool("get_medium_posts", {"query": query, "is_user": is_user, "limit": limit})

if __name__ == "__main__":
    if sys.platform == "win32":
        # Required for async subprocesses on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    asyncio.run(run_medium_query("artificial-intelligence", is_user=False))
