"""MCP Server for Notion-Claude integration.

This server exposes Notion content and Claude analysis as tools
that can be used directly in Claude Desktop/Chat.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Print to stderr for debugging (shows in Claude Desktop logs)
def log(msg: str):
    print(f"[notion-claude] {msg}", file=sys.stderr)

log("Loading MCP server module...")

try:
    from .claude_client import ClaudeClient
    from .content_filter import ContentChunk, ContentFilter, FilterCriteria
    from .notion_client import NotionClient, NotionPage
    log("Imports successful")
except Exception as e:
    log(f"Import error: {e}")
    raise


# Initialize server
server = Server("notion-claude")

# Global state
notion_client: NotionClient | None = None
claude_client: ClaudeClient | None = None
content_filter: ContentFilter | None = None
cached_pages: list[NotionPage] = []
cache_time: datetime | None = None


def get_env_or_raise(key: str) -> str:
    """Get environment variable or raise error."""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"{key} environment variable is required")
    return value


def init_clients():
    """Initialize API clients."""
    global notion_client, claude_client, content_filter

    log("Initializing clients...")

    if notion_client is None:
        notion_client = NotionClient(
            api_key=get_env_or_raise("NOTION_API_KEY"),
        )
    if claude_client is None:
        claude_client = ClaudeClient(
            api_key=get_env_or_raise("ANTHROPIC_API_KEY"),
            model=os.getenv("CLAUDE_MODEL", "claude-opus-4-5-20251101"),
        )
    if content_filter is None:
        content_filter = ContentFilter(
            chunk_size=int(os.getenv("CHUNK_SIZE", "1000"))
        )

    log("Clients initialized")


async def get_pages(force_refresh: bool = False, max_pages: int = 100) -> list[NotionPage]:
    """Get pages from cache or fetch fresh."""
    global cached_pages, cache_time

    cache_duration = 300  # 5 minutes

    if (
        not force_refresh
        and cached_pages
        and cache_time
        and (datetime.now(timezone.utc) - cache_time).seconds < cache_duration
    ):
        return cached_pages[:max_pages]

    init_clients()
    if notion_client:
        cached_pages = await notion_client.fetch_all_pages(max_pages=max_pages)
        cache_time = datetime.now(timezone.utc)

    return cached_pages


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    log("list_tools called")
    return [
        Tool(
            name="notion_search",
            description="Search through your Notion notes and find relevant content. Use this to find specific topics, ideas, or information in your notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query or topic to find in your notes",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="notion_context",
            description="Get a comprehensive overview of your Notion content. Use this to understand what topics, themes, and ideas are in your notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "focus_topic": {
                        "type": "string",
                        "description": "Optional topic to focus the analysis on",
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "Maximum pages to analyze (default: 20)",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="notion_analyze",
            description="Analyze your Notion content to extract summaries, themes, key points, or entities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional query to filter which content to analyze",
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["summary", "themes", "key_points", "entities"],
                        "description": "Type of analysis: summary, themes, key_points, or entities",
                        "default": "summary",
                    },
                },
            },
        ),
        Tool(
            name="notion_integrate",
            description="Find relevant notes and integrate them into your writing. Provide your draft and a topic to find matching notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "draft": {
                        "type": "string",
                        "description": "Your current draft or writing to enhance",
                    },
                    "query": {
                        "type": "string",
                        "description": "Topic or query to find relevant notes",
                    },
                    "style": {
                        "type": "string",
                        "enum": ["enhance", "cite", "expand", "synthesize"],
                        "description": "Integration style: enhance (add depth), cite (add references), expand (elaborate), synthesize (combine ideas)",
                        "default": "enhance",
                    },
                    "max_sources": {
                        "type": "integer",
                        "description": "Maximum number of source notes to use (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["draft", "query"],
            },
        ),
        Tool(
            name="notion_ask",
            description="Ask a question about your Notion notes. The system will find relevant content and answer based on your notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Question to ask about your notes",
                    },
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="notion_list_pages",
            description="List all available Notion pages in your workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_pages": {
                        "type": "integer",
                        "description": "Maximum pages to list (default: 50)",
                        "default": 50,
                    },
                },
            },
        ),
        Tool(
            name="notion_refresh",
            description="Force refresh the Notion content cache. Use this if you've recently updated your Notion and want to see the changes.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    log(f"call_tool: {name}")
    try:
        init_clients()

        if name == "notion_search":
            return await handle_search(arguments)
        elif name == "notion_context":
            return await handle_context(arguments)
        elif name == "notion_analyze":
            return await handle_analyze(arguments)
        elif name == "notion_integrate":
            return await handle_integrate(arguments)
        elif name == "notion_ask":
            return await handle_ask(arguments)
        elif name == "notion_list_pages":
            return await handle_list_pages(arguments)
        elif name == "notion_refresh":
            return await handle_refresh(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        log(f"Error in call_tool: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_search(args: dict) -> list[TextContent]:
    """Handle notion_search tool."""
    query = args.get("query", "")
    max_results = args.get("max_results", 10)

    pages = await get_pages()
    if not pages:
        return [TextContent(type="text", text="No pages found in your Notion workspace.")]

    chunks = content_filter.pages_to_chunks(pages)
    criteria = FilterCriteria(query=query)
    top_chunks = content_filter.get_top_chunks(chunks, criteria, top_k=max_results)

    if not top_chunks:
        return [TextContent(type="text", text=f"No results found for: {query}")]

    results = []
    for chunk in top_chunks:
        results.append(
            f"## {chunk.title}\n"
            f"*Relevance: {chunk.relevance_score:.2f}*\n\n"
            f"{chunk.content}\n"
        )

    topics = content_filter.extract_topics(top_chunks, top_n=5)

    output = f"# Search Results for: {query}\n\n"
    output += f"**Found {len(top_chunks)} relevant notes**\n"
    output += f"**Related topics:** {', '.join(topics)}\n\n"
    output += "---\n\n".join(results)

    return [TextContent(type="text", text=output)]


async def handle_context(args: dict) -> list[TextContent]:
    """Handle notion_context tool."""
    focus_topic = args.get("focus_topic")
    max_pages = args.get("max_pages", 20)

    pages = await get_pages(max_pages=max_pages)
    if not pages:
        return [TextContent(type="text", text="No pages found in your Notion workspace.")]

    # Extract topics
    chunks = content_filter.pages_to_chunks(pages)
    topics = content_filter.extract_topics(chunks, top_n=15)

    # Get context summary from Claude
    page_dicts = [{"title": p.title, "content": p.full_text} for p in pages]
    response = await claude_client.generate_context_summary(page_dicts, focus_topic=focus_topic)

    output = f"# Notion Content Overview\n\n"
    output += f"**Total pages analyzed:** {len(pages)}\n"
    output += f"**Main topics:** {', '.join(topics)}\n\n"
    output += "---\n\n"
    output += response.content

    return [TextContent(type="text", text=output)]


async def handle_analyze(args: dict) -> list[TextContent]:
    """Handle notion_analyze tool."""
    query = args.get("query")
    analysis_type = args.get("analysis_type", "summary")

    pages = await get_pages()
    if not pages:
        return [TextContent(type="text", text="No pages found in your Notion workspace.")]

    # Filter if query provided
    if query:
        chunks = content_filter.pages_to_chunks(pages)
        criteria = FilterCriteria(query=query)
        top_chunks = content_filter.get_top_chunks(chunks, criteria, top_k=20)
        content = "\n\n---\n\n".join(
            f"**{c.title}**\n{c.content}" for c in top_chunks
        )
    else:
        content = "\n\n---\n\n".join(
            f"**{p.title}**\n{p.full_text[:2000]}" for p in pages[:15]
        )

    response = await claude_client.analyze_content(content, analysis_type=analysis_type)

    output = f"# Content Analysis ({analysis_type.title()})\n\n"
    if query:
        output += f"**Filtered by:** {query}\n\n"
    output += response.content

    return [TextContent(type="text", text=output)]


async def handle_integrate(args: dict) -> list[TextContent]:
    """Handle notion_integrate tool."""
    draft = args.get("draft", "")
    query = args.get("query", "")
    style = args.get("style", "enhance")
    max_sources = args.get("max_sources", 5)

    pages = await get_pages()
    chunks = content_filter.pages_to_chunks(pages)

    # Find relevant chunks
    criteria = FilterCriteria(query=query)
    top_chunks = content_filter.get_top_chunks(chunks, criteria, top_k=max_sources * 2)

    if not top_chunks:
        return [TextContent(
            type="text",
            text=f"No relevant content found for: {query}"
        )]

    # Use Claude to refine relevance
    chunk_dicts = [
        {"id": c.id, "title": c.title, "content": c.content}
        for c in top_chunks
    ]
    relevant = await claude_client.find_relevant_content(query, chunk_dicts, top_k=max_sources)

    # Integrate into writing
    response = await claude_client.integrate_into_writing(draft, relevant, integration_style=style)

    output = f"# Integrated Writing\n\n"
    output += f"**Style:** {style}\n"
    output += f"**Sources used:** {len(relevant)}\n\n"
    output += "---\n\n"
    output += response.content
    output += "\n\n---\n\n**Sources:**\n"
    for r in relevant:
        output += f"- {r.get('title', 'Untitled')}\n"

    return [TextContent(type="text", text=output)]


async def handle_ask(args: dict) -> list[TextContent]:
    """Handle notion_ask tool."""
    question = args.get("question", "")

    pages = await get_pages()
    chunks = content_filter.pages_to_chunks(pages)

    criteria = FilterCriteria(query=question)
    relevant_chunks = content_filter.get_top_chunks(chunks, criteria, top_k=10)

    if not relevant_chunks:
        return [TextContent(
            type="text",
            text="I couldn't find any relevant content in your notes to answer this question."
        )]

    # Build context
    context = "\n\n---\n\n".join(
        f"**{c.title}**\n{c.content}" for c in relevant_chunks
    )

    prompt = f"""Based on the following notes from the user's Notion workspace, please answer their question.

