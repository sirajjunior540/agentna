"""MCP Server for Claude CLI integration."""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from agentna.core.project import Project
from agentna.memory.hybrid_store import HybridStore

# Create the MCP server
mcp = FastMCP(
    name="agentna",
    version="0.1.0",
    description="Local code agent with memory and change tracking",
)

# Global state for the current project
_project: Project | None = None
_store: HybridStore | None = None


def get_project() -> Project:
    """Get the current project."""
    global _project
    if _project is None:
        _project = Project.find_project()
    return _project


def get_store() -> HybridStore:
    """Get the hybrid store."""
    global _store, _project
    if _store is None:
        project = get_project()
        _store = HybridStore(project.chroma_dir, project.graph_path)
    return _store


@mcp.tool()
def search_codebase(
    query: str,
    file_types: list[str] | None = None,
    limit: int = 10,
) -> str:
    """
    Semantic search across the indexed codebase.

    Args:
        query: Natural language query or code pattern to search for
        file_types: Optional list of languages to filter (e.g., ["python", "javascript"])
        limit: Maximum number of results to return

    Returns:
        Relevant code chunks with file paths, line numbers, and context
    """
    store = get_store()
    results = store.search(
        query=query,
        n_results=limit,
        file_types=file_types,
        include_related=True,
    )

    if not results:
        return "No matching code found."

    output = []
    for i, result in enumerate(results, 1):
        chunk = result.chunk
        output.append(f"## Result {i} (score: {result.score:.2f})")
        output.append(f"**File:** `{chunk.file_path}`")
        output.append(f"**Lines:** {chunk.line_start}-{chunk.line_end}")
        if chunk.symbol_name:
            output.append(f"**Symbol:** {chunk.symbol_name} ({chunk.symbol_type.value})")
        if chunk.docstring:
            output.append(f"**Documentation:** {chunk.docstring[:200]}...")
        output.append(f"```{chunk.language}")
        output.append(chunk.content[:1000] + ("..." if len(chunk.content) > 1000 else ""))
        output.append("```")
        if result.related_chunks:
            output.append(f"**Related:** {', '.join(result.related_chunks[:3])}")
        output.append("")

    return "\n".join(output)


@mcp.tool()
def get_symbol_info(
    symbol_name: str,
    file_path: str | None = None,
) -> str:
    """
    Get detailed information about a code symbol (function, class, variable).

    Args:
        symbol_name: Name of the symbol to look up
        file_path: Optional file path to disambiguate if multiple symbols exist

    Returns:
        Symbol definition, docstring, relationships, and usage locations
    """
    store = get_store()
    info = store.get_symbol_info(symbol_name, file_path)

    if not info:
        return f"Symbol '{symbol_name}' not found in the index."

    output = []
    symbol = info["symbol"]
    output.append(f"# {symbol.name}")
    output.append(f"**Type:** {symbol.node_type.value}")
    output.append(f"**File:** `{symbol.file_path}`")
    if symbol.line_start:
        output.append(f"**Lines:** {symbol.line_start}-{symbol.line_end}")

    if info.get("signature"):
        output.append(f"\n**Signature:**\n```\n{info['signature']}\n```")

    if info.get("docstring"):
        output.append(f"\n**Documentation:**\n{info['docstring']}")

    if info.get("content"):
        output.append(f"\n**Code:**\n```\n{info['content'][:500]}{'...' if len(info['content']) > 500 else ''}\n```")

    # Relationships
    if info.get("imports"):
        imports = [r.target_id for r in info["imports"]]
        output.append(f"\n**Imports:** {', '.join(imports[:5])}")

    if info.get("calls"):
        calls = [r.target_id for r in info["calls"]]
        output.append(f"\n**Calls:** {', '.join(calls[:5])}")

    if info.get("called_by"):
        callers = [r.source_id for r in info["called_by"]]
        output.append(f"\n**Called by:** {', '.join(callers[:5])}")

    if info.get("inherits"):
        bases = [r.target_id for r in info["inherits"]]
        output.append(f"\n**Inherits from:** {', '.join(bases)}")

    return "\n".join(output)


