"""FastAPI application for Notion-Claude integration."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .claude_client import ClaudeClient
from .config import get_config
from .content_filter import ContentChunk, ContentFilter, FilterCriteria
from .notion_client import NotionClient, NotionPage


# Request/Response models
class SearchRequest(BaseModel):
    """Request for searching Notion content."""

    query: str = Field(..., description="Search query or topic")
    keywords: list[str] = Field(default_factory=list, description="Additional keywords to filter by")
    exclude_keywords: list[str] = Field(default_factory=list, description="Keywords to exclude")
    recently_edited_days: Optional[int] = Field(None, description="Only include content edited within N days")
    max_results: int = Field(10, ge=1, le=50, description="Maximum number of results")


class AnalyzeRequest(BaseModel):
    """Request for analyzing content."""

    page_ids: Optional[list[str]] = Field(None, description="Specific page IDs to analyze")
    query: Optional[str] = Field(None, description="Optional query to filter content")
    analysis_type: str = Field(
        "summary",
        description="Type of analysis: summary, themes, key_points, entities"
    )
    max_pages: int = Field(20, ge=1, le=100, description="Maximum pages to analyze")


class IntegrateRequest(BaseModel):
    """Request for integrating notes into writing."""

    draft: str = Field(..., description="Your current draft or writing")
    query: str = Field(..., description="Topic or query to find relevant notes")
    integration_style: str = Field(
        "enhance",
        description="Style: enhance, cite, expand, synthesize"
    )
    max_sources: int = Field(5, ge=1, le=20, description="Maximum source notes to use")


class ContextRequest(BaseModel):
    """Request for getting context overview."""

    focus_topic: Optional[str] = Field(None, description="Optional topic to focus analysis on")
    max_pages: int = Field(20, ge=1, le=100, description="Maximum pages to include")


class ContentChunkResponse(BaseModel):
    """Response model for a content chunk."""

    id: str
    title: str
    content: str
    relevance_score: float
    last_edited: datetime
    url: Optional[str] = None


class SearchResponse(BaseModel):
    """Response for search results."""

    query: str
    total_found: int
    results: list[ContentChunkResponse]
    topics: list[str]


class AnalysisResponse(BaseModel):
    """Response for content analysis."""

    analysis_type: str
    content: str
    pages_analyzed: int
    tokens_used: int


class IntegrationResponse(BaseModel):
    """Response for writing integration."""

    integrated_text: str
    sources_used: int
    tokens_used: int


class ContextResponse(BaseModel):
    """Response for context overview."""

    overview: str
    total_pages: int
    main_topics: list[str]
    tokens_used: int


# Global state for clients
class AppState:
    notion_client: Optional[NotionClient] = None
    claude_client: Optional[ClaudeClient] = None
    content_filter: Optional[ContentFilter] = None
    cached_pages: list[NotionPage] = []
    cache_time: Optional[datetime] = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize clients on startup."""
    config = get_config()

    state.notion_client = NotionClient(
        api_key=config.notion_api_key,
        api_version=config.notion_api_version,
    )
    state.claude_client = ClaudeClient(
        api_key=config.anthropic_api_key,
        model=config.claude_model,
        max_tokens=config.max_tokens,
    )
    state.content_filter = ContentFilter(chunk_size=config.chunk_size)

    yield

    # Cleanup
    state.notion_client = None
    state.claude_client = None
    state.content_filter = None


app = FastAPI(
    title="Notion-Claude API",
    description="API for integrating Notion notes with Claude for intelligent content filtering and writing assistance",
    version="0.1.0",
    lifespan=lifespan,
)


async def get_cached_pages(force_refresh: bool = False, max_pages: int = 100) -> list[NotionPage]:
    """Get pages from cache or fetch fresh."""
    cache_duration = 300  # 5 minutes

    if (
        not force_refresh
        and state.cached_pages
        and state.cache_time
        and (datetime.now(timezone.utc) - state.cache_time).seconds < cache_duration
    ):
        return state.cached_pages[:max_pages]

    if not state.notion_client:
        raise HTTPException(status_code=500, detail="Notion client not initialized")

    state.cached_pages = await state.notion_client.fetch_all_pages(max_pages=max_pages)
    state.cache_time = datetime.now(timezone.utc)

    return state.cached_pages


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "name": "Notion-Claude API",
        "version": "0.1.0",
        "endpoints": [
            "/search",
            "/analyze",
            "/integrate",
            "/context",
            "/pages",
            "/refresh",
        ],
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "notion_client": state.notion_client is not None,
        "claude_client": state.claude_client is not None,
        "cached_pages": len(state.cached_pages),
    }


