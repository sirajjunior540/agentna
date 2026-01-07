"""File watcher for automatic change detection."""

import asyncio
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from agentna.core.project import Project


class ChangeHandler(FileSystemEventHandler):
    """Handle file system events with debouncing."""

    def __init__(
        self,
        project: Project,
        debounce_ms: int = 1000,
        on_change: Callable[[list[Path]], None] | None = None,
    ) -> None:
        self.project = project
        self.debounce_ms = debounce_ms
        self.on_change = on_change
        self.pending_changes: dict[str, float] = defaultdict(float)
        self._last_process_time = 0.0

    def _should_process(self, path: Path) -> bool:
        """Check if a file should be processed."""
        # Skip if file should be ignored
        if self.project.should_ignore(path):
            return False

        # Skip if not in include patterns
        if not self.project.should_include(path):
            return False

        return True

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if self._should_process(path):
            self.pending_changes[str(path)] = time.time()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if self._should_process(path):
            self.pending_changes[str(path)] = time.time()

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        # Don't check should_include for deleted files
        if not self.project.should_ignore(path):
            self.pending_changes[str(path)] = time.time()

    def process_pending(self) -> list[Path]:
        """Process pending changes after debounce period."""
        now = time.time()
        to_process: list[Path] = []

        for path_str, change_time in list(self.pending_changes.items()):
            if now - change_time >= self.debounce_ms / 1000:
                to_process.append(Path(path_str))
                del self.pending_changes[path_str]

        if to_process and self.on_change:
            self.on_change(to_process)

        return to_process


class FileWatcher:
    """Watch project directory for file changes."""

    def __init__(
        self,
        project: Project,
        on_change: Callable[[list[Path]], None] | None = None,
        debounce_ms: int | None = None,
    ) -> None:
        """
        Initialize the file watcher.

        Args:
            project: The project to watch
            on_change: Callback when files change
            debounce_ms: Debounce period in milliseconds
        """
        self.project = project
        self.debounce_ms = debounce_ms or project.config.watcher.debounce_ms
        self.handler = ChangeHandler(
            project=project,
            debounce_ms=self.debounce_ms,
            on_change=on_change,
        )
        self.observer = Observer()
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Start watching for file changes (blocking)."""
        self.observer.schedule(
            self.handler,
            str(self.project.root),
            recursive=self.project.config.watcher.recursive,
        )
        self.observer.start()
        self._running = True

        try:
            while self._running:
                self.handler.process_pending()
                time.sleep(0.5)  # Check for pending changes every 500ms
        except KeyboardInterrupt:
            self.stop()

    async def start_async(self) -> None:
        """Start watching for file changes (async)."""
        self.observer.schedule(
            self.handler,
            str(self.project.root),
            recursive=self.project.config.watcher.recursive,
        )
        self.observer.start()
        self._running = True

        try:
            while self._running:
                self.handler.process_pending()
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            self.stop()

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        self.observer.stop()
        self.observer.join(timeout=5)

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running


def create_watcher_callback(project: Project) -> Callable[[list[Path]], None]:
    """Create a callback that indexes changed files."""
    from agentna.indexing.indexer import Indexer
    from agentna.memory.hybrid_store import HybridStore

    store = HybridStore(project.chroma_dir, project.graph_path)
    indexer = Indexer(project, store)

    def callback(changed_files: list[Path]) -> None:
        """Index changed files."""
        from rich.console import Console

        console = Console()

        for file_path in changed_files:
            if file_path.exists():
                console.print(f"[cyan]Indexing:[/cyan] {file_path.name}")
                indexer.index_file(file_path, force=True)
            else:
                console.print(f"[yellow]Removing:[/yellow] {file_path.name}")
                indexer.remove_file(file_path)

        store.save()

    return callback
