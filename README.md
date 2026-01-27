# Notion-Claude API

A powerful integration between Notion and Claude that helps you understand and leverage your notes for writing. Works with **Claude Desktop via MCP** or as a standalone **REST API**.

## Features

- **Content Search & Filtering**: Search through your Notion workspace with intelligent relevance scoring
- **Context Understanding**: Get a comprehensive overview of themes and topics across your notes
- **Writing Integration**: Seamlessly integrate relevant notes into your writing with different styles
- **Content Analysis**: Analyze your notes for summaries, themes, key points, and entities
- **Q&A**: Ask questions about your notes and get answers based on your content

---

## Option 1: Claude Desktop (MCP) - Recommended

Use your Notion notes directly in Claude Desktop conversations.

### Setup

1. **Install dependencies**
   ```bash
   git clone <repo-url>
   cd notion-claude-api
   pip install -r requirements.txt
   ```

2. **Get your API keys**
   - Notion: [notion.so/my-integrations](https://www.notion.so/my-integrations)
   - Anthropic: [console.anthropic.com](https://console.anthropic.com/)

3. **Share Notion pages with your integration**
   - Open a page in Notion
   - Click "..." menu > "Connections"
   - Add your integration

4. **Configure Claude Desktop**

   Edit your Claude Desktop config file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

   Add this configuration:
   ```json
   {
     "mcpServers": {
       "notion-claude": {
         "command": "python",
         "args": ["-m", "src.mcp_server"],
         "cwd": "/path/to/notion-claude-api",
         "env": {
           "NOTION_API_KEY": "your_notion_integration_token",
           "ANTHROPIC_API_KEY": "your_anthropic_api_key"
         }
       }
     }
   }
   ```

5. **Restart Claude Desktop**

### Available Tools in Claude

Once configured, you can ask Claude things like:

| Command | What it does |
|---------|--------------|
| "Search my Notion for notes about AI" | Finds relevant content using `notion_search` |
| "Give me an overview of my notes" | Analyzes themes using `notion_context` |
| "Summarize my research notes" | Uses `notion_analyze` with summary type |
| "Help me write about X using my notes" | Uses `notion_integrate` to enhance your draft |
| "What do my notes say about Y?" | Uses `notion_ask` to answer from your content |
| "List my Notion pages" | Shows all pages with `notion_list_pages` |
| "Refresh my Notion cache" | Updates content with `notion_refresh` |

### Example Conversation

```
You: I'm writing a blog post about productivity. Can you find relevant notes
     from my Notion and help me write an introduction?

Claude: [Uses notion_search to find productivity-related notes]
        [Uses notion_integrate to help write the introduction]

        Here's a draft introduction based on your notes...
```

---

## Option 2: REST API

Run as a standalone API server for programmatic access.

### Setup

```bash
# Clone and install
git clone <repo-url>
cd notion-claude-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
python -m src.api
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### `POST /search`
Search and filter your Notion content by relevance.

```json
{
  "query": "machine learning projects",
  "keywords": ["neural networks", "deep learning"],
  "recently_edited_days": 30,
  "max_results": 10
}
```

#### `POST /analyze`
Analyze your content with different analysis types.

```json
{
  "query": "research notes",
  "analysis_type": "themes",
  "max_pages": 20
}
```

Analysis types: `summary`, `themes`, `key_points`, `entities`

#### `POST /integrate`
Integrate relevant notes into your writing.

```json
{
  "draft": "Your current draft text here...",
  "query": "topic to find relevant notes",
  "integration_style": "enhance",
  "max_sources": 5
}
```

Integration styles:
- `enhance`: Add depth and insights
- `cite`: Add references and citations
- `expand`: Elaborate with more content
- `synthesize`: Combine ideas into new text

#### `POST /context`
Get a comprehensive overview of your Notion content.

```json
{
  "focus_topic": "optional specific topic",
  "max_pages": 20
}
```

#### `POST /ask`
Ask questions about your notes.

```
POST /ask?question=What are my main project ideas?&max_context=10
```

#### `GET /pages`
List all accessible Notion pages.

#### `POST /refresh`
Force refresh the content cache.

---

## Architecture

```
src/
├── __init__.py          # Package initialization
├── mcp_server.py        # MCP server for Claude Desktop
├── api.py               # FastAPI REST application
├── config.py            # Configuration management
├── notion_client.py     # Notion API client
├── claude_client.py     # Claude API client
└── content_filter.py    # Content filtering and relevance scoring
```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `NOTION_API_KEY` | Notion integration token | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key | Required |
| `CLAUDE_MODEL` | Claude model to use | `claude-opus-4-5-20251101` |
| `MAX_TOKENS` | Max tokens for Claude responses | `4096` |
| `CHUNK_SIZE` | Size of content chunks | `1000` |
| `API_PORT` | API server port (REST only) | `8000` |

## License

MIT License - see [LICENSE](LICENSE) for details.