@app.post("/refresh")
async def refresh_cache():
    """Force refresh the Notion content cache."""
    pages = await get_cached_pages(force_refresh=True)
    return {
        "status": "refreshed",
        "pages_loaded": len(pages),
        "cache_time": state.cache_time,
    }


@app.get("/pages")
async def list_pages(
    max_pages: int = Query(50, ge=1, le=200),
    refresh: bool = Query(False),
):
    """List all available Notion pages."""
    pages = await get_cached_pages(force_refresh=refresh, max_pages=max_pages)

    return {
        "total": len(pages),
        "pages": [
            {
                "id": page.id,
                "title": page.title,
                "url": page.url,
                "last_edited": page.last_edited_time,
                "word_count": len(page.full_text.split()),
            }
            for page in pages
        ],
    }


@app.post("/search", response_model=SearchResponse)
async def search_content(request: SearchRequest):
    """
    Search and filter Notion content by relevance.

    This endpoint fetches your Notion pages, filters them based on your criteria,
    and returns the most relevant content chunks.
    """
    if not state.content_filter or not state.claude_client:
        raise HTTPException(status_code=500, detail="Services not initialized")

    # Get pages
    pages = await get_cached_pages()

    if not pages:
        return SearchResponse(
            query=request.query,
            total_found=0,
            results=[],
            topics=[],
        )

    # Convert to chunks
    chunks = state.content_filter.pages_to_chunks(pages)

    # Create filter criteria
    criteria = FilterCriteria(
        query=request.query,
        keywords=request.keywords,
        exclude_keywords=request.exclude_keywords,
        recently_edited_days=request.recently_edited_days,
    )

    # Get top chunks
    top_chunks = state.content_filter.get_top_chunks(
        chunks, criteria, top_k=request.max_results
    )

    # Extract topics from results
    topics = state.content_filter.extract_topics(top_chunks, top_n=5)

    # Build response
    results = [
        ContentChunkResponse(
            id=chunk.id,
            title=chunk.title,
            content=chunk.content,
            relevance_score=chunk.relevance_score,
            last_edited=chunk.last_edited_time,
            url=chunk.metadata.get("url"),
        )
        for chunk in top_chunks
    ]

    return SearchResponse(
        query=request.query,
        total_found=len(top_chunks),
        results=results,
        topics=topics,
    )


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_content(request: AnalyzeRequest):
    """
    Analyze Notion content using Claude.

    Provides different types of analysis:
    - summary: Concise summary of the content
    - themes: Main themes and topics
    - key_points: Important facts and points
    - entities: People, places, concepts mentioned
    """
    if not state.claude_client or not state.content_filter:
        raise HTTPException(status_code=500, detail="Services not initialized")

    # Get pages
    pages = await get_cached_pages(max_pages=request.max_pages)

    if request.page_ids:
        pages = [p for p in pages if p.id in request.page_ids]

    if not pages:
        raise HTTPException(status_code=404, detail="No pages found")

    # If query provided, filter chunks first
    if request.query:
        chunks = state.content_filter.pages_to_chunks(pages)
        criteria = FilterCriteria(query=request.query)
        top_chunks = state.content_filter.get_top_chunks(chunks, criteria, top_k=20)
        content = "\n\n---\n\n".join(
            f"**{c.title}**\n{c.content}" for c in top_chunks
        )
    else:
        content = "\n\n---\n\n".join(
            f"**{p.title}**\n{p.full_text[:2000]}" for p in pages[:15]
        )

    # Analyze with Claude
    response = await state.claude_client.analyze_content(
        content, analysis_type=request.analysis_type
    )

    return AnalysisResponse(
        analysis_type=request.analysis_type,
        content=response.content,
        pages_analyzed=len(pages),
        tokens_used=response.input_tokens + response.output_tokens,
    )


