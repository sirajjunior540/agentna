"""Hybrid memory store combining embeddings and knowledge graph."""

from pathlib import Path
from typing import Any

from agentna.memory.embeddings import EmbeddingStore
from agentna.memory.knowledge_graph import KnowledgeGraph
from agentna.memory.models import (
    CodeChunk,
    Decision,
    GraphNode,
    Relationship,
    RelationType,
    SearchResult,
    SymbolType,
)


class HybridStore:
    """
    Unified memory interface combining vector search and graph traversal.

    This is the primary interface for all memory operations in AgentNA.
    """

    def __init__(self, chroma_dir: Path, graph_path: Path) -> None:
        """
        Initialize the hybrid store.

        Args:
            chroma_dir: Directory for ChromaDB storage
            graph_path: Path to knowledge graph JSON file
        """
        self.embeddings = EmbeddingStore(chroma_dir)
        self.graph = KnowledgeGraph(graph_path)

    def index_chunk(
        self,
        chunk: CodeChunk,
        relationships: list[Relationship] | None = None,
        embedding: list[float] | None = None,
    ) -> None:
        """
        Index a code chunk with optional relationships.

        Args:
            chunk: The code chunk to index
            relationships: Optional relationships to add to the graph
            embedding: Optional pre-computed embedding
        """
        # Add to vector store
        self.embeddings.add_chunks([chunk], [embedding] if embedding else None)

        # Add node to graph
        node = GraphNode(
            id=chunk.id,
            node_type=chunk.symbol_type,
            name=chunk.symbol_name or chunk.file_path,
            file_path=chunk.file_path,
            line_start=chunk.line_start,
            line_end=chunk.line_end,
        )
        self.graph.add_node(node)

        # Add relationships
        if relationships:
            for rel in relationships:
                self.graph.add_relationship(rel)

    def index_chunks(
        self,
        chunks: list[CodeChunk],
        relationships: list[Relationship] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> None:
        """
        Index multiple code chunks with optional relationships.

        Args:
            chunks: List of code chunks to index
            relationships: Optional relationships to add to the graph
            embeddings: Optional pre-computed embeddings
        """
        if not chunks:
            return

        # Add to vector store
        self.embeddings.add_chunks(chunks, embeddings)

        # Add nodes to graph
        for chunk in chunks:
            node = GraphNode(
                id=chunk.id,
                node_type=chunk.symbol_type,
                name=chunk.symbol_name or chunk.file_path,
                file_path=chunk.file_path,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
            )
            self.graph.add_node(node)

        # Add relationships
        if relationships:
            for rel in relationships:
                self.graph.add_relationship(rel)

        # Save graph
        self.graph.save()

    def remove_file(self, file_path: str) -> None:
        """
        Remove all data associated with a file.

        Args:
            file_path: Relative path to the file
        """
        self.embeddings.delete_by_file(file_path)
        self.graph.remove_nodes_by_file(file_path)
        self.graph.save()

    def search(
        self,
        query: str,
        n_results: int = 10,
        include_related: bool = True,
        file_types: list[str] | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[SearchResult]:
        """
        Search for relevant code with optional relationship context.

        Args:
            query: Search query
            n_results: Maximum number of results
            include_related: Whether to include related chunks
            file_types: Optional filter for languages
            query_embedding: Optional pre-computed query embedding

        Returns:
            List of search results with relationship context
        """
        # Get initial results from vector search
        results = self.embeddings.search(
            query=query,
            query_embedding=query_embedding,
            n_results=n_results,
            file_types=file_types,
        )

        if include_related:
            # Enrich results with related chunks
            for result in results:
                relationships = self.graph.get_relationships(result.chunk.id)
                related_ids = [
                    rel.target_id if rel.source_id == result.chunk.id else rel.source_id
                    for rel in relationships
                ]
                result.related_chunks = related_ids[:5]  # Limit related chunks

        return results

    def search_with_context(
        self,
        query: str,
        n_results: int = 5,
        context_depth: int = 2,
        query_embedding: list[float] | None = None,
    ) -> dict[str, Any]:
        """
        Search with full context including related files and dependencies.

        Args:
            query: Search query
            n_results: Maximum number of primary results
            context_depth: How deep to traverse relationships
            query_embedding: Optional pre-computed query embedding

        Returns:
            Dictionary with results, related files, and dependency paths
        """
        results = self.search(
            query=query,
            n_results=n_results,
            include_related=False,
            query_embedding=query_embedding,
        )

        # Collect all affected files and symbols
        affected_files: set[str] = set()
        affected_symbols: set[str] = set()

        for result in results:
            affected_files.add(result.chunk.file_path)

            # Get related nodes from graph
            dependents = self.graph.get_dependents(result.chunk.id, max_depth=context_depth)
            dependencies = self.graph.get_dependencies(result.chunk.id, max_depth=context_depth)

            for node_id in dependents + dependencies:
                node = self.graph.get_node(node_id)
                if node and node.file_path:
                    affected_files.add(node.file_path)
                    if node.name:
                        affected_symbols.add(node.name)

        return {
            "results": results,
            "affected_files": list(affected_files),
            "affected_symbols": list(affected_symbols),
            "total_results": len(results),
        }

    def get_symbol_info(
        self,
        symbol_name: str,
        file_path: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get comprehensive information about a code symbol.

        Args:
            symbol_name: Name of the symbol
            file_path: Optional file path to disambiguate

        Returns:
            Dictionary with symbol info, or None if not found
        """
        # Search in graph
        nodes = self.graph.search_nodes(name_pattern=symbol_name)

        if file_path:
            nodes = [n for n in nodes if n.file_path == file_path]

        if not nodes:
            return None

        node = nodes[0]  # Take first match

        # Get chunk content
        chunk = self.embeddings.get_chunk(node.id)

        # Get relationships
        relationships = self.graph.get_relationships(node.id)

        # Categorize relationships
        imports = [r for r in relationships if r.relation_type == RelationType.IMPORTS]
        calls = [r for r in relationships if r.relation_type == RelationType.CALLS]
        inherits = [r for r in relationships if r.relation_type == RelationType.INHERITS]
        callers = [
            r for r in relationships
            if r.relation_type == RelationType.CALLS and r.target_id == node.id
        ]

        return {
            "symbol": node,
            "content": chunk.content if chunk else None,
            "docstring": chunk.docstring if chunk else None,
            "signature": chunk.signature if chunk else None,
            "imports": imports,
            "calls": calls,
            "inherits": inherits,
            "called_by": callers,
            "file_path": node.file_path,
            "line_start": node.line_start,
            "line_end": node.line_end,
        }

    def get_file_context(
        self,
        file_path: str,
        include_related: bool = True,
    ) -> dict[str, Any]:
        """
        Get full context for a file.

        Args:
            file_path: Path to the file
            include_related: Whether to include related files

        Returns:
            Dictionary with file context
        """
        # Get all chunks from file
        chunks = self.embeddings.get_chunks_by_file(file_path)

        # Get all nodes from file
        nodes = self.graph.get_nodes_by_file(file_path)

        # Get relationships
        all_relationships: list[Relationship] = []
        related_files: set[str] = set()

        for node in nodes:
            relationships = self.graph.get_relationships(node.id)
            all_relationships.extend(relationships)

            if include_related:
                for rel in relationships:
                    other_id = rel.target_id if rel.source_id == node.id else rel.source_id
                    other_node = self.graph.get_node(other_id)
                    if other_node and other_node.file_path and other_node.file_path != file_path:
                        related_files.add(other_node.file_path)

        return {
            "file_path": file_path,
            "chunks": chunks,
            "symbols": [n.name for n in nodes if n.name],
            "relationships": all_relationships,
            "related_files": list(related_files),
        }

    def analyze_impact(
        self,
        file_paths: list[str],
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """
        Analyze the impact of changes to specified files.

        Args:
            file_paths: List of changed file paths
            max_depth: Maximum depth for dependency traversal

        Returns:
            Impact analysis results
        """
        changed_nodes: set[str] = set()
        affected_nodes: set[str] = set()
        affected_files: set[str] = set()

        for file_path in file_paths:
            nodes = self.graph.get_nodes_by_file(file_path)
            for node in nodes:
                changed_nodes.add(node.id)
                dependents = self.graph.get_dependents(node.id, max_depth)
                affected_nodes.update(dependents)

        # Get affected files
        for node_id in affected_nodes:
            node = self.graph.get_node(node_id)
            if node and node.file_path and node.file_path not in file_paths:
                affected_files.add(node.file_path)

        # Calculate impact score (simple heuristic)
        impact_score = min(1.0, len(affected_files) / 10.0)

        return {
            "changed_files": file_paths,
            "changed_symbols": list(changed_nodes),
            "affected_files": list(affected_files),
            "affected_symbols": list(affected_nodes - changed_nodes),
            "impact_score": impact_score,
            "severity": (
                "high" if impact_score > 0.7 else "medium" if impact_score > 0.3 else "low"
            ),
        }

    def add_decision(
        self,
        decision: Decision,
        embedding: list[float] | None = None,
    ) -> None:
        """
        Add an architectural decision.

        Args:
            decision: The decision to add
            embedding: Optional pre-computed embedding
        """
        self.embeddings.add_decision(decision, embedding)

    def search_decisions(
        self,
        query: str,
        n_results: int = 5,
    ) -> list[tuple[Decision, float]]:
        """
        Search architectural decisions.

        Args:
            query: Search query
            n_results: Maximum results

        Returns:
            List of (decision, score) tuples
        """
        return self.embeddings.search_decisions(query, n_results)

    def get_statistics(self) -> dict[str, Any]:
        """Get memory store statistics."""
        return {
            "total_chunks": self.embeddings.count_chunks(),
            "total_nodes": self.graph.node_count(),
            "total_relationships": self.graph.edge_count(),
            "total_decisions": self.embeddings.count_decisions(),
        }

    def save(self) -> None:
        """Save all data to disk."""
        self.graph.save()

    def clear(self) -> None:
        """Clear all data."""
        self.embeddings.clear_all()
        self.graph.clear()
