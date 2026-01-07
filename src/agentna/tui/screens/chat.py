"""Chat screen for AgentNA TUI."""

from textual.widgets import Static

from agentna.core.project import Project
from agentna.memory.hybrid_store import HybridStore


class ChatScreen(Static):
    """Chat screen - displays chat history and results."""

    DEFAULT_CSS = """
    ChatScreen {
        height: 1fr;
        border: solid $primary;
        margin: 1;
        padding: 1;
        overflow-y: auto;
    }
    """

    def __init__(self, project: Project, store: HybridStore) -> None:
        super().__init__()
        self.project = project
        self.store = store
        self.messages: list[str] = []

    def on_mount(self) -> None:
        self.add_message("ASSISTANT", f"Welcome! Ask questions about [bold]{self.project.name}[/]")
        self.add_message("ASSISTANT", "Type below and press Enter to search.")

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat."""
        if role == "USER":
            self.messages.append(f"[bold cyan]> {content}[/]")
        elif role == "ASSISTANT":
            self.messages.append(f"[green]{content}[/]")
        elif role == "RESULT":
            self.messages.append(f"  {content}")
        elif role == "CODE":
            self.messages.append(f"[dim]{content}[/]")
        else:
            self.messages.append(content)

        self.update("\n".join(self.messages))

    def clear_messages(self) -> None:
        """Clear all messages."""
        self.messages = []
        self.update("")

    def refresh_data(self) -> None:
        pass
