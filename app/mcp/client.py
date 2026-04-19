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

async def run_medium_query(query: str, is_user: bool = False, limit: int = 3):
    """Start the MCP server using stdio and call the Medium tool."""
    
    # Path to our built-in MCP server
    server_script = os.path.join(os.path.dirname(__file__), "server.py")
    
    # We specify how to spawn the server. 
    # Since it's a python script, we use the active sys.executable
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=None
    )
    
    print(f"[*] Starting MCP Client and connecting to Server process -> {server_script}")
    
    # stdio_client is an async context manager that handles the sub-process pipes
    async with stdio_client(server_params) as (read_stream, write_stream):
        print("[*] Transports connected. Initializing MCP Session...")
        
        # ClientSession negotiates the actual JSON-RPC protocol
        async with ClientSession(read_stream, write_stream) as session:
            
            # 1. Initialize the connection
            await session.initialize()
            print("[+] Session initialized!")
            
            # 2. Discover available tools
            tools = await session.list_tools()
            print("\n[-] Available Tools on Server:")
            for tool in tools.tools:
                print(f"    - {tool.name}: {tool.description}")
            
            print(f"\n[*] Calling tool 'get_medium_posts' with query='{query}', is_user={is_user}...")
            
            # 3. Call the target tool by name, passing the required arguments
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

if __name__ == "__main__":
    if sys.platform == "win32":
        # Required for async subprocesses on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    asyncio.run(run_medium_query("artificial-intelligence", is_user=False))
