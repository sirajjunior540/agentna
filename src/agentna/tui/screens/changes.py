"""Changes screen for AgentNA TUI."""

from textual.widgets import Static

from agentna.core.project import Project
from agentna.memory.hybrid_store import HybridStore


class ChangesScreen(Static):
    """Changes screen - shows recent changes."""

    def __init__(self, project: Project, store: HybridStore) -> None:
        super().__init__()
        self.project = project
        self.store = store

    def on_mount(self) -> None:
        self.update(
            "[bold magenta]CHANGES[/]\n\n"
            f"Project: [green]{self.project.name}[/]\n\n"
            "[yellow]Change tracking info:[/]\n\n"
            "Use the CLI to explain changes:\n\n"
            "  [bold white]agent explain recent[/]     - Recent commits\n"
            "  [bold white]agent explain <hash>[/]     - Specific commit\n"
            "  [bold white]agent explain uncommitted[/] - Staged changes\n"
        )

    def refresh_data(self) -> None:
        pass
