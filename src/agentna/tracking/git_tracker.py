"""Git integration for tracking changes."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from git import Repo
from git.exc import InvalidGitRepositoryError

from agentna.memory.models import ChangeRecord, ChangeType


@dataclass
class GitChange:
    """Represents a change from git."""

    file_path: str
    change_type: ChangeType
    additions: int = 0
    deletions: int = 0


@dataclass
class CommitInfo:
    """Information about a git commit."""

    hash: str
    short_hash: str
    author: str
    email: str
    message: str
    timestamp: datetime
    files_changed: list[GitChange]


class GitTracker:
    """Track changes using git."""

    def __init__(self, project_path: Path) -> None:
        """
        Initialize git tracker.

        Args:
            project_path: Path to the project root
        """
        self.project_path = Path(project_path)
        self._repo: Repo | None = None

    @property
    def repo(self) -> Repo | None:
        """Get the git repository."""
        if self._repo is None:
            try:
                self._repo = Repo(self.project_path, search_parent_directories=True)
            except InvalidGitRepositoryError:
                pass
        return self._repo

    @property
    def is_git_repo(self) -> bool:
        """Check if project is a git repository."""
        return self.repo is not None

    def get_current_branch(self) -> str | None:
        """Get the current branch name."""
        if not self.repo:
            return None
        try:
            return self.repo.active_branch.name
        except TypeError:
            # Detached HEAD state
            return None

    def get_head_commit(self) -> CommitInfo | None:
        """Get information about the HEAD commit."""
        if not self.repo:
            return None

        try:
            commit = self.repo.head.commit
            return self._commit_to_info(commit)
        except Exception:
            return None

    def get_recent_commits(self, limit: int = 10) -> list[CommitInfo]:
        """Get recent commits."""
        if not self.repo:
            return []

        commits = []
        try:
            for commit in self.repo.iter_commits(max_count=limit):
                commits.append(self._commit_to_info(commit))
        except Exception:
            pass

        return commits

    def get_commit(self, commit_hash: str) -> CommitInfo | None:
        """Get information about a specific commit."""
        if not self.repo:
            return None

        try:
            commit = self.repo.commit(commit_hash)
            return self._commit_to_info(commit)
        except Exception:
            return None

    def get_uncommitted_changes(self) -> list[GitChange]:
        """Get list of uncommitted changes (staged and unstaged)."""
        if not self.repo:
            return []

        changes: list[GitChange] = []

        try:
            # Get staged changes
            staged = self.repo.index.diff("HEAD")
            for diff in staged:
                change_type = self._diff_type_to_change_type(diff.change_type)
                changes.append(
                    GitChange(
                        file_path=diff.a_path or diff.b_path or "",
                        change_type=change_type,
                    )
                )

            # Get unstaged changes
            unstaged = self.repo.index.diff(None)
            for diff in unstaged:
                change_type = self._diff_type_to_change_type(diff.change_type)
                changes.append(
                    GitChange(
                        file_path=diff.a_path or diff.b_path or "",
                        change_type=change_type,
                    )
                )

            # Get untracked files
            for file_path in self.repo.untracked_files:
                changes.append(
                    GitChange(
                        file_path=file_path,
                        change_type=ChangeType.ADDED,
                    )
                )

        except Exception:
            pass

        return changes

    def get_diff_between_commits(
        self, from_commit: str, to_commit: str = "HEAD"
    ) -> list[GitChange]:
        """Get changes between two commits."""
        if not self.repo:
            return []

        changes: list[GitChange] = []

        try:
            diff = self.repo.commit(from_commit).diff(self.repo.commit(to_commit))
            for d in diff:
                change_type = self._diff_type_to_change_type(d.change_type)
                changes.append(
                    GitChange(
                        file_path=d.a_path or d.b_path or "",
                        change_type=change_type,
                    )
                )
        except Exception:
            pass

        return changes

    def get_file_history(self, file_path: str, limit: int = 10) -> list[CommitInfo]:
        """Get commit history for a specific file."""
        if not self.repo:
            return []

        commits = []
        try:
            for commit in self.repo.iter_commits(paths=file_path, max_count=limit):
                commits.append(self._commit_to_info(commit))
        except Exception:
            pass

        return commits

    def get_blame(self, file_path: str) -> list[tuple[CommitInfo, int, int, str]]:
        """
        Get blame information for a file.

        Returns:
            List of (commit_info, start_line, end_line, content) tuples
        """
        if not self.repo:
            return []

        blame_info = []
        try:
            blame = self.repo.blame("HEAD", file_path)
            for commit, lines in blame:
                info = CommitInfo(
                    hash=commit.hexsha,
                    short_hash=commit.hexsha[:7],
                    author=commit.author.name,
                    email=commit.author.email,
                    message=commit.message.strip(),
                    timestamp=datetime.fromtimestamp(commit.committed_date),
                    files_changed=[],
                )
                blame_info.append((info, 0, 0, "\n".join(lines)))
        except Exception:
            pass

        return blame_info

    def _commit_to_info(self, commit) -> CommitInfo:
        """Convert a git commit to CommitInfo."""
        files_changed: list[GitChange] = []

        try:
            # Get diff with parent
            if commit.parents:
                diff = commit.parents[0].diff(commit)
                for d in diff:
                    change_type = self._diff_type_to_change_type(d.change_type)
                    files_changed.append(
                        GitChange(
                            file_path=d.a_path or d.b_path or "",
                            change_type=change_type,
                        )
                    )
        except Exception:
            pass

        return CommitInfo(
            hash=commit.hexsha,
            short_hash=commit.hexsha[:7],
            author=commit.author.name,
            email=commit.author.email,
            message=commit.message.strip(),
            timestamp=datetime.fromtimestamp(commit.committed_date),
            files_changed=files_changed,
        )

    def _diff_type_to_change_type(self, diff_type: str) -> ChangeType:
        """Convert git diff type to ChangeType."""
        mapping = {
            "A": ChangeType.ADDED,
            "D": ChangeType.DELETED,
            "M": ChangeType.MODIFIED,
            "R": ChangeType.RENAMED,
        }
        return mapping.get(diff_type, ChangeType.MODIFIED)

    def create_change_record(self, commit_info: CommitInfo) -> ChangeRecord:
        """Create a ChangeRecord from a CommitInfo."""
        import uuid

        files_changed = [c.file_path for c in commit_info.files_changed]
        symbols_added = [
            c.file_path for c in commit_info.files_changed if c.change_type == ChangeType.ADDED
        ]
        symbols_removed = [
            c.file_path for c in commit_info.files_changed if c.change_type == ChangeType.DELETED
        ]
        symbols_modified = [
            c.file_path for c in commit_info.files_changed if c.change_type == ChangeType.MODIFIED
        ]

        return ChangeRecord(
            id=str(uuid.uuid4()),
            timestamp=commit_info.timestamp,
            commit_hash=commit_info.hash,
            author=commit_info.author,
            message=commit_info.message,
            files_changed=files_changed,
            symbols_added=symbols_added,
            symbols_modified=symbols_modified,
            symbols_removed=symbols_removed,
            change_type=ChangeType.MODIFIED,
        )
