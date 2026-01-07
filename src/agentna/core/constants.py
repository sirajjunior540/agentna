"""Constants and default values for AgentNA."""

from pathlib import Path

# Directory names
AGENTNA_DIR = ".agentna"
MEMORY_DIR = "memory"
CHROMA_DIR = "chroma"
HISTORY_DIR = "history"
CHANGES_DIR = "changes"
INDEX_DIR = "index"
CACHE_DIR = "cache"

# File names
CONFIG_FILE = "config.yaml"
GRAPH_FILE = "graph.json"
DECISIONS_FILE = "decisions.json"
CONVENTIONS_FILE = "conventions.json"
FILE_HASHES_FILE = "file_hashes.json"
LAST_SYNC_FILE = "last_sync.json"

# Global config
GLOBAL_CONFIG_DIR = Path.home() / ".agentna"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"

# Default ignore patterns (similar to .gitignore)
DEFAULT_IGNORE_PATTERNS = [
    # Version control
    ".git/",
    ".svn/",
    ".hg/",
    # Dependencies
    "node_modules/",
    ".venv/",
    "venv/",
    "env/",
    "__pycache__/",
    "*.pyc",
    ".eggs/",
    "*.egg-info/",
    # Build artifacts
    "dist/",
    "build/",
    "*.so",
    "*.dll",
    "*.dylib",
    # IDE
    ".idea/",
    ".vscode/",
    "*.swp",
    "*.swo",
    # OS files
    ".DS_Store",
    "Thumbs.db",
    # AgentNA internal
    ".agentna/",
    # Large files
    "*.min.js",
    "*.min.css",
    "*.map",
    # Data files
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    # Logs
    "*.log",
    "logs/",
]

# Default include patterns for indexing
DEFAULT_INCLUDE_PATTERNS = [
    "**/*.py",
    "**/*.js",
    "**/*.ts",
    "**/*.tsx",
    "**/*.jsx",
    "**/*.go",
    "**/*.rs",
    "**/*.java",
    "**/*.kt",
    "**/*.rb",
    "**/*.php",
    "**/*.c",
    "**/*.cpp",
    "**/*.h",
    "**/*.hpp",
    "**/*.cs",
    "**/*.swift",
    "**/*.md",
    "**/*.rst",
    "**/*.yaml",
    "**/*.yml",
    "**/*.json",
    "**/*.toml",
]

# File size limits
MAX_FILE_SIZE_KB = 500
MAX_CHUNK_SIZE_CHARS = 4000
MIN_CHUNK_SIZE_CHARS = 100

# Embedding settings
EMBEDDING_DIMENSION = 768  # nomic-embed-text
EMBEDDING_MODEL = "nomic-embed-text"

# LLM defaults
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"

# ChromaDB settings
CHROMA_COLLECTION_CODE = "code_chunks"
CHROMA_COLLECTION_DOCS = "documentation"
CHROMA_COLLECTION_DECISIONS = "decisions"

# Watcher settings
DEFAULT_DEBOUNCE_MS = 1000
DEFAULT_WATCH_RECURSIVE = True

# Graph settings
GRAPH_MAX_DEPTH = 10

# Language mappings
LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".md": "markdown",
    ".rst": "rst",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
}

# Code file extensions (source of truth - prioritized in search)
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
    ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift",
}

# Documentation file extensions (lower priority - may be outdated)
DOC_EXTENSIONS = {
    ".md", ".rst", ".txt", ".doc", ".docx", ".pdf",
}

# Config file extensions
CONFIG_EXTENSIONS = {
    ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf",
}

# Default boost factor for code files in search (1.0 = no boost)
CODE_BOOST_FACTOR = 1.5
DOC_PENALTY_FACTOR = 0.6
