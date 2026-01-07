"""Data models for AgentNA memory and storage."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SymbolType(str, Enum):
    """Types of code symbols."""

    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    IMPORT = "import"
    DECORATOR = "decorator"


class RelationType(str, Enum):
    """Types of relationships between code elements."""

    IMPORTS = "imports"  # A imports B
    CALLS = "calls"  # A calls B
    INHERITS = "inherits"  # A inherits from B
    IMPLEMENTS = "implements"  # A implements B
    REFERENCES = "references"  # A references B
    CONTAINS = "contains"  # A contains B (file contains function)
    DEPENDS_ON = "depends_on"  # Generic dependency
    DECORATES = "decorates"  # A decorates B
    INSTANTIATES = "instantiates"  # A creates instance of B


class ChangeType(str, Enum):
    """Types of code changes."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class CodeChunk(BaseModel):
    """Represents a chunk of code for embedding and retrieval."""

    id: str = Field(..., description="Unique identifier (file_path:line_start:line_end)")
    file_path: str = Field(..., description="Relative path to the file")
    language: str = Field(..., description="Programming language")
    symbol_name: str | None = Field(None, description="Name of the symbol (function, class, etc.)")
    symbol_type: SymbolType = Field(..., description="Type of code symbol")
    line_start: int = Field(..., description="Starting line number (1-based)")
    line_end: int = Field(..., description="Ending line number (1-based)")
    content: str = Field(..., description="The actual code content")
    docstring: str | None = Field(None, description="Docstring or documentation")
    signature: str | None = Field(None, description="Function/method signature")
    parent_symbol: str | None = Field(None, description="Containing class/module name")
    content_hash: str = Field(..., description="Hash of the content for change detection")
    last_indexed: datetime = Field(default_factory=datetime.utcnow)

    def to_embedding_text(self) -> str:
        """Convert chunk to text for embedding."""
        parts = []
        if self.symbol_name:
            parts.append(f"{self.symbol_type.value}: {self.symbol_name}")
        if self.signature:
            parts.append(f"Signature: {self.signature}")
        if self.docstring:
            parts.append(f"Documentation: {self.docstring}")
        parts.append(f"Code:\n{self.content}")
        return "\n".join(parts)


class FileRecord(BaseModel):
    """Tracks an indexed file."""

    path: str = Field(..., description="Relative path to the file")
    absolute_path: str = Field(..., description="Absolute path to the file")
    language: str = Field(..., description="Programming language")
    content_hash: str = Field(..., description="Hash of file content")
    size_bytes: int = Field(..., description="File size in bytes")
    last_modified: datetime = Field(..., description="File modification time")
    last_indexed: datetime = Field(default_factory=datetime.utcnow)
    chunk_ids: list[str] = Field(default_factory=list, description="IDs of chunks from this file")
    symbols: list[str] = Field(default_factory=list, description="Symbol names defined in file")
    imports: list[str] = Field(default_factory=list, description="Import statements")


