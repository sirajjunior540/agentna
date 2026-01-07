"""ChromaDB-based vector store for code embeddings."""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from agentna.core.constants import (
    CHROMA_COLLECTION_CODE,
    CHROMA_COLLECTION_DECISIONS,
    CHROMA_COLLECTION_DOCS,
)
from agentna.core.exceptions import MemoryError
from agentna.memory.models import CodeChunk, Decision, SearchResult


class EmbeddingStore:
    """Manages ChromaDB vector storage for code embeddings."""

    def __init__(self, persist_dir: Path) -> None:
        """
        Initialize the embedding store.

        Args:
            persist_dir: Directory for ChromaDB persistence
        """
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistence
        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Get or create collections
        self._code_collection = self._client.get_or_create_collection(
            name=CHROMA_COLLECTION_CODE,
            metadata={"description": "Code chunks from the project"},
        )
        self._docs_collection = self._client.get_or_create_collection(
            name=CHROMA_COLLECTION_DOCS,
            metadata={"description": "Documentation and comments"},
        )
        self._decisions_collection = self._client.get_or_create_collection(
            name=CHROMA_COLLECTION_DECISIONS,
            metadata={"description": "Architectural decisions"},
        )

    def add_chunks(
        self,
        chunks: list[CodeChunk],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        """
        Add code chunks to the store.

        Args:
            chunks: List of code chunks to add
            embeddings: Optional pre-computed embeddings (if None, ChromaDB will compute)
        """
        if not chunks:
            return

        ids = [chunk.id for chunk in chunks]
        documents = [chunk.to_embedding_text() for chunk in chunks]
        metadatas = [
            {
                "file_path": chunk.file_path,
                "language": chunk.language,
                "symbol_name": chunk.symbol_name or "",
                "symbol_type": chunk.symbol_type.value,
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
                "content_hash": chunk.content_hash,
                "parent_symbol": chunk.parent_symbol or "",
            }
            for chunk in chunks
        ]

        try:
            if embeddings:
                self._code_collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=embeddings,
                )
            else:
                self._code_collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )
        except Exception as e:
            raise MemoryError(f"Failed to add chunks: {e}") from e

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        """
        Delete chunks by their IDs.

        Args:
            chunk_ids: List of chunk IDs to delete
        """
        if not chunk_ids:
            return

        try:
            self._code_collection.delete(ids=chunk_ids)
        except Exception as e:
            raise MemoryError(f"Failed to delete chunks: {e}") from e

    def delete_by_file(self, file_path: str) -> None:
        """
        Delete all chunks from a specific file.

        Args:
            file_path: Relative path to the file
        """
        try:
            self._code_collection.delete(where={"file_path": file_path})
        except Exception as e:
            raise MemoryError(f"Failed to delete chunks for {file_path}: {e}") from e

    def search(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        n_results: int = 10,
        file_types: list[str] | None = None,
        file_path: str | None = None,
    ) -> list[SearchResult]:
        """
        Search for relevant code chunks.

        Args:
            query: Search query text
            query_embedding: Optional pre-computed query embedding
            n_results: Maximum number of results
            file_types: Optional list of languages to filter by
            file_path: Optional specific file to search in

        Returns:
            List of search results
        """
        where_filter: dict[str, Any] | None = None
        where_conditions = []

        if file_types:
            where_conditions.append({"language": {"$in": file_types}})
        if file_path:
            where_conditions.append({"file_path": file_path})

        if len(where_conditions) == 1:
            where_filter = where_conditions[0]
        elif len(where_conditions) > 1:
            where_filter = {"$and": where_conditions}

        try:
            if query_embedding:
                results = self._code_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"],
                )
            else:
                results = self._code_collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"],
                )
        except Exception as e:
            raise MemoryError(f"Failed to search: {e}") from e

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                document = results["documents"][0][i] if results["documents"] else ""
                distance = results["distances"][0][i] if results["distances"] else 0.0

                # Convert distance to similarity score (ChromaDB uses L2 distance)
                score = 1.0 / (1.0 + distance)

                chunk = CodeChunk(
                    id=chunk_id,
                    file_path=metadata.get("file_path", ""),
                    language=metadata.get("language", ""),
                    symbol_name=metadata.get("symbol_name") or None,
                    symbol_type=metadata.get("symbol_type", "file"),
                    line_start=metadata.get("line_start", 0),
                    line_end=metadata.get("line_end", 0),
                    content=document,
                    content_hash=metadata.get("content_hash", ""),
                    parent_symbol=metadata.get("parent_symbol") or None,
                )

                search_results.append(SearchResult(chunk=chunk, score=score))

        return search_results

    def get_chunk(self, chunk_id: str) -> CodeChunk | None:
        """
        Get a specific chunk by ID.

        Args:
            chunk_id: The chunk ID

        Returns:
            CodeChunk if found, None otherwise
        """
        try:
            results = self._code_collection.get(
                ids=[chunk_id],
                include=["documents", "metadatas"],
            )
        except Exception as e:
            raise MemoryError(f"Failed to get chunk: {e}") from e

        if not results["ids"]:
            return None

        metadata = results["metadatas"][0] if results["metadatas"] else {}
        document = results["documents"][0] if results["documents"] else ""

        return CodeChunk(
            id=chunk_id,
            file_path=metadata.get("file_path", ""),
            language=metadata.get("language", ""),
            symbol_name=metadata.get("symbol_name") or None,
            symbol_type=metadata.get("symbol_type", "file"),
            line_start=metadata.get("line_start", 0),
            line_end=metadata.get("line_end", 0),
            content=document,
            content_hash=metadata.get("content_hash", ""),
            parent_symbol=metadata.get("parent_symbol") or None,
        )

    def get_chunks_by_file(self, file_path: str) -> list[CodeChunk]:
        """
        Get all chunks from a specific file.

        Args:
            file_path: Relative path to the file

        Returns:
            List of chunks from the file
        """
        try:
            results = self._code_collection.get(
                where={"file_path": file_path},
                include=["documents", "metadatas"],
            )
        except Exception as e:
            raise MemoryError(f"Failed to get chunks: {e}") from e

        chunks = []
        if results["ids"]:
            for i, chunk_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                document = results["documents"][i] if results["documents"] else ""

                chunks.append(
                    CodeChunk(
                        id=chunk_id,
                        file_path=metadata.get("file_path", ""),
                        language=metadata.get("language", ""),
                        symbol_name=metadata.get("symbol_name") or None,
                        symbol_type=metadata.get("symbol_type", "file"),
                        line_start=metadata.get("line_start", 0),
                        line_end=metadata.get("line_end", 0),
                        content=document,
                        content_hash=metadata.get("content_hash", ""),
                        parent_symbol=metadata.get("parent_symbol") or None,
                    )
                )

        return chunks

    def add_decision(self, decision: Decision, embedding: list[float] | None = None) -> None:
        """
        Add an architectural decision.

        Args:
            decision: The decision to add
            embedding: Optional pre-computed embedding
        """
        document = f"{decision.title}\n\n{decision.description}\n\nRationale: {decision.rationale}"
        metadata = {
            "title": decision.title,
            "timestamp": decision.timestamp.isoformat(),
            "status": decision.status,
            "tags": ",".join(decision.tags),
        }

        try:
            if embedding:
                self._decisions_collection.upsert(
                    ids=[decision.id],
                    documents=[document],
                    metadatas=[metadata],
                    embeddings=[embedding],
                )
            else:
                self._decisions_collection.upsert(
                    ids=[decision.id],
                    documents=[document],
                    metadatas=[metadata],
                )
        except Exception as e:
            raise MemoryError(f"Failed to add decision: {e}") from e

    def search_decisions(
        self, query: str, n_results: int = 5
    ) -> list[tuple[Decision, float]]:
        """
        Search architectural decisions.

        Args:
            query: Search query
            n_results: Maximum number of results

        Returns:
            List of (decision, score) tuples
        """
        try:
            results = self._decisions_collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            raise MemoryError(f"Failed to search decisions: {e}") from e

        decisions = []
        if results["ids"] and results["ids"][0]:
            for i, decision_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                document = results["documents"][0][i] if results["documents"] else ""
                distance = results["distances"][0][i] if results["distances"] else 0.0

                score = 1.0 / (1.0 + distance)

                # Parse document back to decision
                parts = document.split("\n\n")
                title = parts[0] if parts else ""
                description = parts[1] if len(parts) > 1 else ""
                rationale = parts[2].replace("Rationale: ", "") if len(parts) > 2 else ""

                from datetime import datetime

                decision = Decision(
                    id=decision_id,
                    title=title,
                    description=description,
                    rationale=rationale,
                    timestamp=datetime.fromisoformat(metadata.get("timestamp", "")),
                    status=metadata.get("status", "active"),
                    tags=metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                )

                decisions.append((decision, score))

        return decisions

    def count_chunks(self) -> int:
        """Get total number of code chunks."""
        return self._code_collection.count()

    def count_decisions(self) -> int:
        """Get total number of decisions."""
        return self._decisions_collection.count()

    def clear_all(self) -> None:
        """Clear all data from all collections."""
        try:
            self._client.delete_collection(CHROMA_COLLECTION_CODE)
            self._client.delete_collection(CHROMA_COLLECTION_DOCS)
            self._client.delete_collection(CHROMA_COLLECTION_DECISIONS)

            # Recreate collections
            self._code_collection = self._client.create_collection(
                name=CHROMA_COLLECTION_CODE,
                metadata={"description": "Code chunks from the project"},
            )
            self._docs_collection = self._client.create_collection(
                name=CHROMA_COLLECTION_DOCS,
                metadata={"description": "Documentation and comments"},
            )
            self._decisions_collection = self._client.create_collection(
                name=CHROMA_COLLECTION_DECISIONS,
                metadata={"description": "Architectural decisions"},
            )
        except Exception as e:
            raise MemoryError(f"Failed to clear collections: {e}") from e