## Notes:
{context}

## Question:
{question}

## Answer:"""

    system = """You are a helpful assistant that answers questions based on the user's personal notes.
Only use information from the provided notes. If the notes don't contain enough information
to answer the question, say so. Be concise and accurate."""

    response = await claude_client.complete(prompt, system=system, temperature=0.3)

    output = f"# Answer\n\n{response.content}\n\n"
    output += "---\n\n**Based on these notes:**\n"
    for c in relevant_chunks[:5]:
        output += f"- {c.title}\n"

    return [TextContent(type="text", text=output)]


async def handle_list_pages(args: dict) -> list[TextContent]:
    """Handle notion_list_pages tool."""
    max_pages = args.get("max_pages", 50)

    pages = await get_pages(max_pages=max_pages)

    if not pages:
        return [TextContent(type="text", text="No pages found in your Notion workspace.")]

    output = f"# Your Notion Pages ({len(pages)} total)\n\n"
    for page in pages:
        word_count = len(page.full_text.split())
        output += f"- **{page.title}** ({word_count} words)\n"

    return [TextContent(type="text", text=output)]


async def handle_refresh(args: dict) -> list[TextContent]:
    """Handle notion_refresh tool."""
    pages = await get_pages(force_refresh=True)

    return [TextContent(
        type="text",
        text=f"Cache refreshed. Loaded {len(pages)} pages from Notion."
    )]


async def main():
    """Run the MCP server."""
    log("Starting MCP server...")
    try:
        async with stdio_server() as (read_stream, write_stream):
            log("stdio_server connected")
            await server.run(read_stream, write_stream, server.create_initialization_options())
    except Exception as e:
        log(f"Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
