"""Content filtering and relevance scoring for Notion content."""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from .notion_client import NotionPage


@dataclass
class ContentChunk:
    """A chunk of content with metadata for filtering."""

    id: str
    page_id: str
    title: str
    content: str
    created_time: datetime
    last_edited_time: datetime
    word_count: int = 0
    relevance_score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.word_count = len(self.content.split())


@dataclass
class FilterCriteria:
    """Criteria for filtering content."""

    # Text-based filters
    query: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)

    # Time-based filters
    min_date: Optional[datetime] = None
    max_date: Optional[datetime] = None
    recently_edited_days: Optional[int] = None

    # Content filters
    min_word_count: int = 10
    max_word_count: Optional[int] = None

    # Scoring weights
    recency_weight: float = 0.3
    keyword_weight: float = 0.5
    length_weight: float = 0.2


class ContentFilter:
    """Filter and score content based on relevance criteria."""

    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size

    def pages_to_chunks(self, pages: list[NotionPage]) -> list[ContentChunk]:
        """Convert NotionPages to ContentChunks for processing."""
        chunks = []

        for page in pages:
            if not page.full_text:
                page.extract_full_text()

            # Split large pages into chunks
            text = page.full_text
            if len(text) > self.chunk_size:
                text_chunks = self._split_into_chunks(text)
                for i, chunk_text in enumerate(text_chunks):
                    chunks.append(
                        ContentChunk(
                            id=f"{page.id}_{i}",
                            page_id=page.id,
                            title=f"{page.title} (Part {i + 1})",
                            content=chunk_text,
                            created_time=page.created_time,
                            last_edited_time=page.last_edited_time,
                            metadata={"url": page.url, "chunk_index": i},
                        )
                    )
            else:
                chunks.append(
                    ContentChunk(
                        id=page.id,
                        page_id=page.id,
                        title=page.title,
                        content=text,
                        created_time=page.created_time,
                        last_edited_time=page.last_edited_time,
                        metadata={"url": page.url},
                    )
                )

        return chunks

    def _split_into_chunks(self, text: str) -> list[str]:
        """Split text into chunks, trying to break at paragraph boundaries."""
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) < self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def filter_chunks(
        self, chunks: list[ContentChunk], criteria: FilterCriteria
    ) -> list[ContentChunk]:
        """Filter chunks based on criteria."""
        filtered = []

        for chunk in chunks:
            # Word count filter
            if chunk.word_count < criteria.min_word_count:
                continue
            if criteria.max_word_count and chunk.word_count > criteria.max_word_count:
                continue

            # Date filters
            if criteria.min_date and chunk.last_edited_time < criteria.min_date:
                continue
            if criteria.max_date and chunk.last_edited_time > criteria.max_date:
                continue

            if criteria.recently_edited_days:
                cutoff = datetime.now(timezone.utc) - timedelta(
                    days=criteria.recently_edited_days
                )
                if chunk.last_edited_time < cutoff:
                    continue

            # Keyword exclusion filter
            if criteria.exclude_keywords:
                content_lower = chunk.content.lower()
                if any(kw.lower() in content_lower for kw in criteria.exclude_keywords):
                    continue

            filtered.append(chunk)

        return filtered

    def score_chunks(
        self, chunks: list[ContentChunk], criteria: FilterCriteria
    ) -> list[ContentChunk]:
        """Score chunks based on relevance to criteria."""
        now = datetime.now(timezone.utc)

        # Calculate max age for normalization
        if chunks:
            oldest = min(c.last_edited_time for c in chunks)
            max_age_days = max((now - oldest).days, 1)
        else:
            max_age_days = 1

        for chunk in chunks:
            scores = []

            # Recency score (0-1, higher for more recent)
            age_days = (now - chunk.last_edited_time).days
            recency_score = 1 - (age_days / max_age_days)
            scores.append(recency_score * criteria.recency_weight)

            # Keyword relevance score
            if criteria.keywords or criteria.query:
                keyword_score = self._calculate_keyword_score(
                    chunk.content,
                    criteria.keywords,
                    criteria.query,
                )
                scores.append(keyword_score * criteria.keyword_weight)
            else:
                scores.append(0)

            # Length score (prefer medium-length content)
            optimal_length = 500
            length_diff = abs(chunk.word_count - optimal_length) / optimal_length
            length_score = max(0, 1 - length_diff)
            scores.append(length_score * criteria.length_weight)

            chunk.relevance_score = sum(scores)

        return chunks

    def _calculate_keyword_score(
        self,
        content: str,
        keywords: list[str],
        query: Optional[str],
    ) -> float:
        """Calculate keyword relevance score for content."""
        content_lower = content.lower()
        content_words = set(re.findall(r"\w+", content_lower))

        all_keywords = list(keywords)
        if query:
            all_keywords.extend(query.lower().split())

        if not all_keywords:
            return 0.5  # Neutral score if no keywords

        # Count keyword matches
        matches = 0
        for keyword in all_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in content_lower:
                # Exact phrase match scores higher
                matches += 2
            elif keyword_lower in content_words:
                # Word match
                matches += 1

        # Normalize score
        max_possible = len(all_keywords) * 2
        return min(matches / max_possible, 1.0)

    def get_top_chunks(
        self,
        chunks: list[ContentChunk],
        criteria: FilterCriteria,
        top_k: int = 10,
    ) -> list[ContentChunk]:
        """Get the top K most relevant chunks based on criteria."""
        # Filter first
        filtered = self.filter_chunks(chunks, criteria)

        # Score remaining
        scored = self.score_chunks(filtered, criteria)

        # Sort by score and return top K
        sorted_chunks = sorted(scored, key=lambda c: c.relevance_score, reverse=True)
        return sorted_chunks[:top_k]

    def extract_topics(self, chunks: list[ContentChunk], top_n: int = 10) -> list[str]:
        """Extract the most common topics/keywords from chunks."""
        # Common words to exclude
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "this", "that", "these", "those", "i", "you", "he", "she", "it",
            "we", "they", "what", "which", "who", "when", "where", "why", "how",
            "all", "each", "every", "both", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same", "so",
            "than", "too", "very", "just", "also", "now", "here", "there",
        }

        word_counts: Counter = Counter()

        for chunk in chunks:
            words = re.findall(r"\b[a-zA-Z]{3,}\b", chunk.content.lower())
            for word in words:
                if word not in stop_words:
                    word_counts[word] += 1

        return [word for word, _ in word_counts.most_common(top_n)]

    def group_by_topic(
        self, chunks: list[ContentChunk], topics: list[str]
    ) -> dict[str, list[ContentChunk]]:
        """Group chunks by their most relevant topic."""
        groups: dict[str, list[ContentChunk]] = {topic: [] for topic in topics}
        groups["other"] = []

        for chunk in chunks:
            content_lower = chunk.content.lower()
            best_topic = None
            best_count = 0

            for topic in topics:
                count = content_lower.count(topic)
                if count > best_count:
                    best_count = count
                    best_topic = topic

            if best_topic and best_count > 0:
                groups[best_topic].append(chunk)
            else:
                groups["other"].append(chunk)

        # Remove empty groups
        return {k: v for k, v in groups.items() if v}
