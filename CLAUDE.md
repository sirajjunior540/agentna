# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentNA is a local code agent with memory and change tracking. It provides:

- **Hybrid memory**: ChromaDB for semantic search + NetworkX for relationship tracking
- **Change tracking**: File watcher + git hooks for automatic reindexing
- **MCP server**: Integration with Claude CLI
- **TUI**: Terminal user interface built with Textual

## Quick Reference

### Development Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run the CLI
agent --help

# Initialize a project
agent init

# Sync/index the codebase
agent sync        # incremental
agent sync -f     # full reindex

# Ask questions about codebase
agent ask "How does X work?"

# Explain changes
agent explain recent
agent explain <commit-hash>

# Start file watcher
agent watch

# Git hooks management
agent hooks status
agent hooks install
agent hooks uninstall

# Run MCP server for Claude CLI
agent serve

# Launch TUI
agent tui

# Run tests
pytest

# Run linting
ruff check .
ruff format .
```

## Architecture

```
src/agentna/
├── core/           # Config, project discovery, constants, exceptions
│   ├── project.py  # Project class - manages .agentna/ directory
│   ├── config.py   # Configuration models and loading
│   └── constants.py
│
├── memory/         # Storage layer
│   ├── hybrid_store.py    # Central interface combining embeddings + graph
│   ├── embeddings.py      # ChromaDB wrapper for vector storage
│   ├── knowledge_graph.py # NetworkX wrapper for relationships
│   └── models.py          # Pydantic data models
│
├── indexing/       # Code parsing and indexing
│   ├── indexer.py         # Main indexer orchestrator
│   ├── python_parser.py   # AST-based Python parser
│   ├── generic_parser.py  # Fallback parser for other languages
│   └── chunker.py         # Semantic code chunking
│
├── tracking/       # Change detection
│   ├── watcher.py         # Watchdog file system watcher
│   ├── git_tracker.py     # Git integration (GitPython)
│   └── hooks.py           # Git hooks installation
│
├── analysis/       # Code analysis
│   ├── impact_analyzer.py   # Graph-based impact analysis
│   └── change_explainer.py  # LLM-powered change explanations
│
├── llm/            # LLM providers
│   ├── base.py            # Base provider interface
│   ├── ollama_provider.py # Ollama local LLM
│   ├── claude_provider.py # Claude API
│   ├── router.py          # Routes between providers
│   └── prompts.py         # System prompts and formatters
│
├── mcp/            # MCP server for Claude CLI
│   └── server.py          # FastMCP server with tools/resources
│
├── tui/            # Terminal UI
│   ├── app.py             # Main Textual application
│   └── screens/           # Dashboard, Chat, Changes screens
│
└── cli/            # Command line interface
    └── main.py            # Typer CLI commands
```

## Key Components

### HybridStore (`memory/hybrid_store.py`)

Central memory interface combining:
- Vector search via ChromaDB (`EmbeddingStore`)
- Graph traversal via NetworkX (`KnowledgeGraph`)

Key methods:
- `index_chunks()` - Store code chunks with embeddings
- `search()` - Semantic search with optional graph expansion
- `get_symbol_info()` - Get full details about a symbol
- `analyze_impact()` - Find downstream affected code
- `add_decision()` - Record architectural decisions

### Indexer (`indexing/indexer.py`)

Orchestrates code parsing and storage:
- Discovers files using include/exclude patterns
- Parses Python files with AST, others with generic parser
- Extracts symbols (functions, classes, methods)
- Builds relationship graph (imports, calls, inheritance)
- Supports incremental and full indexing

### MCP Server (`mcp/server.py`)

FastMCP server exposing these tools to Claude CLI:
- `search_codebase` - Semantic code search
- `get_symbol_info` - Symbol details
- `analyze_impact` - Impact analysis
- `get_file_context` - File with related symbols
- `get_dependencies` - Dependency graph
- `sync_index` - Trigger reindex
- `add_decision` / `search_decisions` - Decision records

### Project (`core/project.py`)

Manages `.agentna/` directory lifecycle:
- Initialization and discovery
- Configuration loading/saving
- File iteration with gitignore support
- Index status tracking

### TUI (`tui/app.py`)

Textual-based terminal interface:
- Dashboard: Status, quick actions, recent files
- Chat: Interactive codebase queries
- Changes: Git history with explanations

## Data Models (`memory/models.py`)

Key models:
- `CodeChunk` - Indexed code segment with metadata
- `FileRecord` - Tracked file with hash and symbols
- `Relationship` - Graph edge (imports, calls, inherits)
- `ChangeRecord` - Detected change with impact
- `Decision` - Architectural decision record
- `SearchResult` - Search result with score and chunk

Enums:
- `SymbolType` - function, class, method, variable, module
- `RelationType` - imports, calls, inherits, uses, defines
- `ChangeType` - added, modified, deleted, renamed

## MCP Integration

To use AgentNA with Claude CLI, add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "agentna": {
      "command": "agent",
      "args": ["serve"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

## Per-Project Storage

```
.agentna/
├── config.yaml           # Project configuration
├── memory/
│   ├── chroma/           # Vector embeddings
│   └── graph.json        # Knowledge graph
├── history/
│   └── changes/          # Change records
└── index/
    └── file_hashes.json  # For incremental indexing
```

## Common Patterns

### Adding a new CLI command

1. Add command function in `cli/main.py`
2. Use `@app.command()` decorator
3. Use `Project.find_project()` to get current project
4. Use `HybridStore` for memory operations

### Adding a new MCP tool

1. Add tool function in `mcp/server.py`
2. Use `@mcp.tool()` decorator with description
3. Return dict or string result

### Adding a new TUI screen

1. Create screen class in `tui/screens/`
2. Inherit from `Container` or `Static`
3. Implement `compose()` and `refresh_data()`
4. Add to `TabbedContent` in `tui/app.py`

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=agentna

# Run specific test
pytest tests/test_indexer.py -v
```

## Debugging Tips

- Use `agent status -v` to see detailed project info
- Check `.agentna/memory/` for storage issues
- Use `agent sync --full` to force complete reindex
- For MCP issues, test with `agent serve` directly
