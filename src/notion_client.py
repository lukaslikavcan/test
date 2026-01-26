"""Notion API client for fetching and processing notes."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import httpx


@dataclass
class NotionBlock:
    """Represents a Notion block."""

    id: str
    type: str
    content: str
    created_time: datetime
    last_edited_time: datetime
    parent_id: Optional[str] = None
    children: list["NotionBlock"] = field(default_factory=list)


@dataclass
class NotionPage:
    """Represents a Notion page with its content."""

    id: str
    title: str
    url: str
    created_time: datetime
    last_edited_time: datetime
    properties: dict[str, Any] = field(default_factory=dict)
    blocks: list[NotionBlock] = field(default_factory=list)
    full_text: str = ""

    def extract_full_text(self) -> str:
        """Extract all text content from the page."""
        texts = [self.title]
        for block in self.blocks:
            if block.content:
                texts.append(block.content)
            for child in block.children:
                if child.content:
                    texts.append(child.content)
        self.full_text = "\n\n".join(texts)
        return self.full_text


class NotionClient:
    """Client for interacting with the Notion API."""

    BASE_URL = "https://api.notion.com/v1"

    def __init__(self, api_key: str, api_version: str = "2022-06-28"):
        self.api_key = api_key
        self.api_version = api_version
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": api_version,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Make an authenticated request to the Notion API."""
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self.BASE_URL}/{endpoint}",
                headers=self.headers,
                json=json,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def search(
        self,
        query: str = "",
        filter_type: Optional[str] = None,
        page_size: int = 100,
    ) -> list[dict]:
        """
        Search across all pages and databases in the workspace.

        Args:
            query: Search query string
            filter_type: Filter by 'page' or 'database'
            page_size: Number of results per page
        """
        payload: dict[str, Any] = {"page_size": page_size}

        if query:
            payload["query"] = query

        if filter_type:
            payload["filter"] = {"property": "object", "value": filter_type}

        results = []
        has_more = True
        start_cursor = None

        while has_more:
            if start_cursor:
                payload["start_cursor"] = start_cursor

            response = await self._request("POST", "search", json=payload)
            results.extend(response.get("results", []))
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

        return results

    async def get_page(self, page_id: str) -> dict:
        """Get a page by ID."""
        return await self._request("GET", f"pages/{page_id}")

    async def get_block_children(
        self, block_id: str, page_size: int = 100
    ) -> list[dict]:
        """Get all children of a block."""
        results = []
        has_more = True
        start_cursor = None

        while has_more:
            params = {"page_size": page_size}
            if start_cursor:
                params["start_cursor"] = start_cursor

            response = await self._request(
                "GET", f"blocks/{block_id}/children", params=params
            )
            results.extend(response.get("results", []))
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

        return results

    async def get_database(self, database_id: str) -> dict:
        """Get a database by ID."""
        return await self._request("GET", f"databases/{database_id}")

    async def query_database(
        self,
        database_id: str,
        filter: Optional[dict] = None,
        sorts: Optional[list] = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Query a database with optional filters and sorts."""
        payload: dict[str, Any] = {"page_size": page_size}

        if filter:
            payload["filter"] = filter
        if sorts:
            payload["sorts"] = sorts

        results = []
        has_more = True
        start_cursor = None

        while has_more:
            if start_cursor:
                payload["start_cursor"] = start_cursor

            response = await self._request(
                "POST", f"databases/{database_id}/query", json=payload
            )
            results.extend(response.get("results", []))
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

        return results

    def _extract_text_from_rich_text(self, rich_text: list[dict]) -> str:
        """Extract plain text from Notion rich text array."""
        return "".join(item.get("plain_text", "") for item in rich_text)

    def _extract_block_content(self, block: dict) -> str:
        """Extract text content from a block."""
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})

        # Text-based blocks
        if "rich_text" in block_data:
            return self._extract_text_from_rich_text(block_data["rich_text"])

        # Special block types
        if block_type == "child_page":
            return block_data.get("title", "")
        if block_type == "child_database":
            return block_data.get("title", "")
        if block_type == "equation":
            return block_data.get("expression", "")
        if block_type == "code":
            code_text = self._extract_text_from_rich_text(
                block_data.get("rich_text", [])
            )
            language = block_data.get("language", "")
            return f"```{language}\n{code_text}\n```"

        return ""

    def _extract_title_from_properties(self, properties: dict) -> str:
        """Extract title from page properties."""
        for prop in properties.values():
            if prop.get("type") == "title":
                return self._extract_text_from_rich_text(prop.get("title", []))
        return "Untitled"

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """Parse ISO datetime string."""
        return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))

    async def fetch_page_with_content(self, page_id: str) -> NotionPage:
        """Fetch a page with all its block content."""
        page_data = await self.get_page(page_id)
        blocks_data = await self.get_block_children(page_id)

        # Parse blocks
        blocks = []
        for block_data in blocks_data:
            block = NotionBlock(
                id=block_data["id"],
                type=block_data["type"],
                content=self._extract_block_content(block_data),
                created_time=self._parse_datetime(block_data["created_time"]),
                last_edited_time=self._parse_datetime(block_data["last_edited_time"]),
                parent_id=page_id,
            )

            # Fetch children if block has them
            if block_data.get("has_children", False):
                children_data = await self.get_block_children(block_data["id"])
                block.children = [
                    NotionBlock(
                        id=child["id"],
                        type=child["type"],
                        content=self._extract_block_content(child),
                        created_time=self._parse_datetime(child["created_time"]),
                        last_edited_time=self._parse_datetime(child["last_edited_time"]),
                        parent_id=block_data["id"],
                    )
                    for child in children_data
                ]
            blocks.append(block)

        # Build page object
        properties = page_data.get("properties", {})
        page = NotionPage(
            id=page_data["id"],
            title=self._extract_title_from_properties(properties),
            url=page_data.get("url", ""),
            created_time=self._parse_datetime(page_data["created_time"]),
            last_edited_time=self._parse_datetime(page_data["last_edited_time"]),
            properties=properties,
            blocks=blocks,
        )
        page.extract_full_text()

        return page

    async def fetch_all_pages(
        self, query: str = "", max_pages: Optional[int] = None
    ) -> list[NotionPage]:
        """Fetch all pages in the workspace with their content."""
        search_results = await self.search(query=query, filter_type="page")

        if max_pages:
            search_results = search_results[:max_pages]

        # Fetch pages concurrently with rate limiting
        pages = []
        batch_size = 5  # Process 5 pages at a time to avoid rate limits

        for i in range(0, len(search_results), batch_size):
            batch = search_results[i : i + batch_size]
            tasks = [self.fetch_page_with_content(result["id"]) for result in batch]
            batch_pages = await asyncio.gather(*tasks, return_exceptions=True)

            for page in batch_pages:
                if isinstance(page, NotionPage):
                    pages.append(page)

            # Small delay between batches to respect rate limits
            if i + batch_size < len(search_results):
                await asyncio.sleep(0.5)

        return pages
