"""
test_search.py - Test the search functionality directly

Run this to test the search without needing Claude Desktop.
This simulates what happens when Claude calls our MCP tools.

Usage:
    python test_search.py

Or with a custom query:
    python test_search.py "your search query here"
"""

import sys
import asyncio
from src.mcp_server.server import handle_search, handle_get_details, get_index


async def test_search(query: str):
    """Test the search_ordinance tool."""
    print("=" * 60)
    print(f"TESTING SEARCH: '{query}'")
    print("=" * 60)

    # Call the same function that Claude would call
    result = await handle_search({"query": query, "max_results": 5})

    # Extract the text content
    for content in result.content:
        print(content.text)

    print()


async def interactive_mode():
    """Interactive search mode."""
    print("=" * 60)
    print("GovNavigator - Interactive Search Test")
    print("=" * 60)
    print("\nType a search query and press Enter.")
    print("Type 'quit' to exit.\n")

    # Pre-load the index
    print("Loading search index...")
    idx = get_index()
    print(f"Ready! Index has {idx.num_docs} documents.\n")

    while True:
        try:
            query = input("Search > ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            if not query:
                continue

            await test_search(query)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            break


async def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Query provided as argument
        query = " ".join(sys.argv[1:])
        await test_search(query)
    else:
        # Interactive mode
        await interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())