@app.post("/integrate", response_model=IntegrationResponse)
async def integrate_into_writing(request: IntegrateRequest):
    """
    Integrate relevant Notion notes into your writing.

    Finds the most relevant notes for your topic and helps weave them
    into your draft using different integration styles:
    - enhance: Add depth and insights
    - cite: Add references and citations
    - expand: Elaborate with more content
    - synthesize: Combine ideas into new text
    """
    if not state.claude_client or not state.content_filter:
        raise HTTPException(status_code=500, detail="Services not initialized")

    # Get pages and filter
    pages = await get_cached_pages()
    chunks = state.content_filter.pages_to_chunks(pages)

    # Find relevant chunks
    criteria = FilterCriteria(query=request.query)
    top_chunks = state.content_filter.get_top_chunks(
        chunks, criteria, top_k=request.max_sources * 2
    )

    if not top_chunks:
        raise HTTPException(
            status_code=404,
            detail="No relevant content found for your query"
        )

    # Use Claude to refine relevance
    chunk_dicts = [
        {"id": c.id, "title": c.title, "content": c.content}
        for c in top_chunks
    ]
    relevant = await state.claude_client.find_relevant_content(
        request.query, chunk_dicts, top_k=request.max_sources
    )

    # Integrate into writing
    response = await state.claude_client.integrate_into_writing(
        request.draft,
        relevant,
        integration_style=request.integration_style,
    )

    return IntegrationResponse(
        integrated_text=response.content,
        sources_used=len(relevant),
        tokens_used=response.input_tokens + response.output_tokens,
    )


@app.post("/context", response_model=ContextResponse)
async def get_context_overview(request: ContextRequest):
    """
    Get a comprehensive overview of your Notion content.

    Analyzes your notes to identify main topics, themes, connections,
    and potential areas for development. Optionally focus on a specific topic.
    """
    if not state.claude_client or not state.content_filter:
        raise HTTPException(status_code=500, detail="Services not initialized")

    # Get pages
    pages = await get_cached_pages(max_pages=request.max_pages)

    if not pages:
        raise HTTPException(status_code=404, detail="No pages found in Notion")

    # Extract topics first
    chunks = state.content_filter.pages_to_chunks(pages)
    topics = state.content_filter.extract_topics(chunks, top_n=15)

    # Prepare page data for Claude
    page_dicts = [
        {"title": p.title, "content": p.full_text}
        for p in pages
    ]

    # Get context summary from Claude
    response = await state.claude_client.generate_context_summary(
        page_dicts, focus_topic=request.focus_topic
    )

    return ContextResponse(
        overview=response.content,
        total_pages=len(pages),
        main_topics=topics,
        tokens_used=response.input_tokens + response.output_tokens,
    )


@app.post("/ask")
async def ask_about_notes(
    question: str = Query(..., description="Question about your notes"),
    max_context: int = Query(10, ge=1, le=30),
):
    """
    Ask a question about your Notion notes.

    Finds relevant content and uses Claude to answer your question
    based on your notes.
    """
    if not state.claude_client or not state.content_filter:
        raise HTTPException(status_code=500, detail="Services not initialized")

    # Get pages and find relevant content
    pages = await get_cached_pages()
    chunks = state.content_filter.pages_to_chunks(pages)

    criteria = FilterCriteria(query=question)
    relevant_chunks = state.content_filter.get_top_chunks(
        chunks, criteria, top_k=max_context
    )

    if not relevant_chunks:
        return {
            "question": question,
            "answer": "I couldn't find any relevant content in your notes to answer this question.",
            "sources": [],
        }

    # Build context from relevant chunks
    context = "\n\n---\n\n".join(
        f"**{c.title}**\n{c.content}" for c in relevant_chunks
    )

    # Ask Claude
    prompt = f"""Based on the following notes from the user's Notion workspace, please answer their question.

## Notes:
{context}

## Question:
{question}

## Answer:"""

    system = """You are a helpful assistant that answers questions based on the user's personal notes.
Only use information from the provided notes. If the notes don't contain enough information
to answer the question, say so. Be concise and accurate."""

    response = await state.claude_client.complete(prompt, system=system, temperature=0.3)

    return {
        "question": question,
        "answer": response.content,
        "sources": [
            {"title": c.title, "url": c.metadata.get("url")}
            for c in relevant_chunks[:5]
        ],
        "tokens_used": response.input_tokens + response.output_tokens,
    }


def run_server():
    """Run the API server."""
    import uvicorn
    config = get_config()
    uvicorn.run(
        "src.api:app",
        host=config.api_host,
        port=config.api_port,
        reload=config.debug,
    )


if __name__ == "__main__":
    run_server()