class Relationship(BaseModel):
    """An edge in the knowledge graph representing a relationship between code elements."""

    source_id: str = Field(..., description="Source symbol or file ID")
    target_id: str = Field(..., description="Target symbol or file ID")
    relation_type: RelationType = Field(..., description="Type of relationship")
    weight: float = Field(1.0, description="Importance/frequency weight")
    line_number: int | None = Field(None, description="Line where relationship is defined")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChangeRecord(BaseModel):
    """Records a detected change in the codebase."""

    id: str = Field(..., description="Unique change ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    commit_hash: str | None = Field(None, description="Git commit hash if available")
    author: str | None = Field(None, description="Author of the change")
    message: str | None = Field(None, description="Commit message if available")
    files_changed: list[str] = Field(default_factory=list)
    symbols_added: list[str] = Field(default_factory=list)
    symbols_modified: list[str] = Field(default_factory=list)
    symbols_removed: list[str] = Field(default_factory=list)
    change_type: ChangeType = Field(ChangeType.MODIFIED)
    impact_score: float = Field(0.0, description="Calculated impact score 0-1")
    explanation: str | None = Field(None, description="LLM-generated explanation")
    affected_files: list[str] = Field(default_factory=list, description="Downstream affected files")


class Decision(BaseModel):
    """An architectural decision record."""

    id: str = Field(..., description="Unique decision ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    title: str = Field(..., description="Short title for the decision")
    description: str = Field(..., description="What was decided")
    context: str = Field("", description="Context and background")
    rationale: str = Field(..., description="Why this decision was made")
    related_files: list[str] = Field(default_factory=list)
    related_symbols: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = Field("active", description="active, superseded, deprecated")


class Convention(BaseModel):
    """A detected or documented coding convention."""

    id: str = Field(..., description="Unique convention ID")
    category: str = Field(..., description="Category: naming, structure, patterns, etc.")
    description: str = Field(..., description="Description of the convention")
    examples: list[str] = Field(default_factory=list, description="Code examples")
    confidence: float = Field(1.0, description="Confidence score 0-1 (for detected conventions)")
    source: str = Field("manual", description="'detected' or 'manual'")
    related_files: list[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    """A node in the knowledge graph."""

    id: str = Field(..., description="Unique node ID")
    node_type: SymbolType = Field(..., description="Type of node")
    name: str = Field(..., description="Display name")
    file_path: str | None = Field(None, description="File containing this symbol")
    line_start: int | None = Field(None)
    line_end: int | None = Field(None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexStatus(BaseModel):
    """Status of the project index."""

    total_files: int = Field(0)
    total_chunks: int = Field(0)
    total_symbols: int = Field(0)
    total_relationships: int = Field(0)
    last_full_sync: datetime | None = Field(None)
    last_incremental_sync: datetime | None = Field(None)
    pending_files: list[str] = Field(default_factory=list)
    index_size_bytes: int = Field(0)


class SearchResult(BaseModel):
    """A search result from the memory store."""

    chunk: CodeChunk
    score: float = Field(..., description="Similarity score")
    highlights: list[str] = Field(default_factory=list, description="Highlighted matches")
    related_chunks: list[str] = Field(default_factory=list, description="Related chunk IDs")


class SymbolSummary(BaseModel):
    """Pre-computed summary and context for a code symbol.

    Generated at sync time to provide instant recall without re-analysis.
    This is the core of AgentNA's memory - understand once, remember forever.
    """

    id: str = Field(..., description="Symbol ID (matches CodeChunk.id)")
    symbol_name: str = Field(..., description="Name of the function/class/method")
    symbol_type: SymbolType = Field(..., description="Type of symbol")
    file_path: str = Field(..., description="File containing this symbol")
    line_start: int = Field(..., description="Starting line")
    line_end: int = Field(..., description="Ending line")

    # Pre-computed understanding
    summary: str = Field(..., description="What this symbol does (1-2 sentences)")
    purpose: str = Field("", description="Why this exists / business purpose")

    # Relationships (pre-computed from graph)
    callers: list[str] = Field(default_factory=list, description="Functions that call this")
    callees: list[str] = Field(default_factory=list, description="Functions this calls")
    dependencies: list[str] = Field(default_factory=list, description="Imports/dependencies")
    dependents: list[str] = Field(default_factory=list, description="What depends on this")

    # Impact analysis (pre-computed)
    impact_score: float = Field(0.0, description="How critical: 0-1 (1 = changes break many things)")
    impact_files: list[str] = Field(default_factory=list, description="Files affected if this changes")

    # Metadata
    signature: str | None = Field(None, description="Function/method signature")
    return_type: str | None = Field(None, description="Return type if known")
    parameters: list[str] = Field(default_factory=list, description="Parameter names")

    last_analyzed: datetime = Field(default_factory=datetime.utcnow)
    content_hash: str = Field(..., description="Hash to detect changes")
