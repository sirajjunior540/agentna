"""NetworkX-based knowledge graph for code relationships."""

import json
from pathlib import Path
from typing import Any, Iterator

import networkx as nx

from agentna.core.exceptions import MemoryError
from agentna.memory.models import GraphNode, Relationship, RelationType, SymbolType


class KnowledgeGraph:
    """Manages the code knowledge graph using NetworkX."""

    def __init__(self, graph_path: Path) -> None:
        """
        Initialize the knowledge graph.

        Args:
            graph_path: Path to the JSON file for persistence
        """
        self.graph_path = Path(graph_path)
        self._graph = nx.DiGraph()
        self._load()

    def _load(self) -> None:
        """Load graph from disk."""
        if not self.graph_path.exists():
            return

        try:
            with open(self.graph_path) as f:
                data = json.load(f)

            # Load nodes
            for node_data in data.get("nodes", []):
                self._graph.add_node(
                    node_data["id"],
                    **{k: v for k, v in node_data.items() if k != "id"},
                )

            # Load edges
            for edge_data in data.get("edges", []):
                self._graph.add_edge(
                    edge_data["source"],
                    edge_data["target"],
                    **{k: v for k, v in edge_data.items() if k not in ("source", "target")},
                )
        except Exception as e:
            raise MemoryError(f"Failed to load knowledge graph: {e}") from e

    def save(self) -> None:
        """Save graph to disk."""
        try:
            nodes = []
            for node_id, attrs in self._graph.nodes(data=True):
                nodes.append({"id": node_id, **attrs})

            edges = []
            for source, target, attrs in self._graph.edges(data=True):
                edges.append({"source": source, "target": target, **attrs})

            self.graph_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.graph_path, "w") as f:
                json.dump({"nodes": nodes, "edges": edges}, f, indent=2, default=str)
        except Exception as e:
            raise MemoryError(f"Failed to save knowledge graph: {e}") from e

    def add_node(self, node: GraphNode) -> None:
        """
        Add a node to the graph.

        Args:
            node: The node to add
        """
        self._graph.add_node(
            node.id,
            node_type=node.node_type.value,
            name=node.name,
            file_path=node.file_path,
            line_start=node.line_start,
            line_end=node.line_end,
            **node.metadata,
        )

    def add_relationship(self, relationship: Relationship) -> None:
        """
        Add a relationship (edge) to the graph.

        Args:
            relationship: The relationship to add
        """
        self._graph.add_edge(
            relationship.source_id,
            relationship.target_id,
            relation_type=relationship.relation_type.value,
            weight=relationship.weight,
            line_number=relationship.line_number,
            **relationship.metadata,
        )

    def remove_node(self, node_id: str) -> None:
        """
        Remove a node and all its edges.

        Args:
            node_id: ID of the node to remove
        """
        if node_id in self._graph:
            self._graph.remove_node(node_id)

    def remove_nodes_by_file(self, file_path: str) -> None:
        """
        Remove all nodes associated with a file.

        Args:
            file_path: Path to the file
        """
        nodes_to_remove = [
            node_id
            for node_id, attrs in self._graph.nodes(data=True)
            if attrs.get("file_path") == file_path
        ]
        for node_id in nodes_to_remove:
            self._graph.remove_node(node_id)

    def get_node(self, node_id: str) -> GraphNode | None:
        """
        Get a node by ID.

        Args:
            node_id: The node ID

        Returns:
            GraphNode if found, None otherwise
        """
        if node_id not in self._graph:
            return None

        attrs = self._graph.nodes[node_id]
        return GraphNode(
            id=node_id,
            node_type=SymbolType(attrs.get("node_type", "file")),
            name=attrs.get("name", ""),
            file_path=attrs.get("file_path"),
            line_start=attrs.get("line_start"),
            line_end=attrs.get("line_end"),
            metadata={
                k: v
                for k, v in attrs.items()
                if k not in ("node_type", "name", "file_path", "line_start", "line_end")
            },
        )

    def get_relationships(
        self,
        node_id: str,
        direction: str = "both",
        relation_types: list[RelationType] | None = None,
    ) -> list[Relationship]:
        """
        Get relationships for a node.

        Args:
            node_id: The node ID
            direction: "incoming", "outgoing", or "both"
            relation_types: Optional filter for relationship types

        Returns:
            List of relationships
        """
        relationships = []

        if direction in ("outgoing", "both"):
            for target in self._graph.successors(node_id):
                edge_data = self._graph.edges[node_id, target]
                rel_type = RelationType(edge_data.get("relation_type", "depends_on"))

                if relation_types and rel_type not in relation_types:
                    continue

                relationships.append(
                    Relationship(
                        source_id=node_id,
                        target_id=target,
                        relation_type=rel_type,
                        weight=edge_data.get("weight", 1.0),
                        line_number=edge_data.get("line_number"),
                        metadata={
                            k: v
                            for k, v in edge_data.items()
                            if k not in ("relation_type", "weight", "line_number")
                        },
                    )
                )

        if direction in ("incoming", "both"):
            for source in self._graph.predecessors(node_id):
                edge_data = self._graph.edges[source, node_id]
                rel_type = RelationType(edge_data.get("relation_type", "depends_on"))

                if relation_types and rel_type not in relation_types:
                    continue

                relationships.append(
                    Relationship(
                        source_id=source,
                        target_id=node_id,
                        relation_type=rel_type,
                        weight=edge_data.get("weight", 1.0),
                        line_number=edge_data.get("line_number"),
                        metadata={
                            k: v
                            for k, v in edge_data.items()
                            if k not in ("relation_type", "weight", "line_number")
                        },
                    )
                )

        return relationships

    def get_dependents(self, node_id: str, max_depth: int = 10) -> list[str]:
        """
        Get all nodes that depend on a given node (incoming relationships).

        Args:
            node_id: The node ID
            max_depth: Maximum traversal depth

        Returns:
            List of dependent node IDs
        """
        if node_id not in self._graph:
            return []

        dependents = set()
        visited = set()
        queue = [(node_id, 0)]

        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue

            visited.add(current)

            for predecessor in self._graph.predecessors(current):
                if predecessor not in visited:
                    dependents.add(predecessor)
                    queue.append((predecessor, depth + 1))

        return list(dependents)

    def get_dependencies(self, node_id: str, max_depth: int = 10) -> list[str]:
        """
        Get all nodes that a given node depends on (outgoing relationships).

        Args:
            node_id: The node ID
            max_depth: Maximum traversal depth

        Returns:
            List of dependency node IDs
        """
        if node_id not in self._graph:
            return []

        dependencies = set()
        visited = set()
        queue = [(node_id, 0)]

        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue

            visited.add(current)

            for successor in self._graph.successors(current):
                if successor not in visited:
                    dependencies.add(successor)
                    queue.append((successor, depth + 1))

        return list(dependencies)

    def find_path(self, source_id: str, target_id: str) -> list[str] | None:
        """
        Find the shortest path between two nodes.

        Args:
            source_id: Source node ID
            target_id: Target node ID

        Returns:
            List of node IDs forming the path, or None if no path exists
        """
        try:
            return nx.shortest_path(self._graph, source_id, target_id)
        except nx.NetworkXNoPath:
            return None
        except nx.NodeNotFound:
            return None

    def get_nodes_by_file(self, file_path: str) -> list[GraphNode]:
        """
        Get all nodes from a specific file.

        Args:
            file_path: Path to the file

        Returns:
            List of nodes
        """
        nodes = []
        for node_id, attrs in self._graph.nodes(data=True):
            if attrs.get("file_path") == file_path:
                nodes.append(
                    GraphNode(
                        id=node_id,
                        node_type=SymbolType(attrs.get("node_type", "file")),
                        name=attrs.get("name", ""),
                        file_path=attrs.get("file_path"),
                        line_start=attrs.get("line_start"),
                        line_end=attrs.get("line_end"),
                        metadata={
                            k: v
                            for k, v in attrs.items()
                            if k not in ("node_type", "name", "file_path", "line_start", "line_end")
                        },
                    )
                )
        return nodes

    def get_nodes_by_type(self, node_type: SymbolType) -> list[GraphNode]:
        """
        Get all nodes of a specific type.

        Args:
            node_type: Type of nodes to retrieve

        Returns:
            List of nodes
        """
        nodes = []
        for node_id, attrs in self._graph.nodes(data=True):
            if attrs.get("node_type") == node_type.value:
                nodes.append(
                    GraphNode(
                        id=node_id,
                        node_type=node_type,
                        name=attrs.get("name", ""),
                        file_path=attrs.get("file_path"),
                        line_start=attrs.get("line_start"),
                        line_end=attrs.get("line_end"),
                        metadata={
                            k: v
                            for k, v in attrs.items()
                            if k not in ("node_type", "name", "file_path", "line_start", "line_end")
                        },
                    )
                )
        return nodes

    def search_nodes(
        self,
        name_pattern: str | None = None,
        node_types: list[SymbolType] | None = None,
    ) -> list[GraphNode]:
        """
        Search for nodes by name pattern and/or type.

        Args:
            name_pattern: Substring to match in node names (case-insensitive)
            node_types: Optional filter for node types

        Returns:
            List of matching nodes
        """
        nodes = []
        for node_id, attrs in self._graph.nodes(data=True):
            name = attrs.get("name", "")
            node_type_str = attrs.get("node_type", "file")

            # Check name pattern
            if name_pattern and name_pattern.lower() not in name.lower():
                continue

            # Check node type
            if node_types:
                if node_type_str not in [t.value for t in node_types]:
                    continue

            nodes.append(
                GraphNode(
                    id=node_id,
                    node_type=SymbolType(node_type_str),
                    name=name,
                    file_path=attrs.get("file_path"),
                    line_start=attrs.get("line_start"),
                    line_end=attrs.get("line_end"),
                    metadata={
                        k: v
                        for k, v in attrs.items()
                        if k not in ("node_type", "name", "file_path", "line_start", "line_end")
                    },
                )
            )

        return nodes

    def get_impact_subgraph(
        self,
        node_ids: list[str],
        max_depth: int = 3,
    ) -> "KnowledgeGraph":
        """
        Create a subgraph showing impact of changes to given nodes.

        Args:
            node_ids: List of changed node IDs
            max_depth: Maximum depth to traverse

        Returns:
            New KnowledgeGraph containing only the impact subgraph
        """
        affected_nodes = set(node_ids)

        for node_id in node_ids:
            dependents = self.get_dependents(node_id, max_depth)
            affected_nodes.update(dependents)

        # Create subgraph
        subgraph = self._graph.subgraph(affected_nodes).copy()

        # Create new KnowledgeGraph instance with the subgraph
        # Save to a temp path for now
        import tempfile

        temp_path = Path(tempfile.mktemp(suffix=".json"))
        result = KnowledgeGraph(temp_path)
        result._graph = subgraph
        return result

    def node_count(self) -> int:
        """Get total number of nodes."""
        return self._graph.number_of_nodes()

    def edge_count(self) -> int:
        """Get total number of edges."""
        return self._graph.number_of_edges()

    def clear(self) -> None:
        """Clear all nodes and edges."""
        self._graph.clear()
        self.save()

    def iter_nodes(self) -> Iterator[GraphNode]:
        """Iterate over all nodes."""
        for node_id, attrs in self._graph.nodes(data=True):
            yield GraphNode(
                id=node_id,
                node_type=SymbolType(attrs.get("node_type", "file")),
                name=attrs.get("name", ""),
                file_path=attrs.get("file_path"),
                line_start=attrs.get("line_start"),
                line_end=attrs.get("line_end"),
                metadata={
                    k: v
                    for k, v in attrs.items()
                    if k not in ("node_type", "name", "file_path", "line_start", "line_end")
                },
            )

    def iter_relationships(self) -> Iterator[Relationship]:
        """Iterate over all relationships."""
        for source, target, attrs in self._graph.edges(data=True):
            yield Relationship(
                source_id=source,
                target_id=target,
                relation_type=RelationType(attrs.get("relation_type", "depends_on")),
                weight=attrs.get("weight", 1.0),
                line_number=attrs.get("line_number"),
                metadata={
                    k: v
                    for k, v in attrs.items()
                    if k not in ("relation_type", "weight", "line_number")
                },
            )
