"""Impact analysis for code changes."""

from dataclasses import dataclass
from pathlib import Path

from agentna.memory.hybrid_store import HybridStore
from agentna.memory.models import RelationType


@dataclass
class ImpactResult:
    """Result of impact analysis."""

    changed_files: list[str]
    changed_symbols: list[str]
    directly_affected: list[str]
    transitively_affected: list[str]
    affected_files: list[str]
    impact_score: float
    severity: str  # low, medium, high, critical
    risk_factors: list[str]
    recommendations: list[str]


class ImpactAnalyzer:
    """Analyzes the impact of code changes."""

    def __init__(self, store: HybridStore) -> None:
        """
        Initialize the impact analyzer.

        Args:
            store: The hybrid memory store
        """
        self.store = store

    def analyze_files(
        self,
        file_paths: list[str],
        max_depth: int = 3,
    ) -> ImpactResult:
        """
        Analyze the impact of changes to specified files.

        Args:
            file_paths: List of changed file paths
            max_depth: Maximum depth for dependency traversal

        Returns:
            ImpactResult with analysis
        """
        changed_symbols: set[str] = set()
        directly_affected: set[str] = set()
        transitively_affected: set[str] = set()
        affected_files: set[str] = set()
        risk_factors: list[str] = []

        # Get all symbols in changed files
        for file_path in file_paths:
            nodes = self.store.graph.get_nodes_by_file(file_path)
            for node in nodes:
                changed_symbols.add(node.id)

                # Get direct dependents
                deps = self.store.graph.get_dependents(node.id, max_depth=1)
                directly_affected.update(deps)

                # Get transitive dependents
                trans_deps = self.store.graph.get_dependents(node.id, max_depth=max_depth)
                transitively_affected.update(set(trans_deps) - set(deps) - {node.id})

        # Get affected files
        for symbol_id in directly_affected | transitively_affected:
            node = self.store.graph.get_node(symbol_id)
            if node and node.file_path and node.file_path not in file_paths:
                affected_files.add(node.file_path)

        # Calculate impact score
        impact_score = self._calculate_impact_score(
            len(file_paths),
            len(changed_symbols),
            len(directly_affected),
            len(transitively_affected),
        )

        # Determine severity
        severity = self._determine_severity(impact_score)

        # Identify risk factors
        risk_factors = self._identify_risk_factors(
            file_paths,
            changed_symbols,
            directly_affected,
            transitively_affected,
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            severity,
            risk_factors,
            len(affected_files),
        )

        return ImpactResult(
            changed_files=file_paths,
            changed_symbols=list(changed_symbols),
            directly_affected=list(directly_affected),
            transitively_affected=list(transitively_affected),
            affected_files=list(affected_files),
            impact_score=impact_score,
            severity=severity,
            risk_factors=risk_factors,
            recommendations=recommendations,
        )

    def analyze_symbols(
        self,
        symbol_ids: list[str],
        max_depth: int = 3,
    ) -> ImpactResult:
        """
        Analyze the impact of changes to specified symbols.

        Args:
            symbol_ids: List of changed symbol IDs
            max_depth: Maximum depth for dependency traversal

        Returns:
            ImpactResult with analysis
        """
        # Get file paths from symbols
        file_paths: set[str] = set()
        for symbol_id in symbol_ids:
            node = self.store.graph.get_node(symbol_id)
            if node and node.file_path:
                file_paths.add(node.file_path)

        return self.analyze_files(list(file_paths), max_depth)

    def get_dependency_chain(
        self,
        symbol_id: str,
        direction: str = "dependents",
        max_depth: int = 5,
    ) -> list[list[str]]:
        """
        Get the dependency chain for a symbol.

        Args:
            symbol_id: The symbol to analyze
            direction: "dependents" or "dependencies"
            max_depth: Maximum chain depth

        Returns:
            List of dependency chains (paths from symbol to affected items)
        """
        chains: list[list[str]] = []

        if direction == "dependents":
            dependents = self.store.graph.get_dependents(symbol_id, max_depth)
            for dep in dependents:
                path = self.store.graph.find_path(symbol_id, dep)
                if path:
                    chains.append(path)
        else:
            dependencies = self.store.graph.get_dependencies(symbol_id, max_depth)
            for dep in dependencies:
                path = self.store.graph.find_path(symbol_id, dep)
                if path:
                    chains.append(path)

        return chains

    def get_critical_paths(
        self,
        file_paths: list[str],
        max_paths: int = 10,
    ) -> list[dict]:
        """
        Get the most critical dependency paths affected by changes.

        Args:
            file_paths: Changed file paths
            max_paths: Maximum number of paths to return

        Returns:
            List of critical path information
        """
        critical_paths: list[dict] = []

        for file_path in file_paths:
            nodes = self.store.graph.get_nodes_by_file(file_path)
            for node in nodes:
                dependents = self.store.graph.get_dependents(node.id, max_depth=5)
                for dep in dependents[:max_paths]:
                    path = self.store.graph.find_path(node.id, dep)
                    if path and len(path) > 1:
                        dep_node = self.store.graph.get_node(dep)
                        critical_paths.append({
                            "source": node.id,
                            "target": dep,
                            "target_file": dep_node.file_path if dep_node else None,
                            "path": path,
                            "depth": len(path) - 1,
                        })

        # Sort by depth (shorter paths are more critical)
        critical_paths.sort(key=lambda x: x["depth"])
        return critical_paths[:max_paths]

    def _calculate_impact_score(
        self,
        num_files: int,
        num_symbols: int,
        num_direct: int,
        num_transitive: int,
    ) -> float:
        """Calculate impact score from 0 to 1."""
        # Weighted formula based on scope of changes
        file_weight = min(num_files / 10, 0.3)
        symbol_weight = min(num_symbols / 20, 0.2)
        direct_weight = min(num_direct / 30, 0.3)
        transitive_weight = min(num_transitive / 50, 0.2)

        return min(1.0, file_weight + symbol_weight + direct_weight + transitive_weight)

    def _determine_severity(self, score: float) -> str:
        """Determine severity level from impact score."""
        if score >= 0.8:
            return "critical"
        elif score >= 0.6:
            return "high"
        elif score >= 0.3:
            return "medium"
        return "low"

    def _identify_risk_factors(
        self,
        file_paths: list[str],
        changed_symbols: set[str],
        directly_affected: set[str],
        transitively_affected: set[str],
    ) -> list[str]:
        """Identify risk factors for the changes."""
        risks = []

        if len(file_paths) > 5:
            risks.append(f"Large change spanning {len(file_paths)} files")

        if len(changed_symbols) > 20:
            risks.append(f"Many symbols modified ({len(changed_symbols)})")

        if len(directly_affected) > 10:
            risks.append(f"High number of direct dependents ({len(directly_affected)})")

        if len(transitively_affected) > 30:
            risks.append(f"Large transitive impact ({len(transitively_affected)} symbols)")

        # Check for core/critical files
        critical_patterns = ["__init__", "main", "config", "base", "core", "utils"]
        for file_path in file_paths:
            if any(p in file_path.lower() for p in critical_patterns):
                risks.append(f"Changes to core file: {file_path}")
                break

        return risks

    def _generate_recommendations(
        self,
        severity: str,
        risk_factors: list[str],
        num_affected_files: int,
    ) -> list[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        if severity in ("high", "critical"):
            recommendations.append("Consider breaking this change into smaller PRs")
            recommendations.append("Ensure comprehensive test coverage for affected areas")

        if num_affected_files > 10:
            recommendations.append(f"Review all {num_affected_files} affected files before merging")

        if any("core" in r.lower() for r in risk_factors):
            recommendations.append("Changes to core modules require extra review")

        if severity == "critical":
            recommendations.append("Consider a staged rollout or feature flag")

        if not recommendations:
            recommendations.append("Standard review process should be sufficient")

        return recommendations
