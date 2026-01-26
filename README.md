# Notion-Claude API

A powerful API integration between Notion and Claude that helps you understand and leverage your notes for writing.

## Features

- **Content Search & Filtering**: Search through your Notion workspace with intelligent relevance scoring
- **Context Understanding**: Get a comprehensive overview of themes and topics across your notes
- **Writing Integration**: Seamlessly integrate relevant notes into your writing with different styles
- **Content Analysis**: Analyze your notes for summaries, themes, key points, and entities
- **Q&A**: Ask questions about your notes and get answers based on your content

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Notion Integration Token ([Create one here](https://www.notion.so/my-integrations))
- Anthropic API Key ([Get one here](https://console.anthropic.com/))

### 2. Installation

```bash
# Clone the repository
git clone <repo-url>
cd notion-claude-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API keys
NOTION_API_KEY=your_notion_integration_token
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### 4. Connect Notion Pages

In Notion, share the pages you want to access with your integration:
1. Open a page in Notion
2. Click "..." menu > "Connections"
3. Add your integration

### 5. Run the API

```bash
python -m src.api
```

The API will be available at `http://localhost:8000`

## API Endpoints

### `POST /search`
Search and filter your Notion content by relevance.

```json
{
  "query": "machine learning projects",
  "keywords": ["neural networks", "deep learning"],
  "recently_edited_days": 30,
  "max_results": 10
}
```

### `POST /analyze`
Analyze your content with different analysis types.

```json
{
  "query": "research notes",
  "analysis_type": "themes",
  "max_pages": 20
}
```

Analysis types: `summary`, `themes`, `key_points`, `entities`

### `POST /integrate`
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

### `POST /context`
Get a comprehensive overview of your Notion content.

```json
{
  "focus_topic": "optional specific topic",
  "max_pages": 20
}
```

### `POST /ask`
Ask questions about your notes.

```
POST /ask?question=What are my main project ideas?&max_context=10
```

### `GET /pages`
List all accessible Notion pages.

### `POST /refresh`
Force refresh the content cache.

## Example Workflow

### 1. Explore Your Content
```bash
# Get an overview of all your notes
curl -X POST http://localhost:8000/context \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 50}'
```

### 2. Find Relevant Notes
```bash
# Search for specific topics
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "startup ideas", "max_results": 10}'
```

### 3. Integrate into Writing
```bash
# Enhance your draft with relevant notes
curl -X POST http://localhost:8000/integrate \
  -H "Content-Type: application/json" \
  -d '{
    "draft": "I have been thinking about building a new product...",
    "query": "product development notes",
    "integration_style": "enhance"
  }'
```

## Architecture

```
src/
├── __init__.py          # Package initialization
├── api.py               # FastAPI application and endpoints
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
| `RELEVANCE_THRESHOLD` | Minimum relevance score | `0.5` |
| `CHUNK_SIZE` | Size of content chunks | `1000` |
| `API_PORT` | API server port | `8000` |

## License

MIT License - see [LICENSE](LICENSE) for details.
