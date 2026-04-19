"""
app/mcp/server.py
-----------------
Model Context Protocol (MCP) Server using FastMCP.
Exposes a tool to fetch the latest Medium.com posts.
"""

import feedparser
from mcp.server.fastmcp import FastMCP

# 1. Initialize the FastMCP Server
mcp = FastMCP("MediumRSS_Server")

# 2. Define standard tools that expose Medium APIs
@mcp.tool()
def get_medium_posts(query: str, is_user: bool = False, limit: int = 5) -> str:
    """
    Fetches the latest blog posts from Medium.com.
    
    Args:
        query: The topic tag (e.g., 'artificial-intelligence') or username without '@' (e.g., 'towards-data-science').
        is_user: Set to True if the query is a specific author/publication username.
        limit: Max number of posts to return.
    """
    if is_user:
        feed_url = f"https://medium.com/feed/@{query}"
    else:
        feed_url = f"https://medium.com/feed/tag/{query}"
        
    parsed_feed = feedparser.parse(feed_url)
    
    if not parsed_feed.entries:
        return f"No posts found for query: {query}"
        
    results = [f"Found {len(parsed_feed.entries)} entries. Showing top {limit}:\n"]
    
    for idx, entry in enumerate(parsed_feed.entries[:limit]):
        title = entry.get('title', 'Unknown Title')
        link = entry.get('link', 'No Link')
        published = entry.get('published', 'Unknown Date')
        results.append(f"{idx + 1}. {title}\n   Published: {published}\n   Link: {link}\n")
        
    return "\n".join(results)

# 3. Run the server
if __name__ == "__main__":
    # By default, mcp.run() uses the stdio transport, perfect for local LLM clients
    mcp.run()
