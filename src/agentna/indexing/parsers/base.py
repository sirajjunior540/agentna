"""Base parser interface for code parsing."""

from abc import ABC, abstractmethod
from pathlib import Path

from agentna.memory.models import CodeChunk, Relationship


class BaseParser(ABC):
    """Abstract base class for language-specific parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """List of file extensions this parser supports."""
        ...

    @property
    @abstractmethod
    def language(self) -> str:
        """Language name for this parser."""
        ...

    @abstractmethod
    def parse(self, file_path: Path, content: str) -> list[CodeChunk]:
        """
        Parse a file and extract code chunks.

        Args:
            file_path: Path to the file (relative to project root)
            content: File content as string

        Returns:
            List of extracted code chunks
        """
        ...

    @abstractmethod
    def extract_relationships(
        self,
        file_path: Path,
        content: str,
        chunks: list[CodeChunk],
    ) -> list[Relationship]:
        """
        Extract relationships from parsed code.

        Args:
            file_path: Path to the file
            content: File content
            chunks: Previously extracted chunks

        Returns:
            List of relationships between symbols
        """
        ...

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file."""
        return file_path.suffix.lower() in self.supported_extensions
