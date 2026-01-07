"""Dashboard screen for AgentNA TUI."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Static, DataTable

from agentna.core.project import Project
from agentna.memory.hybrid_store import HybridStore


class StatusPanel(Static):
    """Panel showing project status."""

    DEFAULT_CSS = """
    StatusPanel {
        border: solid $primary;
        padding: 1;
        margin: 1;
        height: auto;
    }

    StatusPanel .title {
        text-style: bold;
        color: $secondary;
    }

    StatusPanel .value {
        color: $text;
    }
    """

    def __init__(self, project: Project, store: HybridStore) -> None:
        super().__init__()
        self.project = project
        self.store = store

    def compose(self) -> ComposeResult:
        yield Static("Project Status", classes="title")
        yield Static(id="status-content")

    def on_mount(self) -> None:
        """Load status on mount."""
        self.refresh_data()

    def refresh_data(self) -> None:
        """Refresh status data."""
        status = self.project.get_status()
        stats = self.store.get_statistics()

        content = self.query_one("#status-content", Static)
        content.update(
            f"[cyan]Project:[/cyan] {self.project.name}\n"
            f"[cyan]Path:[/cyan] {self.project.root}\n\n"
            f"[green]Files:[/green] {status.total_files}\n"
            f"[green]Chunks:[/green] {stats['total_chunks']}\n"
            f"[green]Symbols:[/green] {stats['total_nodes']}\n"
            f"[green]Relationships:[/green] {stats['total_relationships']}\n"
            f"[green]Decisions:[/green] {stats['total_decisions']}\n\n"
            f"[dim]Index Size:[/dim] {status.index_size_bytes / 1024:.1f} KB\n"
            f"[dim]Last Sync:[/dim] {status.last_incremental_sync.strftime('%Y-%m-%d %H:%M') if status.last_incremental_sync else 'Never'}"
        )


class QuickActionsPanel(Static):
    """Panel with quick action buttons."""

    DEFAULT_CSS = """
    QuickActionsPanel {
        border: solid $primary;
        padding: 1;
        margin: 1;
        height: auto;
    }

    QuickActionsPanel .title {
        text-style: bold;
        color: $secondary;
        margin-bottom: 1;
    }

    QuickActionsPanel Button {
        margin: 0 1 1 0;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Quick Actions", classes="title")
        yield Button("Sync Now", id="btn-sync", variant="primary")
        yield Button("Full Reindex", id="btn-full-sync", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-sync":
            self.app.action_sync()
        elif event.button.id == "btn-full-sync":
            self._full_sync()

    def _full_sync(self) -> None:
        """Perform full sync."""
        from agentna.indexing import run_sync

        self.app.notify("Starting full reindex...")
        try:
            stats = run_sync(self.app.project, full=True, quiet=True)
            self.app.notify(f"Full sync complete: {stats.get('files_indexed', 0)} files")
            self.app.refresh_all()
        except Exception as e:
            self.app.notify(f"Sync failed: {e}", severity="error")


class RecentFilesPanel(Static):
    """Panel showing recently indexed files."""

    DEFAULT_CSS = """
    RecentFilesPanel {
        border: solid $primary;
        padding: 1;
        margin: 1;
        height: 100%;
    }

    RecentFilesPanel .title {
        text-style: bold;
        color: $secondary;
        margin-bottom: 1;
    }

    RecentFilesPanel DataTable {
        height: 100%;
    }
    """

    def __init__(self, project: Project, store: HybridStore) -> None:
        super().__init__()
        self.project = project
        self.store = store

    def compose(self) -> ComposeResult:
        yield Static("Recent Files", classes="title")
        yield DataTable(id="files-table")

    def on_mount(self) -> None:
        """Set up table on mount."""
        table = self.query_one("#files-table", DataTable)
        table.add_columns("File", "Symbols", "Language")
        self.refresh_data()

    def refresh_data(self) -> None:
        """Refresh file list."""
        table = self.query_one("#files-table", DataTable)
        table.clear()

        # Get files from store
        file_hashes = self.project.get_file_hashes()
        files = list(file_hashes.keys())[:20]  # Show up to 20 files

        for file_path in files:
            chunks = self.store.embeddings.get_chunks_by_file(file_path)
            symbols = [c.symbol_name for c in chunks if c.symbol_name]
            language = chunks[0].language if chunks else "unknown"
            table.add_row(
                file_path[:40] + "..." if len(file_path) > 40 else file_path,
                str(len(symbols)),
                language,
            )


class DashboardScreen(Container):
    """Main dashboard screen."""

    DEFAULT_CSS = """
    DashboardScreen {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 2fr;
        grid-rows: auto 1fr;
    }

    DashboardScreen > StatusPanel {
        row-span: 1;
    }

    DashboardScreen > QuickActionsPanel {
        row-span: 1;
    }

    DashboardScreen > RecentFilesPanel {
        column-span: 2;
    }
    """

    def __init__(self, project: Project, store: HybridStore) -> None:
        super().__init__()
        self.project = project
        self.store = store

    def compose(self) -> ComposeResult:
        yield StatusPanel(self.project, self.store)
        yield QuickActionsPanel()
        yield RecentFilesPanel(self.project, self.store)

    def refresh_data(self) -> None:
        """Refresh all panels."""
        for panel in self.query(StatusPanel):
            panel.refresh_data()
        for panel in self.query(RecentFilesPanel):
            panel.refresh_data()
