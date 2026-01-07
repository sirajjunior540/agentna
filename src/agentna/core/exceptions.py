"""Custom exceptions for AgentNA."""


class AgentNAError(Exception):
    """Base exception for all AgentNA errors."""

    pass


class ProjectNotFoundError(AgentNAError):
    """Raised when a project's .agentna directory is not found."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"No AgentNA project found at {path}. Run 'agent init' to initialize.")


class ConfigError(AgentNAError):
    """Raised when there's an error with configuration."""

    pass


class IndexError(AgentNAError):
    """Raised when there's an error with indexing."""

    pass


class MemoryError(AgentNAError):
    """Raised when there's an error with the memory store."""

    pass


class LLMError(AgentNAError):
    """Raised when there's an error with LLM providers."""

    pass


class LLMConnectionError(LLMError):
    """Raised when unable to connect to LLM provider."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when LLM rate limit is exceeded."""

    pass
