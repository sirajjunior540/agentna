"""Symbol analyzer for pre-computing function/class context at sync time.

This is the core of AgentNA's memory system. Instead of analyzing code at query time,
we analyze everything during sync and store the understanding for instant recall.

Philosophy: Understand once, remember forever.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Callable

from agentna.core.config import LLMConfig
from agentna.llm import LLMRouter
from agentna.memory.knowledge_graph import KnowledgeGraph
from agentna.memory.models import CodeChunk, SymbolSummary, SymbolType


# Prompt for generating symbol summaries
SYMBOL_SUMMARY_PROMPT = """Analyze this code and provide a brief summary.

Symbol: {symbol_name} ({symbol_type})
File: {file_path}

```{language}
{code}
```

Respond in this EXACT JSON format (no markdown, just JSON):
{{
  "summary": "What this does in 1-2 sentences",
  "purpose": "Why this exists / business purpose"
}}"""


class SymbolAnalyzer:
    """Analyzes code symbols and generates pre-computed summaries.

    This runs during `agent sync` to build the memory layer.
    """

    def __init__(
        self,
        graph: KnowledgeGraph,
        llm_config: LLMConfig,
        summaries_path: Path,
    ) -> None:
        """
        Initialize the analyzer.

        Args:
            graph: Knowledge graph for relationships
            llm_config: LLM configuration
            summaries_path: Path to store summaries JSON
        """
        self.graph = graph
        self.llm_config = llm_config
        self.summaries_path = summaries_path
        self._router: LLMRouter | None = None
        self._summaries: dict[str, SymbolSummary] = {}

        # Load existing summaries
        self._load_summaries()

    @property
    def router(self) -> LLMRouter:
        """Lazy-load LLM router."""
        if self._router is None:
            self._router = LLMRouter(self.llm_config)
        return self._router

    def _load_summaries(self) -> None:
        """Load existing summaries from disk."""
        if self.summaries_path.exists():
            try:
                data = json.loads(self.summaries_path.read_text())
                for item in data:
                    summary = SymbolSummary(**item)
                    self._summaries[summary.id] = summary
            except Exception:
                self._summaries = {}

    def _save_summaries(self) -> None:
        """Save summaries to disk."""
        self.summaries_path.parent.mkdir(parents=True, exist_ok=True)
        data = [s.model_dump(mode="json") for s in self._summaries.values()]
        self.summaries_path.write_text(json.dumps(data, indent=2, default=str))

    def analyze_chunk(self, chunk: CodeChunk, force: bool = False) -> SymbolSummary | None:
        """
        Analyze a code chunk and generate its summary.

        Args:
            chunk: The code chunk to analyze
            force: Force re-analysis even if cached

        Returns:
            SymbolSummary or None if analysis failed
        """
        # Skip file-level chunks (too broad)
        if chunk.symbol_type == SymbolType.FILE:
            return None

        # Check if already analyzed and unchanged
        if not force and chunk.id in self._summaries:
            existing = self._summaries[chunk.id]
            if existing.content_hash == chunk.content_hash:
                return existing  # Return cached

        # Get relationships from graph
        callers = []
        callees = []
        dependencies = []
        dependents = []

        relationships = self.graph.get_relationships(chunk.id)
        for rel in relationships:
            if rel.source_id == chunk.id:
                # This symbol is the source
                if rel.relation_type.value == "calls":
                    callees.append(rel.target_id)
                elif rel.relation_type.value == "imports":
                    dependencies.append(rel.target_id)
            else:
                # This symbol is the target
                if rel.relation_type.value == "calls":
                    callers.append(rel.source_id)
                elif rel.relation_type.value in ("imports", "depends_on"):
                    dependents.append(rel.source_id)

        # Get all dependents (what breaks if this changes)
        all_dependents = self.graph.get_dependents(chunk.id, max_depth=3)
        impact_files = set()
        for dep_id in all_dependents:
            node = self.graph.get_node(dep_id)
            if node and node.file_path:
                impact_files.add(node.file_path)

        # Calculate impact score
        impact_score = min(1.0, len(all_dependents) / 20.0)

        # Generate LLM summary
        summary_text = ""
        purpose_text = ""

        try:
            if self.router.get_status().get("ollama") or self.router.get_status().get("claude"):
                prompt = SYMBOL_SUMMARY_PROMPT.format(
                    symbol_name=chunk.symbol_name or "unknown",
                    symbol_type=chunk.symbol_type.value,
                    file_path=chunk.file_path,
                    language=chunk.language,
                    code=chunk.content[:1500],  # Limit for faster processing
                )

                response = self.router.complete_sync(
                    prompt,
                    system="You are a code analyzer. Respond only with valid JSON.",
                    max_tokens=200,
                )

                # Parse JSON response
                try:
                    # Clean up response (remove markdown if present)
                    response = response.strip()
                    if response.startswith("```"):
                        response = response.split("```")[1]
                        if response.startswith("json"):
                            response = response[4:]
                    result = json.loads(response)
                    summary_text = result.get("summary", "")
                    purpose_text = result.get("purpose", "")
                except json.JSONDecodeError:
                    # Fallback: use docstring or first line
                    summary_text = chunk.docstring or f"{chunk.symbol_type.value}: {chunk.symbol_name}"
        except Exception:
            # No LLM available - use docstring or generate basic summary
            summary_text = chunk.docstring or f"{chunk.symbol_type.value}: {chunk.symbol_name}"

        # Create summary
        summary = SymbolSummary(
            id=chunk.id,
            symbol_name=chunk.symbol_name or "unknown",
            symbol_type=chunk.symbol_type,
            file_path=chunk.file_path,
            line_start=chunk.line_start,
            line_end=chunk.line_end,
            summary=summary_text,
            purpose=purpose_text,
            callers=callers[:10],  # Limit stored relationships
            callees=callees[:10],
            dependencies=dependencies[:10],
            dependents=list(all_dependents)[:20],
            impact_score=impact_score,
            impact_files=list(impact_files)[:20],
            signature=chunk.signature,
            content_hash=chunk.content_hash,
        )

        # Cache it
        self._summaries[chunk.id] = summary
        return summary

    def analyze_chunks(
        self,
        chunks: list[CodeChunk],
        force: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, int]:
        """
        Analyze multiple chunks and generate summaries.

        Args:
            chunks: List of code chunks to analyze
            force: Force re-analysis
            progress_callback: Optional progress callback

        Returns:
            Statistics dictionary
        """
        analyzed = 0
        skipped = 0
        failed = 0

        # Filter to only functions, classes, methods (skip file chunks)
        analyzable = [c for c in chunks if c.symbol_type != SymbolType.FILE]

        for i, chunk in enumerate(analyzable):
            if progress_callback:
                progress_callback(
                    f"{chunk.symbol_name or chunk.file_path}",
                    i + 1,
                    len(analyzable),
                )

            try:
                result = self.analyze_chunk(chunk, force=force)
                if result:
                    if result.content_hash == chunk.content_hash and not force:
                        skipped += 1
                    else:
                        analyzed += 1
                else:
                    skipped += 1
            except Exception:
                failed += 1

        # Save all summaries
        self._save_summaries()

        return {
            "analyzed": analyzed,
            "skipped": skipped,
            "failed": failed,
            "total_summaries": len(self._summaries),
        }

    def get_summary(self, symbol_id: str) -> SymbolSummary | None:
        """Get a pre-computed summary by ID."""
        return self._summaries.get(symbol_id)

    def search_summaries(self, query: str, limit: int = 10) -> list[SymbolSummary]:
        """Search summaries by symbol name or content."""
        query_lower = query.lower()
        matches = []

        for summary in self._summaries.values():
            score = 0
            if query_lower in summary.symbol_name.lower():
                score += 10
            if query_lower in summary.summary.lower():
                score += 5
            if query_lower in summary.purpose.lower():
                score += 3
            if query_lower in summary.file_path.lower():
                score += 2

            if score > 0:
                matches.append((score, summary))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:limit]]

    def get_impact_analysis(self, symbol_id: str) -> dict:
        """Get pre-computed impact analysis for a symbol."""
        summary = self._summaries.get(symbol_id)
        if not summary:
            return {"error": "Symbol not found"}

        return {
            "symbol": summary.symbol_name,
            "file": summary.file_path,
            "impact_score": summary.impact_score,
            "severity": (
                "high" if summary.impact_score > 0.7
                else "medium" if summary.impact_score > 0.3
                else "low"
            ),
            "affected_files": summary.impact_files,
            "dependents": summary.dependents,
            "callers": summary.callers,
        }

    def clear(self) -> None:
        """Clear all summaries."""
        self._summaries = {}
        if self.summaries_path.exists():
            self.summaries_path.unlink()
