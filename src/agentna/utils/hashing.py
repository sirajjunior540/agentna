"""Hashing utilities for AgentNA."""

import hashlib
from pathlib import Path


def hash_content(content: str | bytes) -> str:
    """
    Generate a SHA256 hash of content.

    Args:
        content: String or bytes to hash

    Returns:
        Hex digest of the hash
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def hash_file(path: Path | str) -> str:
    """
    Generate a SHA256 hash of a file's contents.

    Args:
        path: Path to the file

    Returns:
        Hex digest of the hash
    """
    path = Path(path)
    hasher = hashlib.sha256()

    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)

    return hasher.hexdigest()


def generate_chunk_id(file_path: str, line_start: int, line_end: int) -> str:
    """
    Generate a unique ID for a code chunk.

    Args:
        file_path: Relative path to the file
        line_start: Starting line number
        line_end: Ending line number

    Returns:
        Unique chunk ID
    """
    return f"{file_path}:{line_start}:{line_end}"


def generate_symbol_id(symbol_type: str, file_path: str, name: str) -> str:
    """
    Generate a unique ID for a code symbol.

    Args:
        symbol_type: Type of symbol (function, class, etc.)
        file_path: Relative path to the file
        name: Symbol name

    Returns:
        Unique symbol ID
    """
    return f"{symbol_type}:{file_path}:{name}"
