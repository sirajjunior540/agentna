"""Git hooks management for AgentNA."""

from pathlib import Path

POST_COMMIT_HOOK = '''#!/bin/sh
# AgentNA post-commit hook - triggers incremental sync after commits
# Runs in background to not block git operations

if command -v agent &> /dev/null; then
    agent sync --quiet 2>/dev/null &
fi
'''

POST_MERGE_HOOK = '''#!/bin/sh
# AgentNA post-merge hook - triggers sync after merges
# Runs in background to not block git operations

if command -v agent &> /dev/null; then
    agent sync --quiet 2>/dev/null &
fi
'''

POST_CHECKOUT_HOOK = '''#!/bin/sh
# AgentNA post-checkout hook - triggers sync after branch checkout
# Only triggers on branch checkout (not file checkout)
# $3 is 1 for branch checkout, 0 for file checkout

if [ "$3" = "1" ]; then
    if command -v agent &> /dev/null; then
        agent sync --quiet 2>/dev/null &
    fi
fi
'''

HOOK_MARKER = "# AgentNA"


def get_git_hooks_dir(project_path: Path) -> Path | None:
    """Get the git hooks directory for a project."""
    git_dir = project_path / ".git"
    if not git_dir.exists():
        # Check if it's inside a git repo
        current = project_path.parent
        while current != current.parent:
            if (current / ".git").exists():
                git_dir = current / ".git"
                break
            current = current.parent

    if not git_dir.exists():
        return None

    # Handle git worktrees where .git is a file
    if git_dir.is_file():
        with open(git_dir) as f:
            content = f.read().strip()
            if content.startswith("gitdir:"):
                git_dir = Path(content.split(":", 1)[1].strip())

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    return hooks_dir


def is_hook_installed(hook_path: Path) -> bool:
    """Check if AgentNA hook is already installed."""
    if not hook_path.exists():
        return False

    content = hook_path.read_text()
    return HOOK_MARKER in content


def install_hook(hooks_dir: Path, hook_name: str, hook_content: str) -> str:
    """
    Install a git hook.

    Returns:
        Status: "installed", "already_installed", or "appended"
    """
    hook_path = hooks_dir / hook_name

    if is_hook_installed(hook_path):
        return "already_installed"

    if hook_path.exists():
        # Append to existing hook
        existing = hook_path.read_text()
        if not existing.endswith("\n"):
            existing += "\n"
        hook_path.write_text(existing + "\n" + hook_content)
        hook_path.chmod(0o755)
        return "appended"
    else:
        # Create new hook
        hook_path.write_text(hook_content)
        hook_path.chmod(0o755)
        return "installed"


def uninstall_hook(hooks_dir: Path, hook_name: str) -> bool:
    """
    Remove AgentNA hook content from a git hook.

    Returns:
        True if hook was modified, False otherwise
    """
    hook_path = hooks_dir / hook_name

    if not hook_path.exists():
        return False

    content = hook_path.read_text()
    if HOOK_MARKER not in content:
        return False

    # Remove AgentNA section
    lines = content.split("\n")
    new_lines = []
    skip_until_empty = False

    for line in lines:
        if HOOK_MARKER in line:
            skip_until_empty = True
            continue
        if skip_until_empty:
            if line.strip() == "" or line.startswith("fi"):
                skip_until_empty = False
                if line.startswith("fi"):
                    continue
            else:
                continue
        new_lines.append(line)

    new_content = "\n".join(new_lines).strip()

    if new_content.strip() in ("#!/bin/sh", "#!/bin/bash", ""):
        # Hook is now empty, remove it
        hook_path.unlink()
    else:
        hook_path.write_text(new_content + "\n")

    return True


def install_all_hooks(project_path: Path) -> dict[str, str]:
    """
    Install all AgentNA git hooks.

    Returns:
        Dictionary of hook_name -> status
    """
    hooks_dir = get_git_hooks_dir(project_path)
    if not hooks_dir:
        return {"error": "Not a git repository"}

    results = {}

    hooks = {
        "post-commit": POST_COMMIT_HOOK,
        "post-merge": POST_MERGE_HOOK,
        "post-checkout": POST_CHECKOUT_HOOK,
    }

    for hook_name, hook_content in hooks.items():
        results[hook_name] = install_hook(hooks_dir, hook_name, hook_content)

    return results


def uninstall_all_hooks(project_path: Path) -> dict[str, bool]:
    """
    Uninstall all AgentNA git hooks.

    Returns:
        Dictionary of hook_name -> was_removed
    """
    hooks_dir = get_git_hooks_dir(project_path)
    if not hooks_dir:
        return {"error": False}

    results = {}

    for hook_name in ["post-commit", "post-merge", "post-checkout"]:
        results[hook_name] = uninstall_hook(hooks_dir, hook_name)

    return results


def get_hooks_status(project_path: Path) -> dict[str, bool]:
    """
    Check which hooks are installed.

    Returns:
        Dictionary of hook_name -> is_installed
    """
    hooks_dir = get_git_hooks_dir(project_path)
    if not hooks_dir:
        return {}

    results = {}

    for hook_name in ["post-commit", "post-merge", "post-checkout"]:
        hook_path = hooks_dir / hook_name
        results[hook_name] = is_hook_installed(hook_path)

    return results