@mcp.tool()
def analyze_impact(
    file_paths: list[str],
) -> str:
    """
    Analyze the potential impact of changes to specified files.

    Args:
        file_paths: List of file paths that have been or will be modified

    Returns:
        List of affected files, functions, and classes with impact severity
    """
    store = get_store()
    impact = store.analyze_impact(file_paths)

    output = []
    output.append("# Impact Analysis")
    output.append(f"**Changed files:** {', '.join(impact['changed_files'])}")
    output.append(f"**Impact score:** {impact['impact_score']:.2f}")
    output.append(f"**Severity:** {impact['severity']}")

    if impact["affected_files"]:
        output.append(f"\n## Affected Files ({len(impact['affected_files'])})")
        for f in impact["affected_files"][:10]:
            output.append(f"- `{f}`")
        if len(impact["affected_files"]) > 10:
            output.append(f"- ... and {len(impact['affected_files']) - 10} more")

    if impact["affected_symbols"]:
        output.append(f"\n## Affected Symbols ({len(impact['affected_symbols'])})")
        for s in impact["affected_symbols"][:10]:
            output.append(f"- {s}")
        if len(impact["affected_symbols"]) > 10:
            output.append(f"- ... and {len(impact['affected_symbols']) - 10} more")

    return "\n".join(output)


@mcp.tool()
def get_file_context(
    file_path: str,
    include_related: bool = True,
) -> str:
    """
    Get full context for a file including related files and documentation.

    Args:
        file_path: Path to the file
        include_related: Whether to include related files

    Returns:
        File content, docstrings, related files, and relevant conventions
    """
    store = get_store()
    context = store.get_file_context(file_path, include_related)

    output = []
    output.append(f"# File: {context['file_path']}")

    if context["symbols"]:
        output.append(f"\n## Symbols ({len(context['symbols'])})")
        for symbol in context["symbols"][:20]:
            output.append(f"- {symbol}")

    if context["chunks"]:
        output.append(f"\n## Content Preview")
        for chunk in context["chunks"][:2]:
            output.append(f"\n### {chunk.symbol_name or 'Main'}")
            if chunk.docstring:
                output.append(f"*{chunk.docstring[:200]}*")
            output.append(f"```{chunk.language}")
            output.append(chunk.content[:500])
            output.append("```")

    if context["related_files"]:
        output.append(f"\n## Related Files ({len(context['related_files'])})")
        for f in context["related_files"][:10]:
            output.append(f"- `{f}`")

    return "\n".join(output)


@mcp.tool()
def get_dependencies(
    file_path: str,
    direction: str = "both",
    depth: int = 2,
) -> str:
    """
    Get dependency information for a file.

    Args:
        file_path: The file to analyze
        direction: "incoming" (what depends on this), "outgoing" (what this depends on), or "both"
        depth: How many levels deep to traverse

    Returns:
        Dependency tree showing relationships
    """
    store = get_store()
    project = get_project()

    # Get file node
    nodes = store.graph.get_nodes_by_file(file_path)
    if not nodes:
        return f"File '{file_path}' not found in the index."

    output = []
    output.append(f"# Dependencies for: {file_path}")

    if direction in ("outgoing", "both"):
        output.append("\n## Dependencies (what this file uses)")
        for node in nodes:
            deps = store.graph.get_dependencies(node.id, max_depth=depth)
            if deps:
                for dep in deps[:15]:
                    dep_node = store.graph.get_node(dep)
                    if dep_node:
                        output.append(f"- {dep_node.name} ({dep_node.node_type.value})")

    if direction in ("incoming", "both"):
        output.append("\n## Dependents (what uses this file)")
        for node in nodes:
            dependents = store.graph.get_dependents(node.id, max_depth=depth)
            if dependents:
                for dep in dependents[:15]:
                    dep_node = store.graph.get_node(dep)
                    if dep_node:
                        output.append(f"- {dep_node.name} ({dep_node.node_type.value})")

    return "\n".join(output)


@mcp.tool()
def sync_index(
    full: bool = False,
) -> str:
    """
    Trigger a sync of the code index.

    Args:
        full: If True, perform a full reindex. Otherwise, incremental.

    Returns:
        Sync status and summary of changes
    """
    from agentna.indexing import run_sync

    project = get_project()
    stats = run_sync(project, full=full, quiet=True)

    output = []
    output.append("# Index Sync Complete")
    output.append(f"**Mode:** {'Full reindex' if full else 'Incremental'}")
    output.append(f"**Files indexed:** {stats.get('files_indexed', 0)}")
    output.append(f"**Code chunks:** {stats.get('total_chunks', 0)}")
    output.append(f"**Relationships:** {stats.get('total_relationships', 0)}")
    if "deleted_files" in stats:
        output.append(f"**Deleted files:** {stats['deleted_files']}")

    return "\n".join(output)


