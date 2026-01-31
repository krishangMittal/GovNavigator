"""
server.py - MCP Server for Municipal Code Navigation

=== WHAT IS MCP (Model Context Protocol)? ===

MCP is a protocol that lets AI assistants (like Claude) use external tools.
It's like giving Claude new abilities - in our case, searching municipal codes.

Without MCP:
    User: "Can I build a fence in Madison?"
    Claude: "I don't have specific information about Madison's codes..."

With MCP:
    User: "Can I build a fence in Madison?"
    Claude: *calls search_ordinance("fence regulations")* → Gets real data
    Claude: "According to Madison Code Section 28.142, fences in front yards
             cannot exceed 4 feet in height..."

=== HOW MCP WORKS ===

1. MCP Server (this file) exposes "tools" - functions Claude can call
2. Claude Desktop connects to our server
3. When a user asks a question, Claude can call our tools
4. We return results, Claude uses them to answer

The communication happens via JSON-RPC over stdio (standard input/output).

=== MCP SERVER STRUCTURE ===

An MCP server needs to:
1. Declare what tools it has (name, description, parameters)
2. Handle requests to execute those tools
3. Return results in the expected format

Let's build it!
"""

import asyncio
import json
import sys
from pathlib import Path

# MCP SDK imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

# Add parent directory to path so we can import our search module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.search.index import SearchIndex


# === GLOBAL STATE ===
# The search index (loaded once when server starts)
search_index: SearchIndex | None = None


def get_index() -> SearchIndex:
    """
    Get or load the search index.

    === LAZY LOADING ===
    We don't load the index until it's needed.
    This makes the server start faster.
    """
    global search_index

    if search_index is None:
        index_path = Path(__file__).parent.parent.parent / "data" / "processed" / "search_index.json"

        if not index_path.exists():
            raise FileNotFoundError(
                f"Search index not found at {index_path}. "
                "Run `python -m src.search.index` first to build it."
            )

        print(f"Loading search index from {index_path}...", file=sys.stderr)
        search_index = SearchIndex.load(str(index_path))
        print(f"Index loaded: {search_index.num_docs} documents", file=sys.stderr)

    return search_index


# === CREATE THE MCP SERVER ===
# The Server class handles the MCP protocol for us
server = Server("govnavigator")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    Declare what tools our server provides.

    === TOOL DECLARATION ===
    Each tool has:
    - name: What Claude calls it
    - description: Helps Claude understand when to use it
    - inputSchema: JSON Schema defining the parameters

    The description is VERY important - it tells Claude when this tool
    is useful. Be specific about what it can and can't do.
    """
    return [
        Tool(
            name="search_ordinance",
            description="""Search Madison, WI municipal code/ordinances for specific topics.

Use this tool when users ask about:
- City regulations (fences, parking, noise, permits, etc.)
- What is allowed or prohibited in Madison
- Requirements for construction, businesses, animals, etc.
- Penalties and fees for violations

Returns relevant ordinance sections with citations.

Examples of good queries:
- "fence height limit residential"
- "short term rental requirements"
- "parking permit downtown"
- "noise ordinance quiet hours"
- "building permit required when"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query about municipal regulations"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5, max: 10)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_ordinance_details",
            description="""Get full details of a specific ordinance section by title.

Use this after search_ordinance to get more details about a specific section.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the ordinance section to retrieve"
                    }
                },
                "required": ["title"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    """
    Handle tool execution requests from Claude.

    === TOOL EXECUTION ===
    When Claude decides to use a tool:
    1. MCP sends us the tool name and arguments
    2. We execute the appropriate function
    3. We return results as CallToolResult

    The results become part of Claude's context for answering.

    Args:
        name: Which tool to run ("search_ordinance" or "get_ordinance_details")
        arguments: The parameters passed to the tool

    Returns:
        CallToolResult containing the tool output
    """
    try:
        if name == "search_ordinance":
            return await handle_search(arguments)
        elif name == "get_ordinance_details":
            return await handle_get_details(arguments)
        else:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Unknown tool: {name}"
                )],
                isError=True
            )
    except Exception as e:
        # Return errors gracefully
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Error executing {name}: {str(e)}"
            )],
            isError=True
        )


async def handle_search(arguments: dict) -> CallToolResult:
    """
    Handle the search_ordinance tool.

    === SEARCH WORKFLOW ===
    1. Parse arguments
    2. Query the search index
    3. Format results for Claude

    We format results to be useful for Claude:
    - Section numbers for citations
    - Relevant snippets
    - Match scores for relevance
    """
    query = arguments.get("query", "")
    max_results = min(arguments.get("max_results", 5), 10)

    if not query:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: No query provided")],
            isError=True
        )

    # Get the search index
    index = get_index()

    # Perform search
    results = index.search(query, max_results=max_results)

    if not results:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"No ordinances found matching '{query}'. Try different keywords."
            )]
        )

    # Format results for Claude
    output_lines = [
        f"Found {len(results)} relevant ordinance sections for '{query}':",
        ""
    ]

    for i, result in enumerate(results, 1):
        doc = result["document"]
        score = result["score"]
        snippet = result["snippet"]

        section = doc.get("section_number", "N/A")
        title = doc.get("title", "Untitled")
        chapter = doc.get("chapter", "")

        output_lines.extend([
            f"--- Result {i} ---",
            f"Title: {title}",
            f"Section: {section}" if section else "",
            f"Chapter: {chapter}" if chapter else "",
            f"Relevance Score: {score}",
            f"Excerpt: {snippet}",
            f"URL: {doc.get('url', 'N/A')}",
            ""
        ])

    return CallToolResult(
        content=[TextContent(
            type="text",
            text="\n".join(line for line in output_lines if line is not None)
        )]
    )


async def handle_get_details(arguments: dict) -> CallToolResult:
    """
    Handle the get_ordinance_details tool.

    Returns full content of a specific ordinance section.
    """
    title = arguments.get("title", "")

    if not title:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: No title provided")],
            isError=True
        )

    index = get_index()

    # Find the document by title
    for doc in index.documents:
        if title.lower() in doc.get("title", "").lower():
            content = doc.get("content", "")
            section = doc.get("section_number", "N/A")
            chapter = doc.get("chapter", "")
            url = doc.get("url", "N/A")

            # Limit content length for response
            if len(content) > 5000:
                content = content[:5000] + "\n\n[Content truncated. See full text at URL.]"

            output = f"""
=== {doc.get('title', 'Untitled')} ===

Section: {section}
Chapter: {chapter}
URL: {url}

FULL TEXT:
{content}
"""
            return CallToolResult(
                content=[TextContent(type="text", text=output)]
            )

    return CallToolResult(
        content=[TextContent(
            type="text",
            text=f"No ordinance found with title matching '{title}'"
        )]
    )


async def run_server():
    """
    Run the MCP server.

    === STDIO TRANSPORT ===
    The server communicates via stdin/stdout.
    This is how Claude Desktop connects to it.

    When you configure Claude Desktop to use this server,
    it launches our script and talks to it via stdio.
    """
    # Print startup message to stderr (stdout is for MCP protocol)
    print("GovNavigator MCP Server starting...", file=sys.stderr)
    print("Ready to serve municipal code queries!", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def main():
    """Entry point for the server."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
