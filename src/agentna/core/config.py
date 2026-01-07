"""Configuration management for AgentNA."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agentna.core.constants import (
    DEFAULT_DEBOUNCE_MS,
    DEFAULT_IGNORE_PATTERNS,
    DEFAULT_INCLUDE_PATTERNS,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    EMBEDDING_MODEL,
    GLOBAL_CONFIG_DIR,
    GLOBAL_CONFIG_FILE,
    MAX_FILE_SIZE_KB,
)
from agentna.core.exceptions import ConfigError


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    preferred_provider: str = Field("ollama", description="'ollama' or 'claude'")
    ollama_model: str = Field(DEFAULT_OLLAMA_MODEL)
    ollama_embed_model: str = Field(EMBEDDING_MODEL)
    ollama_host: str = Field(DEFAULT_OLLAMA_HOST)
    claude_model: str = Field("claude-sonnet-4-20250514")
    anthropic_api_key: str | None = Field(None, description="Anthropic API key (or use env var)")
    fallback_enabled: bool = Field(True, description="Fall back to Claude if Ollama fails")


class IndexingConfig(BaseModel):
    """Indexing configuration."""

    include_patterns: list[str] = Field(default_factory=lambda: DEFAULT_INCLUDE_PATTERNS.copy())
    exclude_patterns: list[str] = Field(default_factory=lambda: DEFAULT_IGNORE_PATTERNS.copy())
    max_file_size_kb: int = Field(MAX_FILE_SIZE_KB)
    chunk_by_symbols: bool = Field(True, description="Chunk by functions/classes vs fixed size")
    include_docstrings: bool = Field(True)
    include_comments: bool = Field(False)


class WatcherConfig(BaseModel):
    """File watcher configuration."""

    enabled: bool = Field(True)
    debounce_ms: int = Field(DEFAULT_DEBOUNCE_MS)
    recursive: bool = Field(True)
    ignore_hidden: bool = Field(True)


class GraphConfig(BaseModel):
    """Knowledge graph configuration."""

    track_imports: bool = Field(True)
    track_calls: bool = Field(True)
    track_inheritance: bool = Field(True)
    max_depth: int = Field(10)


class ProjectConfig(BaseModel):
    """Project-level configuration stored in .agentna/config.yaml."""

    version: str = Field("1.0")
    name: str | None = Field(None, description="Project name (defaults to directory name)")
    description: str | None = Field(None)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    watcher: WatcherConfig = Field(default_factory=WatcherConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)

    @classmethod
    def load(cls, path: Path) -> "ProjectConfig":
        """Load configuration from a YAML file."""
        if not path.exists():
            return cls()
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            return cls.model_validate(data)
        except Exception as e:
            raise ConfigError(f"Failed to load config from {path}: {e}") from e

    def save(self, path: Path) -> None:
        """Save configuration to a YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w") as f:
                yaml.dump(
                    self.model_dump(exclude_none=True, exclude_defaults=False),
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                )
        except Exception as e:
            raise ConfigError(f"Failed to save config to {path}: {e}") from e


class GlobalConfig(BaseModel):
    """Global configuration stored in ~/.agentna/config.yaml."""

    version: str = Field("1.0")
    default_llm: LLMConfig = Field(default_factory=LLMConfig)
    telemetry_enabled: bool = Field(False)
    auto_update_check: bool = Field(True)
    projects: dict[str, str] = Field(
        default_factory=dict, description="Known projects: name -> path"
    )

    @classmethod
    def load(cls) -> "GlobalConfig":
        """Load global configuration."""
        if not GLOBAL_CONFIG_FILE.exists():
            return cls()
        try:
            with open(GLOBAL_CONFIG_FILE) as f:
                data = yaml.safe_load(f) or {}
            return cls.model_validate(data)
        except Exception as e:
            raise ConfigError(f"Failed to load global config: {e}") from e

    def save(self) -> None:
        """Save global configuration."""
        GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(GLOBAL_CONFIG_FILE, "w") as f:
                yaml.dump(
                    self.model_dump(exclude_none=True),
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                )
        except Exception as e:
            raise ConfigError(f"Failed to save global config: {e}") from e

    def register_project(self, name: str, path: str) -> None:
        """Register a project in the global config."""
        self.projects[name] = path
        self.save()

    def unregister_project(self, name: str) -> None:
        """Unregister a project from the global config."""
        if name in self.projects:
            del self.projects[name]
            self.save()


def merge_configs(project: ProjectConfig, global_config: GlobalConfig) -> dict[str, Any]:
    """Merge project config with global defaults."""
    merged = global_config.default_llm.model_dump()
    merged.update(project.llm.model_dump(exclude_unset=True))
    return merged
