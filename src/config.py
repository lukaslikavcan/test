"""Configuration management for Notion-Claude API."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Application configuration."""

    # Notion API settings
    notion_api_key: str
    notion_api_version: str = "2022-06-28"

    # Claude API settings
    anthropic_api_key: str
    claude_model: str = "claude-opus-4-5-20251101"
    max_tokens: int = 4096

    # Content filtering settings
    relevance_threshold: float = 0.5
    max_content_chunks: int = 50
    chunk_size: int = 1000

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        notion_key = os.getenv("NOTION_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if not notion_key:
            raise ValueError("NOTION_API_KEY environment variable is required")
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        return cls(
            notion_api_key=notion_key,
            anthropic_api_key=anthropic_key,
            notion_api_version=os.getenv("NOTION_API_VERSION", "2022-06-28"),
            claude_model=os.getenv("CLAUDE_MODEL", "claude-opus-4-5-20251101"),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
            relevance_threshold=float(os.getenv("RELEVANCE_THRESHOLD", "0.5")),
            max_content_chunks=int(os.getenv("MAX_CONTENT_CHUNKS", "50")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            debug=os.getenv("DEBUG", "false").lower() == "true",
        )


def get_config() -> Config:
    """Get application configuration."""
    return Config.from_env()
