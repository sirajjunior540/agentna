# AgentNA

**Local Code Agent with Memory and Change Tracking**

AgentNA is a powerful tool that provides intelligent code memory, semantic search, change tracking, and impact analysis for your development projects. It integrates with Claude CLI via MCP and offers a rich terminal user interface.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Commands](#cli-commands)
- [TUI (Terminal User Interface)](#tui-terminal-user-interface)
- [MCP Integration (Claude CLI)](#mcp-integration-claude-cli)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## Features

- **Project Isolation**: Each project has its own `.agentna/` directory with isolated memory and context
- **Hybrid Memory**: ChromaDB for semantic vector search + NetworkX for relationship/dependency tracking
- **Automatic Change Tracking**: File watcher + git hooks detect changes and reindex automatically
- **Impact Analysis**: Understand how code changes affect other parts of your codebase
- **Change Explanation**: LLM-powered explanations of what changed and why it matters
- **Multi-LLM Support**: Use Ollama for local/fast queries, Claude API as fallback for complex tasks
- **MCP Server**: Integrate directly with Claude CLI for AI-assisted development
- **Rich TUI**: Beautiful terminal interface for interactive exploration

## Installation

### From PyPI (when published)

```bash
pip install agentna
```

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/agentna.git
cd agentna

# Install in development mode
pip install -e ".[dev]"
```

### Requirements

- Python 3.10+
- Ollama (optional, for local LLM and embeddings)
- Claude API key (optional, for Claude LLM fallback)

### Setting up Ollama (Recommended)

AgentNA uses Ollama for local embeddings and LLM queries:

```bash
# Install Ollama (macOS)
brew install ollama

# Or download from https://ollama.ai

# Start Ollama service
ollama serve

# Pull recommended models
ollama pull nomic-embed-text    # For embeddings
ollama pull llama3.2            # For LLM queries (or any model you prefer)
```

### Setting up Claude API (Optional)

For Claude API fallback, set your API key:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

Or add to `.agentna/config.yaml` after initialization.

## Quick Start

### 1. Initialize a Project

Navigate to your project directory and initialize AgentNA:

```bash
cd /path/to/your/project
agent init
```

This creates a `.agentna/` directory with:
- `config.yaml` - Project configuration
- `memory/chroma/` - Vector embeddings database
- `memory/graph.json` - Knowledge graph (relationships)
- `index/file_hashes.json` - File tracking for incremental sync

### 2. Index Your Codebase

```bash
# Incremental sync (only changed files)
agent sync

# Full reindex (all files)
agent sync --full
```

### 3. Query Your Code

```bash
# Ask questions about your codebase
agent ask "How does the authentication system work?"
agent ask "What functions call the database?"
agent ask "Show me error handling patterns"
```

### 4. Explain Changes

```bash
# Explain recent git commits
agent explain recent

# Explain a specific commit
agent explain abc123

# Explain uncommitted changes
agent explain uncommitted
```

### 5. Launch the TUI

```bash
agent tui
```

### 6. Set Up Automatic Tracking

```bash
# Start file watcher (foreground)
agent watch

# Or install git hooks for automatic sync after commits
agent hooks install
```

## CLI Commands

### `agent init`

Initialize AgentNA in a project directory.

```bash
agent init [PATH] [--name NAME]

# Examples:
agent init                      # Initialize in current directory
agent init /path/to/project     # Initialize in specific directory
agent init --name "My Project"  # Set custom project name
```

### `agent status`

Show the status of the AgentNA index.

```bash
agent status [--path PATH] [--verbose]

# Examples:
agent status                    # Show basic status
agent status -v                 # Show detailed status with config
```

### `agent sync`

Sync/reindex the codebase.

```bash
agent sync [--path PATH] [--full]

# Examples:
agent sync                      # Incremental sync (changed files only)
agent sync --full               # Full reindex of all files
agent sync -f                   # Short form for full reindex
```

### `agent ask`

Ask a question about the codebase using semantic search and LLM.

```bash
agent ask "QUESTION" [--path PATH] [--limit LIMIT]

# Examples:
agent ask "How does user authentication work?"
agent ask "What classes inherit from BaseModel?"
agent ask "Show me database connection code" --limit 10
```

### `agent explain`

Explain changes in the codebase.

```bash
agent explain [TARGET] [--path PATH]

# TARGET can be:
#   recent      - Explain recent commits (default)
#   uncommitted - Explain uncommitted changes
#   <commit>    - Explain a specific commit hash
#   <file>      - Explain changes to a specific file

# Examples:
agent explain                   # Explain recent commits
agent explain recent            # Same as above
agent explain uncommitted       # Explain staged/unstaged changes
agent explain abc123f           # Explain specific commit
agent explain src/main.py       # Explain changes to a file
```

### `agent watch`

Start the file watcher daemon for automatic reindexing.

```bash
agent watch [--path PATH]

# The watcher runs in foreground. Press Ctrl+C to stop.
# It automatically reindexes when files change.
```

### `agent hooks`

Manage git hooks for automatic indexing.

```bash
agent hooks [ACTION] [--path PATH]

# ACTION can be:
#   status    - Show git hooks status (default)
#   install   - Install AgentNA git hooks
#   uninstall - Remove AgentNA git hooks

# Examples:
agent hooks status              # Check which hooks are installed
agent hooks install             # Install post-commit, post-merge hooks
agent hooks uninstall           # Remove AgentNA hooks
```

### `agent serve`

Run MCP server for Claude CLI integration.

```bash
agent serve [--path PATH]

# This starts the MCP server using stdio transport.
# Used by Claude CLI - not meant to be run manually.
```

### `agent tui`

Launch the Terminal User Interface.

```bash
agent tui [--path PATH]

# TUI Keyboard Shortcuts:
#   Ctrl+Q - Quit
#   F1     - Switch to Dashboard tab
#   F2     - Switch to Chat tab
#   F3     - Switch to Changes tab
#   Ctrl+S - Trigger sync
#   Ctrl+R - Refresh all panels
#   Escape - Unfocus input field
#   Tab    - Navigate between elements
```

### Global Options

All commands support:

```bash
--help          # Show help for command
--version, -v   # Show version (main command only)
```

## TUI (Terminal User Interface)

Launch the TUI with `agent tui`. It provides three main screens:

### Dashboard Tab (Press `d`)

- **Status Panel**: Project name, path, indexed files, chunks, symbols, relationships
- **Quick Actions**: Buttons for Sync Now and Full Reindex
- **Recent Files**: Table of recently indexed files with symbol counts

### Chat Tab (Press `c`)

- **Interactive Chat**: Ask questions about your codebase
- **Semantic Search**: Finds relevant code using vector embeddings
- **LLM Responses**: Get AI-powered explanations (when Ollama/Claude available)

### Changes Tab (Press `h`)

- **Recent Changes**: List of recent git commits and file changes
- **Change Details**: Detailed view of selected changes with diffs
- **Explain Button**: Generate LLM explanations for changes

## MCP Integration (Claude CLI)

AgentNA can act as an MCP (Model Context Protocol) server for Claude CLI, giving Claude direct access to your codebase.

### Setup

Add AgentNA to your Claude CLI MCP configuration (`~/.claude/mcp.json`):

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

### Available MCP Tools

Once configured, Claude CLI can use these tools:

| Tool | Description |
|------|-------------|
| `search_codebase` | Semantic search across indexed code |
| `get_symbol_info` | Get details about a function/class/variable |
| `analyze_impact` | Find what's affected by changes to files |
| `get_file_context` | Get full context for a file with related symbols |
| `get_dependencies` | Get dependency graph for a file or symbol |
| `sync_index` | Trigger reindexing of the codebase |
| `add_decision` | Record an architectural decision |
| `search_decisions` | Search recorded architectural decisions |

### Available MCP Resources

| Resource | Description |
|----------|-------------|
| `agentna://project/info` | Project configuration and metadata |
| `agentna://index/stats` | Index statistics (files, chunks, symbols) |

### Example Claude CLI Usage

After setup, you can ask Claude questions and it will use AgentNA:

```
> How does the authentication system work in this project?
(Claude uses search_codebase to find auth-related code)

> What would be affected if I change the User model?
(Claude uses analyze_impact to show dependencies)

> Record a decision: We chose PostgreSQL for the database because...
(Claude uses add_decision to store it)
```

## Configuration

Configuration is stored in `.agentna/config.yaml`:

```yaml
# Project settings
name: my-project
version: "1.0"

# LLM settings
llm:
  preferred_provider: ollama  # or "claude"
  ollama_model: llama3.2
  ollama_embed_model: nomic-embed-text
  ollama_base_url: http://localhost:11434
  claude_model: claude-sonnet-4-20250514
  # claude_api_key: set via ANTHROPIC_API_KEY env var

# Indexing settings
indexing:
  include_patterns:
    - "*.py"
    - "*.js"
    - "*.ts"
    - "*.jsx"
    - "*.tsx"
    - "*.java"
    - "*.go"
    - "*.rs"
    - "*.rb"
    - "*.php"
    - "*.c"
    - "*.cpp"
    - "*.h"
    - "*.md"
    - "*.txt"
    - "*.yaml"
    - "*.yml"
    - "*.json"
    - "*.toml"
  exclude_patterns:
    - ".*"
    - "__pycache__"
    - "node_modules"
    - "venv"
    - ".git"
    - "dist"
    - "build"
  max_file_size: 1048576  # 1MB

# Watcher settings
watcher:
  enabled: true
  debounce_seconds: 2.0
```

## How It Works

### Architecture

```
agentna/
├── core/           # Config, project discovery, constants
├── memory/         # ChromaDB embeddings + NetworkX knowledge graph
├── indexing/       # Code parsing (AST), semantic chunking
├── tracking/       # File watcher (watchdog), git hooks, change detection
├── analysis/       # Impact analyzer, LLM-powered change explainer
├── llm/            # Ollama + Claude providers with automatic routing
├── mcp/            # FastMCP server for Claude CLI integration
├── tui/            # Textual terminal UI (dashboard, chat, changes)
└── cli/            # Typer CLI commands
```

### Per-Project Storage (`.agentna/`)

```
.agentna/
├── config.yaml           # Project configuration
├── memory/
│   ├── chroma/           # Vector embeddings (ChromaDB)
│   └── graph.json        # Knowledge graph (NetworkX)
├── history/
│   └── changes/          # Change history records
└── index/
    └── file_hashes.json  # File tracking for incremental sync
```

### Indexing Process

1. **File Discovery**: Scans project using include/exclude patterns, respects `.gitignore`
2. **Parsing**: Uses Python AST for `.py` files, generic chunking for others
3. **Chunking**: Splits code into semantic chunks (functions, classes, methods)
4. **Embedding**: Generates vector embeddings using Ollama's nomic-embed-text
5. **Graph Building**: Extracts relationships (imports, calls, inheritance)
6. **Storage**: Stores in ChromaDB (vectors) and NetworkX (graph)

### Search Process

1. **Query Embedding**: Converts your question to a vector
2. **Vector Search**: Finds similar code chunks in ChromaDB
3. **Graph Expansion**: Optionally includes related symbols from knowledge graph
4. **LLM Enhancement**: Uses Ollama/Claude to generate natural language answers

## Troubleshooting

### "No AgentNA project found"

You need to initialize AgentNA in your project first:

```bash
cd /path/to/your/project
agent init
```

### "Ollama not available"

Install and start Ollama:

```bash
# Install
brew install ollama  # macOS
# or download from https://ollama.ai

# Start service
ollama serve

# Pull embedding model
ollama pull nomic-embed-text
```

### "No relevant code found"

Make sure to index your codebase first:

```bash
agent sync
```

### Index seems outdated

Force a full reindex:

```bash
agent sync --full
```

### TUI not displaying correctly

Ensure your terminal supports Unicode and has a modern terminal emulator (iTerm2, Alacritty, Windows Terminal, etc.)

### MCP server not connecting

1. Check the path in `mcp.json` is correct
2. Ensure AgentNA is installed and `agent serve` works
3. Restart Claude CLI after config changes

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/agentna.git
cd agentna

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .

# Format code
ruff format .
```

### Project Structure

Key files:
- `src/agentna/memory/hybrid_store.py` - Central memory interface
- `src/agentna/indexing/indexer.py` - Main indexing orchestrator
- `src/agentna/mcp/server.py` - MCP server for Claude CLI
- `src/agentna/core/project.py` - Project lifecycle management
- `src/agentna/tui/app.py` - Main Textual application

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=agentna

# Specific test file
pytest tests/test_indexer.py
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
