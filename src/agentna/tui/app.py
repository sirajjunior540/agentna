"""Main TUI application for AgentNA."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane, Input, Button

from agentna.core.project import Project
from agentna.memory.hybrid_store import HybridStore
from agentna.tui.screens.chat import ChatScreen
from agentna.tui.screens.dashboard import DashboardScreen
from agentna.tui.screens.changes import ChangesScreen


class AgentNAApp(App):
    """Main TUI application."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        height: 100%;
    }

    TabbedContent {
        height: 100%;
    }

    TabPane {
        padding: 1;
    }

    #chat-input-row {
        height: auto;
        margin: 0 1 1 1;
        padding: 0;
    }

    #chat-input {
        width: 1fr;
        margin-right: 1;
    }

    #btn-chat-send {
        min-width: 10;
    }

    .status-bar {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("f1", "switch_tab('dashboard')", "Dashboard", show=True),
        Binding("f2", "switch_tab('chat')", "Chat", show=True),
        Binding("f3", "switch_tab('changes')", "Changes", show=True),
        Binding("ctrl+s", "sync", "Sync"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("escape", "unfocus", "Unfocus", show=False),
    ]

    TITLE = "AgentNA"

    def __init__(self, project_path: Path | None = None) -> None:
        super().__init__()
        self.project_path = project_path
        self._project: Project | None = None
        self._store: HybridStore | None = None

    @property
    def project(self) -> Project:
        """Get the current project."""
        if self._project is None:
            if self.project_path:
                self._project = Project(self.project_path)
            else:
                self._project = Project.find_project()
        return self._project

    @property
    def store(self) -> HybridStore:
        """Get the hybrid store."""
        if self._store is None:
            self._store = HybridStore(self.project.chroma_dir, self.project.graph_path)
        return self._store

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=True)

        with Container(id="main-container"):
            with TabbedContent(initial="dashboard"):
                with TabPane("Dashboard", id="dashboard"):
                    yield DashboardScreen(self.project, self.store)
                with TabPane("Chat", id="chat"):
                    yield ChatScreen(self.project, self.store)
                    with Horizontal(id="chat-input-row"):
                        yield Input(placeholder="Ask a question...", id="chat-input")
                        yield Button("Send", id="btn-chat-send", variant="success")
                with TabPane("Changes", id="changes"):
                    yield ChangesScreen(self.project, self.store)

        yield Footer()

    def on_mount(self) -> None:
        """Handle app mount."""
        self.title = f"AgentNA - {self.project.name}"
        self.sub_title = str(self.project.root)

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch to a specific tab."""
        tabbed_content = self.query_one(TabbedContent)
        tabbed_content.active = tab_id
        # Focus the chat input when switching to chat tab
        if tab_id == "chat":
            self.call_later(self._focus_chat_input)

    def _focus_chat_input(self) -> None:
        """Focus the chat input field."""
        try:
            from textual.widgets import Input
            chat_input = self.query_one("#chat-input", Input)
            chat_input.focus()
        except Exception:
            pass

    def action_unfocus(self) -> None:
        """Remove focus from current widget."""
        self.set_focus(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter in chat input."""
        if event.input.id == "chat-input":
            self._chat_submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-chat-send":
            self._chat_submit()

    def _chat_submit(self) -> None:
        """Submit chat query."""
        try:
            input_widget = self.query_one("#chat-input", Input)
            query = input_widget.value.strip()
            if not query:
                return

            input_widget.value = ""

            # Get chat screen and add user message
            chat_screen = self.query_one(ChatScreen)
            chat_screen.add_message("USER", query)

            self.notify("Searching...")
            results = self.store.search(query, n_results=5)

            if not results:
                chat_screen.add_message("ASSISTANT", "No results found. Try a different query.")
                return

            chat_screen.add_message("ASSISTANT", f"Found {len(results)} results:\n")

            for i, result in enumerate(results, 1):
                chunk = result.chunk
                # File and location
                chat_screen.add_message("RESULT", f"[bold yellow]{i}.[/] [cyan]{chunk.file_path}[/]:[magenta]{chunk.line_start}[/]")
                # Symbol name if present
                if chunk.symbol_name:
                    chat_screen.add_message("RESULT", f"   [bold]{chunk.symbol_name}[/] ({chunk.symbol_type.value if chunk.symbol_type else 'unknown'})")
                # Code preview
                preview = chunk.content[:150].replace('\n', ' ').strip()
                if len(chunk.content) > 150:
                    preview += "..."
                chat_screen.add_message("CODE", f"   {preview}")
                chat_screen.add_message("RESULT", "")

        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def action_sync(self) -> None:
        """Trigger a sync operation."""
        from agentna.indexing import run_sync

        self.notify("Starting sync...")
        try:
            stats = run_sync(self.project, full=False, quiet=True)
            self.notify(
                f"Synced: {stats.get('files_indexed', 0)} files, "
                f"{stats.get('total_chunks', 0)} chunks"
            )
            # Refresh dashboard
            self.refresh_all()
        except Exception as e:
            self.notify(f"Sync failed: {e}", severity="error")

    def action_refresh(self) -> None:
        """Refresh all screens."""
        self.refresh_all()

    def refresh_all(self) -> None:
        """Refresh all screen data."""
        # Refresh store
        self._store = None

        # Notify screens to refresh
        for screen in self.query(DashboardScreen):
            screen.refresh_data()


def run_tui(project_path: Path | None = None) -> None:
    """Run the TUI application."""
    app = AgentNAApp(project_path)
    app.run()
