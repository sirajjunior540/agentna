"""Main CLI application for AgentNA."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from agentna import __version__
from agentna.core.exceptions import AgentNAError, ProjectNotFoundError
from agentna.core.project import Project

# Create the main app
app = typer.Typer(
    name="agent",
    help="AgentNA - Local code agent with memory and change tracking",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"AgentNA version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """AgentNA - Local code agent with memory and change tracking."""
    pass


@app.command()
def init(
    path: Annotated[
        Optional[Path],
        typer.Argument(help="Project directory (defaults to current directory)"),
    ] = None,
    name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="Project name"),
    ] = None,
) -> None:
    """Initialize AgentNA in a project directory."""
    try:
        if path is None:
            path = Path.cwd()
        else:
            path = Path(path).resolve()

        # Check if already initialized
        agentna_dir = path / ".agentna"
        if agentna_dir.exists():
            console.print(
                f"[yellow]AgentNA is already initialized in {path}[/yellow]"
            )
            raise typer.Exit(1)

        # Initialize project
        project = Project.init(path)

        # Update name if provided
        if name:
            project.config.name = name
            project.save_config()

        console.print(
            Panel(
                f"[green]Initialized AgentNA in [bold]{path}[/bold][/green]\n\n"
                f"Project: [cyan]{project.name}[/cyan]\n\n"
                "Next steps:\n"
                "  [dim]agent sync[/dim]    - Index your codebase\n"
                "  [dim]agent watch[/dim]   - Start file watcher\n"
                "  [dim]agent ask[/dim]     - Query your codebase",
                title="AgentNA Initialized",
                border_style="green",
            )
        )

    except AgentNAError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed status"),
    ] = False,
) -> None:
    """Show the status of the AgentNA index."""
    try:
        if path:
            project = Project(path)
        else:
            project = Project.find_project()

        status = project.get_status()

        # Create status table
        table = Table(title=f"AgentNA Status: {project.name}", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Project", project.name)
        table.add_row("Path", str(project.root))
        table.add_row("Files Indexed", str(status.total_files))
        table.add_row("Symbols", str(status.total_symbols))
        table.add_row("Relationships", str(status.total_relationships))
        table.add_row(
            "Index Size",
            f"{status.index_size_bytes / 1024:.1f} KB"
            if status.index_size_bytes > 0
            else "0 KB",
        )

        if status.last_full_sync:
            table.add_row("Last Full Sync", status.last_full_sync.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            table.add_row("Last Full Sync", "[dim]Never[/dim]")

        if status.last_incremental_sync:
            table.add_row(
                "Last Incremental Sync",
                status.last_incremental_sync.strftime("%Y-%m-%d %H:%M:%S"),
            )
        else:
            table.add_row("Last Incremental Sync", "[dim]Never[/dim]")

        console.print(table)

        if verbose:
            console.print("\n[bold]Configuration:[/bold]")
            config_table = Table(show_header=False)
            config_table.add_column("Setting", style="cyan")
            config_table.add_column("Value")

            config_table.add_row("LLM Provider", project.config.llm.preferred_provider)
            config_table.add_row("Ollama Model", project.config.llm.ollama_model)
            config_table.add_row("Watcher Enabled", str(project.config.watcher.enabled))
            config_table.add_row(
                "Include Patterns",
                ", ".join(project.config.indexing.include_patterns[:3]) + "...",
            )
            console.print(config_table)

    except ProjectNotFoundError:
        console.print(
            "[red]No AgentNA project found.[/red]\n"
            "Run [cyan]agent init[/cyan] to initialize a project."
        )
        raise typer.Exit(1)
    except AgentNAError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def sync(
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    full: Annotated[
        bool,
        typer.Option("--full", "-f", help="Force full reindex"),
    ] = False,
) -> None:
    """Sync/reindex the codebase."""
    try:
        from agentna.indexing import run_sync

        if path:
            project = Project(path)
        else:
            project = Project.find_project()

        console.print(f"[cyan]Syncing project: {project.name}[/cyan]")

        # Count files to index
        files = list(project.iter_files())
        console.print(f"Found [green]{len(files)}[/green] files to index")

        if full:
            console.print("[yellow]Performing full reindex...[/yellow]")
        else:
            console.print("[yellow]Performing incremental sync...[/yellow]")

        # Run the sync
        stats = run_sync(project, full=full)

        # Display results
        console.print(f"\n[green]Sync complete![/green]")
        console.print(f"  Files indexed: {stats.get('files_indexed', 0)}")
        console.print(f"  Code chunks: {stats.get('total_chunks', 0)}")
        console.print(f"  Relationships: {stats.get('total_relationships', 0)}")
        if "deleted_files" in stats:
            console.print(f"  Deleted files: {stats['deleted_files']}")

    except ProjectNotFoundError:
        console.print(
            "[red]No AgentNA project found.[/red]\n"
            "Run [cyan]agent init[/cyan] to initialize a project."
        )
        raise typer.Exit(1)
    except AgentNAError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def ask(
    question: Annotated[
        str,
        typer.Argument(help="Question to ask about the codebase"),
    ],
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum search results"),
    ] = 10,
    deep: Annotated[
        bool,
        typer.Option("--deep", "-d", help="Deep search - follow relationships for more context"),
    ] = True,
) -> None:
    """Ask a question about the codebase."""
    try:
        from agentna.llm import LLMRouter
        from agentna.llm.prompts import SYSTEM_PROMPT, format_ask_codebase
        from agentna.memory.hybrid_store import HybridStore

        if path:
            project = Project(path)
        else:
            project = Project.find_project()

        console.print(f"[cyan]Querying project: {project.name}[/cyan]")
        console.print(f"Question: {question}\n")

        # Get store and search for relevant code
        store = HybridStore(project.chroma_dir, project.graph_path)

        # Search with code priority (code > docs)
        results = store.search(question, n_results=limit, include_related=True, code_priority=True)

        if not results:
            console.print("[yellow]No relevant code found in the index.[/yellow]")
            console.print("Try running [cyan]agent sync[/cyan] to index your codebase.")
            return

        # Build context from search results - include MORE content for better analysis
        context_parts = []
        symbols = []
        seen_files = set()

        for result in results:
            chunk = result.chunk
            # Include more content per chunk (up to 2000 chars)
            content = chunk.content[:2000] if len(chunk.content) > 2000 else chunk.content
            context_parts.append(
                f"### File: {chunk.file_path} (lines {chunk.line_start}-{chunk.line_end})\n"
                f"Symbol: {chunk.symbol_name or 'N/A'} ({chunk.symbol_type.value})\n"
                f"```{chunk.language}\n{content}\n```"
            )
            if chunk.symbol_name:
                symbols.append(f"{chunk.symbol_name} ({chunk.symbol_type.value}) - {chunk.file_path}:{chunk.line_start}")
            seen_files.add(chunk.file_path)

        # Deep search: follow graph relationships to find MORE related code
        if deep:
            related_chunks = []
            for result in results[:5]:  # Follow relationships from top 5 results
                # Get dependencies and dependents
                deps = store.graph.get_dependencies(result.chunk.id, max_depth=2)
                dependents = store.graph.get_dependents(result.chunk.id, max_depth=1)

                for node_id in deps + dependents:
                    if len(related_chunks) >= 5:  # Limit additional context
                        break
                    node = store.graph.get_node(node_id)
                    if node and node.file_path and node.file_path not in seen_files:
                        # Get the chunk content
                        related_chunk = store.embeddings.get_chunk(node_id)
                        if related_chunk:
                            content = related_chunk.content[:1500]
                            related_chunks.append(
                                f"### Related: {related_chunk.file_path} (lines {related_chunk.line_start}-{related_chunk.line_end})\n"
                                f"Symbol: {related_chunk.symbol_name or 'N/A'} ({related_chunk.symbol_type.value})\n"
                                f"```{related_chunk.language}\n{content}\n```"
                            )
                            seen_files.add(node.file_path)

            if related_chunks:
                context_parts.append("\n## Related Code (via dependencies)")
                context_parts.extend(related_chunks)

        context = "\n\n".join(context_parts)
        symbols_str = "\n".join(f"- {s}" for s in symbols) if symbols else "No specific symbols"

        # Get relationships - MORE detailed
        relationships = []
        for result in results:
            rels = store.graph.get_relationships(result.chunk.id)
            for rel in rels[:5]:
                rel_str = f"{rel.source_id} --[{rel.relation_type.value}]--> {rel.target_id}"
                if rel_str not in relationships:
                    relationships.append(rel_str)
        relationships_str = "\n".join(relationships[:20]) if relationships else "No relationships found"

        # Try to use LLM for answer
        try:
            router = LLMRouter(project.config.llm)
            status = router.get_status()
            if not any(status.values()):
                console.print("[yellow]No LLM available (Ollama not running or Claude API not configured)[/yellow]")
                console.print(f"[dim]Status: {status}[/dim]\n")
                # Fallback to showing results
                _show_search_results(results)
            else:
                prompt = format_ask_codebase(question, context, symbols_str, relationships_str)
                # Use more tokens for detailed answers
                answer = router.complete_sync(prompt, system=SYSTEM_PROMPT, max_tokens=2500)
                console.print("[green]Answer:[/green]\n")
                # Render as Markdown for proper formatting
                console.print(Markdown(answer))
                return
        except Exception as e:
            # Fallback: just show search results
            console.print(f"[yellow]LLM error: {e}[/yellow]\n")
            _show_search_results(results)

    except ProjectNotFoundError:
        console.print(
            "[red]No AgentNA project found.[/red]\n"
            "Run [cyan]agent init[/cyan] to initialize a project."
        )
        raise typer.Exit(1)
    except AgentNAError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def _show_search_results(results: list) -> None:
    """Display search results as fallback when LLM is unavailable."""
    for i, result in enumerate(results, 1):
        chunk = result.chunk
        console.print(f"[cyan]{i}. {chunk.file_path}:{chunk.line_start}[/cyan]")
        if chunk.symbol_name:
            console.print(f"   Symbol: {chunk.symbol_name} ({chunk.symbol_type.value})")
        console.print(f"   Score: {result.score:.2f}")
        preview = chunk.content[:200].replace('\n', ' ')
        console.print(f"   {preview}...\n")


@app.command()
def explain(
    target: Annotated[
        Optional[str],
        typer.Argument(help="Commit hash, file path, or 'recent' for recent changes"),
    ] = "recent",
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
) -> None:
    """Explain changes in the codebase."""
    try:
        from agentna.analysis import ChangeExplainer
        from agentna.memory.hybrid_store import HybridStore
        from agentna.tracking import GitTracker

        if path:
            project = Project(path)
        else:
            project = Project.find_project()

        console.print(f"[cyan]Explaining changes in: {project.name}[/cyan]")

        # Initialize components
        store = HybridStore(project.chroma_dir, project.graph_path)
        git_tracker = GitTracker(project.root)
        explainer = ChangeExplainer(store, project.config.llm, git_tracker)

        if target == "recent":
            # Explain recent commits
            if not git_tracker.is_git_repo:
                console.print("[yellow]Not a git repository. Cannot explain recent changes.[/yellow]")
                return

            explanations = explainer.explain_recent_changes(limit=3)
            if not explanations:
                console.print("[yellow]No recent changes found.[/yellow]")
                return

            for explanation in explanations:
                console.print(f"\n[green]## {explanation.summary}[/green]")
                console.print(explanation.details)
                console.print(f"\n[dim]Impact: {explanation.impact.severity} ({explanation.impact.impact_score:.2f})[/dim]")
                if explanation.affected_files:
                    console.print(f"[dim]Affected files: {', '.join(explanation.affected_files[:5])}[/dim]")
                console.print("-" * 60)

        elif target == "uncommitted":
            # Explain uncommitted changes
            explanation = explainer.explain_uncommitted()
            if not explanation:
                console.print("[yellow]No uncommitted changes found.[/yellow]")
                return

            console.print(f"\n[green]## {explanation.summary}[/green]")
            console.print(explanation.details)
            console.print(f"\n[cyan]Impact: {explanation.impact.severity}[/cyan]")
            if explanation.recommendations:
                console.print("\n[yellow]Recommendations:[/yellow]")
                for rec in explanation.recommendations:
                    console.print(f"  - {rec}")

        elif Path(target).exists() or "/" in target:
            # Explain changes to a specific file
            file_paths = [target]
            explanation = explainer.explain_files(file_paths)

            console.print(f"\n[green]## {explanation.summary}[/green]")
            console.print(explanation.details)
            console.print(f"\n[cyan]Impact: {explanation.impact.severity}[/cyan]")

        else:
            # Assume it's a commit hash
            if not git_tracker.is_git_repo:
                console.print("[yellow]Not a git repository.[/yellow]")
                return

            try:
                explanation = explainer.explain_commit(target)
                console.print(f"\n[green]## {explanation.summary}[/green]")
                console.print(explanation.details)
                console.print(f"\n[cyan]Impact: {explanation.impact.severity}[/cyan]")
            except ValueError as e:
                console.print(f"[red]Error: {e}[/red]")
                return

    except ProjectNotFoundError:
        console.print(
            "[red]No AgentNA project found.[/red]\n"
            "Run [cyan]agent init[/cyan] to initialize a project."
        )
        raise typer.Exit(1)
    except AgentNAError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def watch(
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
) -> None:
    """Start the file watcher daemon."""
    try:
        from agentna.tracking import FileWatcher, create_watcher_callback

        if path:
            project = Project(path)
        else:
            project = Project.find_project()

        console.print(f"[cyan]Starting watcher for: {project.name}[/cyan]")
        console.print(f"Watching: {project.root}")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        # Create watcher with indexing callback
        callback = create_watcher_callback(project)
        watcher = FileWatcher(project, on_change=callback)

        try:
            watcher.start()
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping watcher...[/yellow]")
            watcher.stop()
            console.print("[green]Watcher stopped.[/green]")

    except ProjectNotFoundError:
        console.print(
            "[red]No AgentNA project found.[/red]\n"
            "Run [cyan]agent init[/cyan] to initialize a project."
        )
        raise typer.Exit(1)
    except AgentNAError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def hooks(
    action: Annotated[
        str,
        typer.Argument(help="Action: install, uninstall, or status"),
    ] = "status",
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
) -> None:
    """Manage git hooks for automatic indexing."""
    try:
        from agentna.tracking import get_hooks_status, install_all_hooks, uninstall_all_hooks

        if path:
            project = Project(path)
        else:
            project = Project.find_project()

        if action == "install":
            console.print(f"[cyan]Installing git hooks for: {project.name}[/cyan]")
            results = install_all_hooks(project.root)

            if "error" in results:
                console.print(f"[red]Error: {results['error']}[/red]")
                raise typer.Exit(1)

            for hook, status in results.items():
                if status == "installed":
                    console.print(f"  [green]Installed:[/green] {hook}")
                elif status == "appended":
                    console.print(f"  [yellow]Appended to:[/yellow] {hook}")
                else:
                    console.print(f"  [dim]Already installed:[/dim] {hook}")

            console.print("\n[green]Git hooks installed![/green]")
            console.print("AgentNA will now auto-sync after commits and merges.")

        elif action == "uninstall":
            console.print(f"[cyan]Uninstalling git hooks for: {project.name}[/cyan]")
            results = uninstall_all_hooks(project.root)

            for hook, removed in results.items():
                if removed:
                    console.print(f"  [yellow]Removed:[/yellow] {hook}")
                else:
                    console.print(f"  [dim]Not installed:[/dim] {hook}")

            console.print("\n[green]Git hooks uninstalled.[/green]")

        else:  # status
            console.print(f"[cyan]Git hooks status for: {project.name}[/cyan]\n")
            status = get_hooks_status(project.root)

            if not status:
                console.print("[yellow]Not a git repository[/yellow]")
                return

            for hook, installed in status.items():
                if installed:
                    console.print(f"  [green]Installed:[/green] {hook}")
                else:
                    console.print(f"  [dim]Not installed:[/dim] {hook}")

            console.print("\nRun [cyan]agent hooks install[/cyan] to install hooks.")

    except ProjectNotFoundError:
        console.print(
            "[red]No AgentNA project found.[/red]\n"
            "Run [cyan]agent init[/cyan] to initialize a project."
        )
        raise typer.Exit(1)
    except AgentNAError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def serve(
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
) -> None:
    """Run MCP server for Claude CLI integration."""
    try:
        from agentna.mcp import run_server

        if path:
            project = Project(path)
        else:
            project = Project.find_project()

        # Run the MCP server (this blocks and communicates via stdio)
        run_server(project.root)

    except ProjectNotFoundError:
        console.print(
            "[red]No AgentNA project found.[/red]\n"
            "Run [cyan]agent init[/cyan] to initialize a project."
        )
        raise typer.Exit(1)
    except AgentNAError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="tui")
def launch_tui(
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
) -> None:
    """Launch the Terminal User Interface."""
    try:
        from agentna.tui import run_tui

        if path:
            # Validate project exists
            Project(path)
            run_tui(path)
        else:
            # Find project first
            Project.find_project()
            run_tui(None)

    except ProjectNotFoundError:
        console.print(
            "[red]No AgentNA project found.[/red]\n"
            "Run [cyan]agent init[/cyan] to initialize a project."
        )
        raise typer.Exit(1)
    except AgentNAError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