@mcp.tool()
def get_project_status() -> str:
    """
    Get the current status of the AgentNA index.

    Returns:
        Index statistics, last sync time, and project information
    """
    project = get_project()
    store = get_store()
    status = project.get_status()
    stats = store.get_statistics()

    output = []
    output.append("# AgentNA Project Status")
    output.append(f"**Project:** {project.name}")
    output.append(f"**Path:** {project.root}")
    output.append(f"\n## Index Statistics")
    output.append(f"- Files indexed: {status.total_files}")
    output.append(f"- Code chunks: {stats['total_chunks']}")
    output.append(f"- Symbols: {stats['total_nodes']}")
    output.append(f"- Relationships: {stats['total_relationships']}")
    output.append(f"- Decisions: {stats['total_decisions']}")
    output.append(f"- Index size: {status.index_size_bytes / 1024:.1f} KB")

    if status.last_full_sync:
        output.append(f"\n**Last full sync:** {status.last_full_sync.strftime('%Y-%m-%d %H:%M:%S')}")
    if status.last_incremental_sync:
        output.append(f"**Last incremental sync:** {status.last_incremental_sync.strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(output)


@mcp.tool()
def add_decision(
    title: str,
    description: str,
    rationale: str,
    related_files: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """
    Record an architectural decision for future reference.

    Args:
        title: Short title for the decision
        description: What was decided
        rationale: Why this decision was made
        related_files: Optional list of files this decision affects
        tags: Optional tags for categorization

    Returns:
        Confirmation with decision ID
    """
    import uuid
    from datetime import datetime

    from agentna.memory.models import Decision

    store = get_store()

    decision = Decision(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        title=title,
        description=description,
        rationale=rationale,
        related_files=related_files or [],
        tags=tags or [],
    )

    store.add_decision(decision)

    output = []
    output.append("# Decision Recorded")
    output.append(f"**ID:** {decision.id}")
    output.append(f"**Title:** {decision.title}")
    output.append(f"**Description:** {decision.description}")
    output.append(f"**Rationale:** {decision.rationale}")
    if decision.related_files:
        output.append(f"**Related files:** {', '.join(decision.related_files)}")
    if decision.tags:
        output.append(f"**Tags:** {', '.join(decision.tags)}")

    return "\n".join(output)


@mcp.tool()
def search_decisions(
    query: str,
    limit: int = 5,
) -> str:
    """
    Search architectural decisions.

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        Matching decisions with relevance scores
    """
    store = get_store()
    results = store.search_decisions(query, n_results=limit)

    if not results:
        return "No matching decisions found."

    output = []
    output.append("# Architectural Decisions")
    for decision, score in results:
        output.append(f"\n## {decision.title}")
        output.append(f"**Score:** {score:.2f}")
        output.append(f"**Date:** {decision.timestamp.strftime('%Y-%m-%d')}")
        output.append(f"**Description:** {decision.description}")
        output.append(f"**Rationale:** {decision.rationale}")
        if decision.tags:
            output.append(f"**Tags:** {', '.join(decision.tags)}")

    return "\n".join(output)


# Resources
@mcp.resource("agentna://project/info")
def get_project_info() -> str:
    """Get project metadata and configuration."""
    project = get_project()
    return json.dumps({
        "name": project.name,
        "path": str(project.root),
        "config": project.config.model_dump(),
    }, indent=2)


@mcp.resource("agentna://index/stats")
def get_index_stats() -> str:
    """Get index statistics."""
    project = get_project()
    status = project.get_status()
    store = get_store()
    stats = store.get_statistics()

    return json.dumps({
        "total_files": status.total_files,
        "total_chunks": stats["total_chunks"],
        "total_symbols": stats["total_nodes"],
        "total_relationships": stats["total_relationships"],
        "index_size_bytes": status.index_size_bytes,
        "last_full_sync": status.last_full_sync.isoformat() if status.last_full_sync else None,
        "last_incremental_sync": status.last_incremental_sync.isoformat() if status.last_incremental_sync else None,
    }, indent=2)


def run_server(project_path: Path | None = None) -> None:
    """Run the MCP server."""
    global _project, _store

    # Initialize project
    if project_path:
        _project = Project(project_path)
    else:
        _project = Project.find_project()

    _store = HybridStore(_project.chroma_dir, _project.graph_path)

    # Run the server
    mcp.run()
