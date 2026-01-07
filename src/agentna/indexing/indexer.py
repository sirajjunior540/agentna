"""Main indexer for code parsing and storage."""

from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.progress import Progress, SpinnerColumn, TextColumn

from agentna.core.project import Project
from agentna.indexing.parsers.base import BaseParser
from agentna.indexing.parsers.generic_parser import GenericParser, MarkdownParser
from agentna.indexing.parsers.python_parser import PythonParser
from agentna.memory.hybrid_store import HybridStore
from agentna.memory.models import CodeChunk, FileRecord, Relationship
from agentna.utils.hashing import hash_file


class Indexer:
    """Orchestrates code parsing and indexing."""

    def __init__(self, project: Project, store: HybridStore) -> None:
        """
        Initialize the indexer.

        Args:
            project: The project to index
            store: The hybrid memory store
        """
        self.project = project
        self.store = store

        # Initialize parsers
        self._parsers: list[BaseParser] = [
            PythonParser(),
            MarkdownParser(),
        ]
        self._generic_parser = GenericParser()

    def get_parser(self, file_path: Path) -> BaseParser:
        """Get the appropriate parser for a file."""
        for parser in self._parsers:
            if parser.can_parse(file_path):
                return parser
        return self._generic_parser

    def index_file(
        self,
        file_path: Path,
        force: bool = False,
    ) -> tuple[list[CodeChunk], list[Relationship]]:
        """
        Index a single file.

        Args:
            file_path: Absolute path to the file
            force: Force re-index even if hash hasn't changed

        Returns:
            Tuple of (chunks, relationships) created
        """
        # Get relative path
        rel_path = file_path.relative_to(self.project.root)

        # Check if file needs indexing
        if not force:
            stored_hashes = self.project.get_file_hashes()
            current_hash = hash_file(file_path)
            if stored_hashes.get(str(rel_path)) == current_hash:
                return [], []  # File hasn't changed

        # Read file content
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return [], []

        # Remove old data for this file
        self.store.remove_file(str(rel_path))

        # Get parser and parse
        parser = self.get_parser(file_path)
        chunks = parser.parse(rel_path, content)
        relationships = parser.extract_relationships(rel_path, content, chunks)

        # Store chunks and relationships
        self.store.index_chunks(chunks, relationships)

        # Update file hash
        stored_hashes = self.project.get_file_hashes()
        stored_hashes[str(rel_path)] = hash_file(file_path)
        self.project.save_file_hashes(stored_hashes)

        return chunks, relationships

    def index_files(
        self,
        file_paths: list[Path],
        force: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, int]:
        """
        Index multiple files.

        Args:
            file_paths: List of absolute file paths
            force: Force re-index
            progress_callback: Optional callback(file_path, current, total)

        Returns:
            Statistics dictionary
        """
        total_chunks = 0
        total_relationships = 0
        files_indexed = 0

        for i, file_path in enumerate(file_paths):
            if progress_callback:
                progress_callback(str(file_path), i + 1, len(file_paths))

            chunks, relationships = self.index_file(file_path, force=force)
            if chunks:
                files_indexed += 1
                total_chunks += len(chunks)
                total_relationships += len(relationships)

        return {
            "files_indexed": files_indexed,
            "total_chunks": total_chunks,
            "total_relationships": total_relationships,
        }

    def full_index(
        self,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, int]:
        """
        Perform a full index of the project.

        Args:
            progress_callback: Optional progress callback

        Returns:
            Statistics dictionary
        """
        # Clear existing data
        self.store.clear()
        self.project.save_file_hashes({})

        # Get all files
        files = list(self.project.iter_files())

        # Index all files
        stats = self.index_files(files, force=True, progress_callback=progress_callback)

        # Update sync time
        self.project.update_sync_time(full=True)

        # Save graph
        self.store.save()

        return stats

    def incremental_index(
        self,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, int]:
        """
        Perform incremental index (only changed files).

        Args:
            progress_callback: Optional progress callback

        Returns:
            Statistics dictionary
        """
        stored_hashes = self.project.get_file_hashes()
        files_to_index: list[Path] = []

        # Find changed and new files
        for file_path in self.project.iter_files():
            rel_path = str(file_path.relative_to(self.project.root))
            current_hash = hash_file(file_path)

            if rel_path not in stored_hashes or stored_hashes[rel_path] != current_hash:
                files_to_index.append(file_path)

        # Find deleted files
        current_files = {
            str(f.relative_to(self.project.root))
            for f in self.project.iter_files()
        }
        deleted_files = set(stored_hashes.keys()) - current_files

        # Remove deleted files from index
        for deleted_file in deleted_files:
            self.store.remove_file(deleted_file)
            del stored_hashes[deleted_file]

        self.project.save_file_hashes(stored_hashes)

        # Index changed files
        stats = self.index_files(files_to_index, force=True, progress_callback=progress_callback)
        stats["deleted_files"] = len(deleted_files)

        # Update sync time
        self.project.update_sync_time(full=False)

        # Save graph
        self.store.save()

        return stats

    def remove_file(self, file_path: Path | str) -> None:
        """
        Remove a file from the index.

        Args:
            file_path: Path to the file (absolute or relative)
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # Get relative path
        if file_path.is_absolute():
            try:
                rel_path = str(file_path.relative_to(self.project.root))
            except ValueError:
                return
        else:
            rel_path = str(file_path)

        # Remove from store
        self.store.remove_file(rel_path)

        # Remove from file hashes
        stored_hashes = self.project.get_file_hashes()
        if rel_path in stored_hashes:
            del stored_hashes[rel_path]
            self.project.save_file_hashes(stored_hashes)

        self.store.save()


def run_sync(project: Project, full: bool = False, quiet: bool = False) -> dict[str, int]:
    """
    Run sync operation with progress display.

    Args:
        project: The project to sync
        full: Whether to do a full reindex
        quiet: Suppress progress output

    Returns:
        Statistics dictionary
    """
    store = HybridStore(project.chroma_dir, project.graph_path)
    indexer = Indexer(project, store)

    if not quiet:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Indexing...", total=None)

            def callback(file_path: str, current: int, total: int) -> None:
                progress.update(
                    task,
                    description=f"[cyan]Indexing ({current}/{total}):[/cyan] {Path(file_path).name}",
                )

            if full:
                stats = indexer.full_index(progress_callback=callback)
            else:
                stats = indexer.incremental_index(progress_callback=callback)

        return stats
    else:
        if full:
            return indexer.full_index()
        else:
            return indexer.incremental_index()
