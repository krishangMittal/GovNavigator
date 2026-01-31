# GovNavigator - MCP Municipal Code Assistant

An MCP (Model Context Protocol) server that lets Claude search and navigate Madison, WI municipal ordinances. Ask questions like "Can I build a fence in my front yard?" and get real answers with citations!

## What is MCP?

**Model Context Protocol** is Anthropic's open standard for connecting AI assistants to external tools and data. This project demonstrates building a production MCP server.

```
┌─────────────────────────────────────────────────────┐
│              Claude Desktop                          │
│         (asks: "fence regulations?")                │
└──────────────────────┬──────────────────────────────┘
                       │ MCP Protocol
                       ▼
┌─────────────────────────────────────────────────────┐
│            GovNavigator MCP Server                  │
│        (searches our ordinance database)            │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              TF-IDF Search Index                     │
│        (30+ chapters of Madison city code)          │
└─────────────────────────────────────────────────────┘
```

## Features

- **Real Data**: Scraped from Madison, WI's actual municipal code
- **Semantic Search**: TF-IDF based search finds relevant ordinances
- **No API Costs**: 100% free - no paid APIs needed!
- **Citation Support**: Returns section numbers and URLs
- **MCP Integration**: Works with Claude Desktop

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (Mac/Linux)
source .venv/bin/activate

# Install dependencies
pip install -e .
```

### 2. Scrape Data (Optional - data already included)

```bash
python -m src.scraper.municode_scraper
```

### 3. Build Search Index

```bash
python -m src.search.index
```

### 4. Configure Claude Desktop

Add to your Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "govnavigator": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "C:\\Users\\Krish\\OneDrive\\Desktop\\GovNavigator"
    }
  }
}
```

### 5. Restart Claude Desktop

After adding the config, restart Claude Desktop. You should see "govnavigator" in the MCP tools list.

## Example Queries

Once connected, ask Claude:

- "Can I build a 6-foot fence in my front yard in Madison?"
- "What are the short-term rental regulations in Madison?"
- "Do I need a permit to open a food truck?"
- "What are the noise ordinance quiet hours?"
- "What's required for a building permit?"

## Project Structure

```
GovNavigator/
├── src/
│   ├── scraper/          # Web scraper for Municode
│   │   └── municode_scraper.py
│   ├── search/           # TF-IDF search engine
│   │   └── index.py
│   └── mcp_server/       # MCP server implementation
│       └── server.py
├── data/
│   ├── raw/              # Scraped ordinance data
│   └── processed/        # Search index
└── pyproject.toml        # Project configuration
```

## How It Works

### 1. Web Scraping
Uses Playwright (browser automation) to scrape Madison's municipal code from Municode.com. Handles JavaScript-rendered content.

### 2. TF-IDF Search
Builds a term-frequency inverse-document-frequency index for semantic search. No AI APIs needed - pure Python math!

### 3. MCP Server
Exposes two tools to Claude:
- `search_ordinance`: Search for relevant code sections
- `get_ordinance_details`: Get full text of a specific section

## Tech Stack

- **Python 3.10+**
- **MCP SDK** - Anthropic's Model Context Protocol
- **Playwright** - Browser automation for scraping
- **BeautifulSoup** - HTML parsing
- **Pydantic** - Data validation

## Learning Resources

This project demonstrates:
- Building MCP servers
- Web scraping with Playwright
- TF-IDF search implementation
- Async Python programming
- Data pipeline design

## License

MIT License - Use freely for learning and building!

---

Built with Claude Code by a human learning AI engineering.
