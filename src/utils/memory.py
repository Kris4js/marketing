"""
Long-term Memory System

Memory system using:
- File system for persistence
- Keyword matching for search
- Time decay for relevance scoring

Simplified from vector database approach to file-based storage.
"""

import json
import re
import secrets
import time
from pathlib import Path
from typing import Literal

import aiofiles
from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    id: str = Field(..., description="Unique identifier for the memory entry")
    content: str = Field(..., description="Content of the memory entry")
    source: Literal["user", "agent", "system"] = Field(
        ..., description="Source of the memory entry"
    )
    tags: list[str] = Field(
        default_factory=list, description="List of tags associated with the entry"
    )
    created_at: int = Field(
        ..., description="Timestamp when the entry was created (ms)"
    )


class MemorySearchResult(BaseModel):
    entry: MemoryEntry = Field(
        ..., description="Memory entry matching the search criteria"
    )
    score: float = Field(..., description="Relevance score of the search result")
    snippet: str = Field(
        ..., description="Snippet from the memory entry highlighting relevance"
    )


class MemoryManager:
    def __init__(self, base_dir: str = "./.mini-agent/memory") -> None:
        self.base_dir: Path = Path(base_dir)
        self.entries: list[MemoryEntry] = []
        self.loaded: bool = False

    @property
    def index_path(self) -> Path:
        return self.base_dir / "index.json"

    async def load(self) -> None:
        """Load memory index."""
        if self.loaded:
            return
        try:
            async with aiofiles.open(self.index_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)
                self.entries = [MemoryEntry(**entry) for entry in data]
        except (FileNotFoundError, json.JSONDecodeError):
            self.entries = []
        self.loaded = True

    async def _save(self) -> None:
        """Save memory index."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self.index_path, "w", encoding="utf-8") as f:
            data = [entry.model_dump() for entry in self.entries]
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))

    async def add(
        self,
        content: str,
        source: Literal["user", "agent", "system"],
        tags: list[str] | None = None,
    ) -> str:
        """Add a memory entry."""
        await self.load()

        entry_id = f"mem_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        entry = MemoryEntry(
            id=entry_id,
            content=content,
            source=source,
            tags=tags or [],
            created_at=int(time.time() * 1000),
        )
        self.entries.append(entry)
        await self._save()
        return entry_id

    async def search(self, query: str, limit: int = 5) -> list[MemorySearchResult]:
        """Search memories using keyword matching."""
        await self.load()

        query_terms = [t for t in re.split(r"\s+", query.lower()) if t]
        scored: list[MemorySearchResult] = []

        for entry in self.entries:
            text = entry.content.lower()
            score = 0.0

            # Keyword matching score
            for term in query_terms:
                if term in text:
                    score += 1.0
                    # Tag match bonus
                    if any(term in tag.lower() for tag in entry.tags):
                        score += 0.5

            if score > 0:
                # Time decay: newer memories score higher
                age_hours = (time.time() * 1000 - entry.created_at) / (1000 * 60 * 60)
                recency_boost = max(0, 1 - age_hours / (24 * 30))  # 30 day decay
                score += recency_boost * 0.3

                snippet = entry.content[:200]
                scored.append(
                    MemorySearchResult(entry=entry, score=score, snippet=snippet)
                )

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:limit]

    async def get_by_id(self, entry_id: str) -> MemoryEntry | None:
        """Get memory by ID."""
        await self.load()
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    async def sync_from_files(self) -> int:
        """Scan .md files in memory/files directory and sync to index."""
        await self.load()
        mem_dir = self.base_dir / "files"

        try:
            files = list(mem_dir.iterdir())
            synced = 0

            for file_path in files:
                if not file_path.suffix == ".md":
                    continue

                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()

                file_tag = f"file:{file_path.name}"
                existing_idx = next(
                    (i for i, e in enumerate(self.entries) if file_tag in e.tags),
                    None,
                )

                if existing_idx is not None:
                    self.entries[existing_idx] = self.entries[existing_idx].model_copy(
                        update={"content": content}
                    )
                else:
                    await self.add(content, "system", [file_tag])
                synced += 1

            await self._save()
            return synced
        except FileNotFoundError:
            return 0

    async def get_all(self) -> list[MemoryEntry]:
        """Get all memories (for debugging)."""
        await self.load()
        return self.entries

    async def clear(self) -> None:
        """Clear all memories."""
        self.entries = []
        await self._save()
