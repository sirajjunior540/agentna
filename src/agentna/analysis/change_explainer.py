"""Change explainer using LLM."""

from dataclasses import dataclass

from agentna.analysis.impact_analyzer import ImpactAnalyzer, ImpactResult
from agentna.core.config import LLMConfig
from agentna.llm.prompts import SYSTEM_PROMPT, format_explain_changes, format_impact_analysis
from agentna.llm.router import LLMRouter
from agentna.memory.hybrid_store import HybridStore
from agentna.tracking.git_tracker import CommitInfo, GitTracker


@dataclass
class ChangeExplanation:
    """Explanation of code changes."""

    summary: str
    details: str
    impact: ImpactResult
    recommendations: list[str]
    affected_files: list[str]


class ChangeExplainer:
    """Explains code changes using LLM."""

    def __init__(
        self,
        store: HybridStore,
        llm_config: LLMConfig,
        git_tracker: GitTracker | None = None,
    ) -> None:
        """
        Initialize the change explainer.

        Args:
            store: The hybrid memory store
            llm_config: LLM configuration
            git_tracker: Optional git tracker for commit info
        """
        self.store = store
        self.impact_analyzer = ImpactAnalyzer(store)
        self.llm_router = LLMRouter(llm_config)
        self.git_tracker = git_tracker

    def explain_commit(self, commit_hash: str) -> ChangeExplanation:
        """
        Explain changes in a specific commit.

        Args:
            commit_hash: Git commit hash

        Returns:
            ChangeExplanation with analysis
        """
        if not self.git_tracker:
            raise ValueError("Git tracker not available")

        commit = self.git_tracker.get_commit(commit_hash)
        if not commit:
            raise ValueError(f"Commit {commit_hash} not found")

        return self._explain_commit_info(commit)

    def explain_recent_changes(self, limit: int = 5) -> list[ChangeExplanation]:
        """
        Explain recent commits.

        Args:
            limit: Number of recent commits to explain

        Returns:
            List of ChangeExplanation for each commit
        """
        if not self.git_tracker:
            raise ValueError("Git tracker not available")

        commits = self.git_tracker.get_recent_commits(limit)
        explanations = []

        for commit in commits:
            try:
                explanation = self._explain_commit_info(commit)
                explanations.append(explanation)
            except Exception:
                continue

        return explanations

    def explain_files(self, file_paths: list[str]) -> ChangeExplanation:
        """
        Explain changes to specific files.

        Args:
            file_paths: List of file paths that changed

        Returns:
            ChangeExplanation with analysis
        """
        # Get impact analysis
        impact = self.impact_analyzer.analyze_files(file_paths)

        # Get code context
        code_context = self._get_code_context(file_paths)

        # Generate explanation using LLM
        prompt = format_explain_changes(
            changed_files=file_paths,
            change_details=self._format_impact_details(impact),
            affected_code=code_context,
        )

        try:
            explanation_text = self.llm_router.complete_sync(
                prompt=prompt,
                system=SYSTEM_PROMPT,
                max_tokens=1000,
            )
        except Exception:
            explanation_text = self._generate_fallback_explanation(file_paths, impact)

        # Parse the explanation
        summary, details = self._parse_explanation(explanation_text)

        return ChangeExplanation(
            summary=summary,
            details=details,
            impact=impact,
            recommendations=impact.recommendations,
            affected_files=impact.affected_files,
        )

    def explain_uncommitted(self) -> ChangeExplanation | None:
        """
        Explain uncommitted changes.

        Returns:
            ChangeExplanation or None if no changes
        """
        if not self.git_tracker:
            return None

        changes = self.git_tracker.get_uncommitted_changes()
        if not changes:
            return None

        file_paths = [c.file_path for c in changes]
        return self.explain_files(file_paths)

    def _explain_commit_info(self, commit: CommitInfo) -> ChangeExplanation:
        """Explain a commit from CommitInfo."""
        file_paths = [c.file_path for c in commit.files_changed]

        # Get impact analysis
        impact = self.impact_analyzer.analyze_files(file_paths)

        # Get code context
        code_context = self._get_code_context(file_paths)

        # Build change details with commit message
        change_details = f"Commit: {commit.short_hash}\n"
        change_details += f"Author: {commit.author}\n"
        change_details += f"Message: {commit.message}\n\n"
        change_details += self._format_impact_details(impact)

        # Generate explanation using LLM
        prompt = format_explain_changes(
            changed_files=file_paths,
            change_details=change_details,
            affected_code=code_context,
        )

        try:
            explanation_text = self.llm_router.complete_sync(
                prompt=prompt,
                system=SYSTEM_PROMPT,
                max_tokens=1000,
            )
        except Exception:
            explanation_text = self._generate_fallback_explanation(file_paths, impact)

        summary, details = self._parse_explanation(explanation_text)

        return ChangeExplanation(
            summary=f"[{commit.short_hash}] {summary}",
            details=details,
            impact=impact,
            recommendations=impact.recommendations,
            affected_files=impact.affected_files,
        )

    def _get_code_context(self, file_paths: list[str], max_chars: int = 3000) -> str:
        """Get code context for the changed files."""
        context_parts = []
        chars_used = 0

        for file_path in file_paths:
            if chars_used >= max_chars:
                break

            context = self.store.get_file_context(file_path, include_related=False)
            if context["chunks"]:
                for chunk in context["chunks"][:2]:
                    content = chunk.content[:500]
                    context_parts.append(f"### {file_path}\n```\n{content}\n```")
                    chars_used += len(content)

        return "\n\n".join(context_parts) if context_parts else "No code context available"

    def _format_impact_details(self, impact: ImpactResult) -> str:
        """Format impact analysis as text."""
        lines = []
        lines.append(f"Impact Score: {impact.impact_score:.2f} ({impact.severity})")
        lines.append(f"Changed Symbols: {len(impact.changed_symbols)}")
        lines.append(f"Directly Affected: {len(impact.directly_affected)}")
        lines.append(f"Transitively Affected: {len(impact.transitively_affected)}")

        if impact.risk_factors:
            lines.append("\nRisk Factors:")
            for risk in impact.risk_factors:
                lines.append(f"  - {risk}")

        return "\n".join(lines)

    def _parse_explanation(self, text: str) -> tuple[str, str]:
        """Parse LLM explanation into summary and details."""
        lines = text.strip().split("\n")

        # First non-empty line is summary
        summary = ""
        details_start = 0

        for i, line in enumerate(lines):
            line = line.strip()
            if line:
                # Remove markdown headers
                if line.startswith("#"):
                    line = line.lstrip("#").strip()
                summary = line[:200]  # Limit summary length
                details_start = i + 1
                break

        # Rest is details
        details = "\n".join(lines[details_start:]).strip()

        return summary or "Changes detected", details or "No detailed analysis available"

    def _generate_fallback_explanation(
        self,
        file_paths: list[str],
        impact: ImpactResult,
    ) -> str:
        """Generate a fallback explanation without LLM."""
        lines = []
        lines.append(f"Changes to {len(file_paths)} file(s)")
        lines.append("")
        lines.append("## Modified Files")
        for path in file_paths:
            lines.append(f"- {path}")

        if impact.affected_files:
            lines.append("")
            lines.append("## Affected Files")
            for path in impact.affected_files[:10]:
                lines.append(f"- {path}")

        lines.append("")
        lines.append(f"## Impact: {impact.severity.upper()}")
        lines.append(f"Score: {impact.impact_score:.2f}")

        if impact.risk_factors:
            lines.append("")
            lines.append("## Risk Factors")
            for risk in impact.risk_factors:
                lines.append(f"- {risk}")

        return "\n".join(lines)
