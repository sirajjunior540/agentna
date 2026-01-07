"""Project management for AgentNA."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterator

import pathspec

from agentna.core.config import GlobalConfig, ProjectConfig
from agentna.core.constants import (
    AGENTNA_DIR,
    CACHE_DIR,
    CHANGES_DIR,
    CHROMA_DIR,
    CONFIG_FILE,
    CONVENTIONS_FILE,
    DECISIONS_FILE,
    FILE_HASHES_FILE,
    GRAPH_FILE,
    HISTORY_DIR,
    INDEX_DIR,
    LAST_SYNC_FILE,
    MEMORY_DIR,
)
from agentna.core.exceptions import ProjectNotFoundError
from agentna.memory.models import IndexStatus


class Project:
    """Represents an AgentNA-managed project."""

    def __init__(self, path: Path | str, create: bool = False) -> None:
        """
        Initialize a project.

        Args:
            path: Path to the project root directory
            create: If True, create .agentna directory if it doesn't exist
        """
        self.root = Path(path).resolve()
        self.agentna_dir = self.root / AGENTNA_DIR

        if create:
            self._create_structure()
        elif not self.agentna_dir.exists():
            raise ProjectNotFoundError(str(self.root))

        self._config: ProjectConfig | None = None
        self._ignore_spec: pathspec.PathSpec | None = None

    @property
    def name(self) -> str:
        """Get project name from config or directory name."""
        if self.config.name:
            return self.config.name
        return self.root.name

    @property
    def config(self) -> ProjectConfig:
        """Get project configuration (lazy loaded)."""
        if self._config is None:
            self._config = ProjectConfig.load(self.config_path)
        return self._config

    @property
    def config_path(self) -> Path:
        """Path to project config file."""
        return self.agentna_dir / CONFIG_FILE

    @property
    def memory_dir(self) -> Path:
        """Path to memory directory."""
        return self.agentna_dir / MEMORY_DIR

    @property
    def chroma_dir(self) -> Path:
        """Path to ChromaDB storage."""
        return self.memory_dir / CHROMA_DIR

    @property
    def graph_path(self) -> Path:
        """Path to knowledge graph file."""
        return self.memory_dir / GRAPH_FILE

    @property
    def decisions_path(self) -> Path:
        """Path to decisions file."""
        return self.memory_dir / DECISIONS_FILE

    @property
    def conventions_path(self) -> Path:
        """Path to conventions file."""
        return self.memory_dir / CONVENTIONS_FILE

    @property
    def summaries_path(self) -> Path:
        """Path to pre-computed symbol summaries."""
        return self.memory_dir / "summaries.json"

    @property
    def history_dir(self) -> Path:
        """Path to change history directory."""
        return self.agentna_dir / HISTORY_DIR

    @property
    def changes_dir(self) -> Path:
        """Path to individual change records."""
        return self.history_dir / CHANGES_DIR

    @property
    def index_dir(self) -> Path:
        """Path to index metadata."""
        return self.agentna_dir / INDEX_DIR

    @property
    def file_hashes_path(self) -> Path:
        """Path to file hashes for incremental indexing."""
        return self.index_dir / FILE_HASHES_FILE

    @property
    def last_sync_path(self) -> Path:
        """Path to last sync metadata."""
        return self.index_dir / LAST_SYNC_FILE

    @property
    def cache_dir(self) -> Path:
        """Path to cache directory."""
        return self.agentna_dir / CACHE_DIR

    def _create_structure(self) -> None:
        """Create the .agentna directory structure."""
        directories = [
            self.agentna_dir,
            self.memory_dir,
            self.chroma_dir,
            self.history_dir,
            self.changes_dir,
            self.index_dir,
            self.cache_dir,
        ]
        for d in directories:
            d.mkdir(parents=True, exist_ok=True)

        # Create default config if not exists
        if not self.config_path.exists():
            config = ProjectConfig(name=self.root.name)
            config.save(self.config_path)

        # Initialize empty JSON files
        self._init_json_file(self.graph_path, {"nodes": [], "edges": []})
        self._init_json_file(self.decisions_path, [])
        self._init_json_file(self.conventions_path, [])
        self._init_json_file(self.file_hashes_path, {})
        self._init_json_file(
            self.last_sync_path,
            {"last_full_sync": None, "last_incremental_sync": None},
        )

    def _init_json_file(self, path: Path, default: dict | list) -> None:
        """Initialize a JSON file if it doesn't exist."""
        if not path.exists():
            with open(path, "w") as f:
                json.dump(default, f, indent=2)

    def reload_config(self) -> None:
        """Reload configuration from disk."""
        self._config = ProjectConfig.load(self.config_path)

    def save_config(self) -> None:
        """Save current configuration to disk."""
        self.config.save(self.config_path)

    def _build_ignore_spec(self) -> pathspec.PathSpec:
        """Build pathspec for file filtering."""
        patterns = list(self.config.indexing.exclude_patterns)

        # Add patterns from .gitignore if it exists
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            with open(gitignore) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)

        # Add patterns from .agentnaignore if it exists
        agentnaignore = self.root / ".agentnaignore"
        if agentnaignore.exists():
            with open(agentnaignore) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)

        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def should_ignore(self, path: Path | str) -> bool:
        """Check if a file should be ignored based on patterns."""
        if self._ignore_spec is None:
            self._ignore_spec = self._build_ignore_spec()

        path = Path(path)
        if path.is_absolute():
            try:
                rel_path = path.relative_to(self.root)
            except ValueError:
                return True  # Path is outside project
        else:
            rel_path = path

        return self._ignore_spec.match_file(str(rel_path))

    def should_include(self, path: Path | str) -> bool:
        """Check if a file should be included based on include patterns."""
        path = Path(path)
        if path.is_absolute():
            try:
                rel_path = path.relative_to(self.root)
            except ValueError:
                return False
        else:
            rel_path = path

        include_spec = pathspec.PathSpec.from_lines(
            "gitwildmatch", self.config.indexing.include_patterns
        )
        return include_spec.match_file(str(rel_path))

    def iter_files(self) -> Iterator[Path]:
        """Iterate over all files that should be indexed."""
        for root, dirs, files in os.walk(self.root):
            root_path = Path(root)

            # Filter directories in-place to skip ignored ones
            dirs[:] = [
                d for d in dirs if not self.should_ignore(root_path / d) and not d.startswith(".")
            ]

            for f in files:
                file_path = root_path / f
                rel_path = file_path.relative_to(self.root)

                # Skip if ignored
                if self.should_ignore(rel_path):
                    continue

                # Skip if not in include patterns
                if not self.should_include(rel_path):
                    continue

                # Skip if too large
                try:
                    size_kb = file_path.stat().st_size / 1024
                    if size_kb > self.config.indexing.max_file_size_kb:
                        continue
                except OSError:
                    continue

                yield file_path

    def get_file_hashes(self) -> dict[str, str]:
        """Load stored file hashes for incremental indexing."""
        if self.file_hashes_path.exists():
            with open(self.file_hashes_path) as f:
                return json.load(f)
        return {}

    def save_file_hashes(self, hashes: dict[str, str]) -> None:
        """Save file hashes for incremental indexing."""
        with open(self.file_hashes_path, "w") as f:
            json.dump(hashes, f, indent=2)

    def update_sync_time(self, full: bool = False) -> None:
        """Update the last sync timestamp."""
        with open(self.last_sync_path) as f:
            data = json.load(f)

        now = datetime.utcnow().isoformat()
        if full:
            data["last_full_sync"] = now
        data["last_incremental_sync"] = now

        with open(self.last_sync_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_status(self) -> IndexStatus:
        """Get the current index status."""
        # Load sync times
        sync_data = {}
        if self.last_sync_path.exists():
            with open(self.last_sync_path) as f:
                sync_data = json.load(f)

        # Count files
        file_hashes = self.get_file_hashes()

        # Calculate index size
        index_size = 0
        if self.chroma_dir.exists():
            for f in self.chroma_dir.rglob("*"):
                if f.is_file():
                    index_size += f.stat().st_size

        # Load graph stats
        graph_data = {"nodes": [], "edges": []}
        if self.graph_path.exists():
            with open(self.graph_path) as f:
                graph_data = json.load(f)

        return IndexStatus(
            total_files=len(file_hashes),
            total_chunks=0,  # Will be populated from ChromaDB
            total_symbols=len(graph_data.get("nodes", [])),
            total_relationships=len(graph_data.get("edges", [])),
            last_full_sync=(
                datetime.fromisoformat(sync_data["last_full_sync"])
                if sync_data.get("last_full_sync")
                else None
            ),
            last_incremental_sync=(
                datetime.fromisoformat(sync_data["last_incremental_sync"])
                if sync_data.get("last_incremental_sync")
                else None
            ),
            index_size_bytes=index_size,
        )

    @classmethod
    def find_project(cls, start_path: Path | str | None = None) -> "Project":
        """
        Find a project by walking up the directory tree.

        Args:
            start_path: Starting directory (defaults to current directory)

        Returns:
            Project instance

        Raises:
            ProjectNotFoundError: If no project is found
        """
        if start_path is None:
            start_path = Path.cwd()
        else:
            start_path = Path(start_path).resolve()

        current = start_path
        while current != current.parent:
            if (current / AGENTNA_DIR).exists():
                return cls(current)
            current = current.parent

        raise ProjectNotFoundError(str(start_path))

    @classmethod
    def init(cls, path: Path | str | None = None) -> "Project":
        """
        Initialize a new project.

        Args:
            path: Project root directory (defaults to current directory)

        Returns:
            Newly created Project instance
        """
        if path is None:
            path = Path.cwd()
        else:
            path = Path(path).resolve()

        project = cls(path, create=True)

        # Register in global config
        global_config = GlobalConfig.load()
        global_config.register_project(project.name, str(project.root))

        return project
