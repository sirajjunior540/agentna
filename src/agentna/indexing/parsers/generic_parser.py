"""Generic parser for files without specialized parsers."""

from pathlib import Path

from agentna.core.constants import LANGUAGE_EXTENSIONS, MAX_CHUNK_SIZE_CHARS
from agentna.indexing.parsers.base import BaseParser
from agentna.memory.models import CodeChunk, Relationship, SymbolType
from agentna.utils.hashing import generate_chunk_id, hash_content


class GenericParser(BaseParser):
    """Generic parser that creates file-level chunks for any text file."""

    @property
    def supported_extensions(self) -> list[str]:
        # Support all known extensions
        return list(LANGUAGE_EXTENSIONS.keys())

    @property
    def language(self) -> str:
        return "generic"

    def get_language(self, file_path: Path) -> str:
        """Get language for a specific file."""
        return LANGUAGE_EXTENSIONS.get(file_path.suffix.lower(), "text")

    def parse(self, file_path: Path, content: str) -> list[CodeChunk]:
        """Parse file and create chunks based on size."""
        chunks: list[CodeChunk] = []
        lines = content.split("\n")
        language = self.get_language(file_path)

        # If file is small enough, create single chunk
        if len(content) <= MAX_CHUNK_SIZE_CHARS:
            chunks.append(
                CodeChunk(
                    id=generate_chunk_id(str(file_path), 1, len(lines)),
                    file_path=str(file_path),
                    language=language,
                    symbol_name=file_path.stem,
                    symbol_type=SymbolType.FILE,
                    line_start=1,
                    line_end=len(lines),
                    content=content,
                    content_hash=hash_content(content),
                )
            )
            return chunks

        # Split into multiple chunks
        current_chunk_lines: list[str] = []
        current_chunk_start = 1
        current_size = 0

        for i, line in enumerate(lines, 1):
            line_size = len(line) + 1  # +1 for newline

            if current_size + line_size > MAX_CHUNK_SIZE_CHARS and current_chunk_lines:
                # Save current chunk
                chunk_content = "\n".join(current_chunk_lines)
                chunks.append(
                    CodeChunk(
                        id=generate_chunk_id(str(file_path), current_chunk_start, i - 1),
                        file_path=str(file_path),
                        language=language,
                        symbol_type=SymbolType.FILE,
                        line_start=current_chunk_start,
                        line_end=i - 1,
                        content=chunk_content,
                        content_hash=hash_content(chunk_content),
                    )
                )

                # Start new chunk
                current_chunk_lines = [line]
                current_chunk_start = i
                current_size = line_size
            else:
                current_chunk_lines.append(line)
                current_size += line_size

        # Save last chunk
        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            chunks.append(
                CodeChunk(
                    id=generate_chunk_id(str(file_path), current_chunk_start, len(lines)),
                    file_path=str(file_path),
                    language=language,
                    symbol_type=SymbolType.FILE,
                    line_start=current_chunk_start,
                    line_end=len(lines),
                    content=chunk_content,
                    content_hash=hash_content(chunk_content),
                )
            )

        return chunks

    def extract_relationships(
        self,
        file_path: Path,
        content: str,
        chunks: list[CodeChunk],
    ) -> list[Relationship]:
        """Generic parser doesn't extract relationships."""
        return []


class MarkdownParser(BaseParser):
    """Parser for Markdown files that chunks by sections."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".md", ".markdown", ".rst"]

    @property
    def language(self) -> str:
        return "markdown"

    def parse(self, file_path: Path, content: str) -> list[CodeChunk]:
        """Parse Markdown file and chunk by sections."""
        chunks: list[CodeChunk] = []
        lines = content.split("\n")

        # Track sections by headers
        sections: list[tuple[int, int, str, list[str]]] = []  # (start, end, title, content)
        current_section_start = 0
        current_section_title = file_path.stem
        current_section_content: list[str] = []

        for i, line in enumerate(lines):
            # Check for markdown header
            if line.startswith("#"):
                # Save previous section
                if current_section_content:
                    sections.append((
                        current_section_start,
                        i - 1,
                        current_section_title,
                        current_section_content,
                    ))

                # Start new section
                current_section_start = i
                current_section_title = line.lstrip("#").strip()
                current_section_content = [line]
            else:
                current_section_content.append(line)

        # Save last section
        if current_section_content:
            sections.append((
                current_section_start,
                len(lines) - 1,
                current_section_title,
                current_section_content,
            ))

        # Create chunks from sections
        for start, end, title, section_content in sections:
            content_str = "\n".join(section_content)
            if len(content_str.strip()) > 0:  # Skip empty sections
                chunks.append(
                    CodeChunk(
                        id=generate_chunk_id(str(file_path), start + 1, end + 1),
                        file_path=str(file_path),
                        language=self.language,
                        symbol_name=title,
                        symbol_type=SymbolType.FILE,
                        line_start=start + 1,
                        line_end=end + 1,
                        content=content_str,
                        content_hash=hash_content(content_str),
                    )
                )

        # If no sections found, create single chunk
        if not chunks:
            chunks.append(
                CodeChunk(
                    id=generate_chunk_id(str(file_path), 1, len(lines)),
                    file_path=str(file_path),
                    language=self.language,
                    symbol_name=file_path.stem,
                    symbol_type=SymbolType.FILE,
                    line_start=1,
                    line_end=len(lines),
                    content=content,
                    content_hash=hash_content(content),
                )
            )

        return chunks

    def extract_relationships(
        self,
        file_path: Path,
        content: str,
        chunks: list[CodeChunk],
    ) -> list[Relationship]:
        """Markdown parser doesn't extract code relationships."""
        return []
