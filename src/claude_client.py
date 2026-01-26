"""Claude API client for content analysis and writing assistance."""

from dataclasses import dataclass
from typing import Optional
import httpx


@dataclass
class ClaudeResponse:
    """Response from Claude API."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str


class ClaudeClient:
    """Client for interacting with the Claude API."""

    BASE_URL = "https://api.anthropic.com/v1"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-5-20251101",
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def _request(self, endpoint: str, json: dict) -> dict:
        """Make an authenticated request to the Claude API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/{endpoint}",
                headers=self.headers,
                json=json,
                timeout=120.0,
            )
            response.raise_for_status()
            return response.json()

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> ClaudeResponse:
        """Generate a completion from Claude."""
        payload = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system:
            payload["system"] = system

        response = await self._request("messages", payload)

        content = ""
        for block in response.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        return ClaudeResponse(
            content=content,
            model=response.get("model", self.model),
            input_tokens=response.get("usage", {}).get("input_tokens", 0),
            output_tokens=response.get("usage", {}).get("output_tokens", 0),
            stop_reason=response.get("stop_reason", ""),
        )

    async def analyze_content(
        self, content: str, analysis_type: str = "summary"
    ) -> ClaudeResponse:
        """
        Analyze content with different analysis types.

        Args:
            content: The content to analyze
            analysis_type: Type of analysis - 'summary', 'themes', 'key_points', 'entities'
        """
        prompts = {
            "summary": f"""Provide a concise summary of the following content, highlighting the main ideas and conclusions:

{content}

Summary:""",
            "themes": f"""Identify and list the main themes and topics present in the following content:

{content}

Themes:""",
            "key_points": f"""Extract the key points and important facts from the following content as a bullet-point list:

{content}

Key Points:""",
            "entities": f"""Identify and categorize the main entities (people, places, concepts, projects) mentioned in the following content:

{content}

Entities:""",
        }

        system = """You are an expert content analyst. Your task is to analyze text content
and extract meaningful insights. Be concise, accurate, and focus on the most important information."""

        prompt = prompts.get(analysis_type, prompts["summary"])
        return await self.complete(prompt, system=system, temperature=0.3)

    async def find_relevant_content(
        self,
        query: str,
        content_chunks: list[dict],
        top_k: int = 10,
    ) -> list[dict]:
        """
        Use Claude to find the most relevant content chunks for a query.

        Args:
            query: The search query or topic of interest
            content_chunks: List of dicts with 'id', 'title', 'content' keys
            top_k: Number of most relevant chunks to return
        """
        # Prepare content summary for Claude
        chunk_summaries = []
        for i, chunk in enumerate(content_chunks):
            chunk_summaries.append(
                f"[{i}] Title: {chunk.get('title', 'Untitled')}\n"
                f"Content preview: {chunk.get('content', '')[:500]}..."
            )

        chunks_text = "\n\n".join(chunk_summaries)

        prompt = f"""Given the following query/topic and a list of content chunks, identify the {top_k} most relevant chunks.

Query/Topic: {query}

Available content chunks:
{chunks_text}

Return ONLY the indices of the {top_k} most relevant chunks as a comma-separated list of numbers (e.g., "0, 3, 7, 12").
Consider relevance based on:
1. Direct topic match
2. Related concepts and themes
3. Supporting information
4. Useful context

Most relevant chunk indices:"""

        system = """You are a relevance ranking expert. Your task is to identify the most relevant
content for a given query. Return only the numeric indices as requested."""

        response = await self.complete(prompt, system=system, temperature=0.1)

        # Parse response to get indices
        try:
            indices_str = response.content.strip()
            indices = [
                int(idx.strip())
                for idx in indices_str.split(",")
                if idx.strip().isdigit()
            ]
            indices = [i for i in indices if 0 <= i < len(content_chunks)][:top_k]
        except (ValueError, AttributeError):
            indices = list(range(min(top_k, len(content_chunks))))

        return [content_chunks[i] for i in indices]

    async def integrate_into_writing(
        self,
        user_draft: str,
        relevant_content: list[dict],
        integration_style: str = "enhance",
    ) -> ClaudeResponse:
        """
        Help integrate relevant notes into user's writing.

        Args:
            user_draft: The user's current draft or writing
            relevant_content: List of relevant content chunks to integrate
            integration_style: 'enhance' (add depth), 'cite' (add references),
                             'expand' (elaborate), 'synthesize' (combine ideas)
        """
        content_text = "\n\n---\n\n".join(
            f"**{chunk.get('title', 'Note')}**\n{chunk.get('content', '')}"
            for chunk in relevant_content
        )

        style_instructions = {
            "enhance": """Enhance the draft by weaving in relevant ideas, examples, and insights
from the notes. Maintain the original voice and structure while adding depth.""",
            "cite": """Add appropriate references and citations from the notes to support
the points in the draft. Use inline citations or footnote-style references.""",
            "expand": """Expand on the ideas in the draft using the additional context
and information from the notes. Add new paragraphs or sections where appropriate.""",
            "synthesize": """Synthesize the ideas from both the draft and notes into
a cohesive new piece that combines the best elements of both sources.""",
        }

        instruction = style_instructions.get(integration_style, style_instructions["enhance"])

        prompt = f"""I have a draft and some relevant notes from my Notion. Please help me integrate them.

## My Draft:
{user_draft}

## Relevant Notes from Notion:
{content_text}

## Task:
{instruction}

Please provide the improved/integrated version:"""

        system = """You are an expert writing assistant. Help users integrate their notes and
research into their writing while maintaining their voice and style. Produce clean,
well-structured output that flows naturally."""

        return await self.complete(prompt, system=system, temperature=0.7)

    async def generate_context_summary(
        self, pages: list[dict], focus_topic: Optional[str] = None
    ) -> ClaudeResponse:
        """
        Generate a summary of the user's Notion content to understand context.

        Args:
            pages: List of page data with titles and content
            focus_topic: Optional topic to focus the summary on
        """
        pages_text = "\n\n".join(
            f"## {page.get('title', 'Untitled')}\n{page.get('content', '')[:1000]}..."
            for page in pages[:20]  # Limit to prevent token overflow
        )

        focus_instruction = ""
        if focus_topic:
            focus_instruction = f"\nPay special attention to content related to: {focus_topic}"

        prompt = f"""Analyze the following collection of notes and pages from a Notion workspace.
Provide a comprehensive overview that includes:

1. **Main Topics**: What are the primary subjects covered?
2. **Key Themes**: What recurring ideas or themes emerge?
3. **Connections**: How do different notes relate to each other?
4. **Knowledge Gaps**: What areas might benefit from more development?
5. **Writing Potential**: What content could be developed into longer pieces?
{focus_instruction}

## Notes Collection:
{pages_text}

## Analysis:"""

        system = """You are an expert at analyzing personal knowledge bases and notes.
Help users understand the landscape of their collected knowledge and identify opportunities
for synthesis and development."""

        return await self.complete(prompt, system=system, temperature=0.5)
