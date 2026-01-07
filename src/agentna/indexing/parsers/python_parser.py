"""Python code parser using AST."""

import ast
from pathlib import Path
from typing import Any

from agentna.indexing.parsers.base import BaseParser
from agentna.memory.models import CodeChunk, Relationship, RelationType, SymbolType
from agentna.utils.hashing import generate_chunk_id, generate_symbol_id, hash_content


class PythonParser(BaseParser):
    """Parser for Python code using the ast module."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".py", ".pyi"]

    @property
    def language(self) -> str:
        return "python"

    def parse(self, file_path: Path, content: str) -> list[CodeChunk]:
        """Parse Python file and extract code chunks."""
        chunks: list[CodeChunk] = []
        lines = content.split("\n")

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # If parsing fails, create a single file-level chunk
            return [self._create_file_chunk(file_path, content, lines)]

        # Add file-level chunk
        chunks.append(self._create_file_chunk(file_path, content, lines))

        # Extract classes and functions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                chunks.append(self._parse_class(file_path, node, lines))
                # Also extract methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        chunks.append(
                            self._parse_function(file_path, item, lines, parent=node.name)
                        )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Top-level functions only (not methods)
                if not self._is_method(node, tree):
                    chunks.append(self._parse_function(file_path, node, lines))

        return chunks

    def extract_relationships(
        self,
        file_path: Path,
        content: str,
        chunks: list[CodeChunk],
    ) -> list[Relationship]:
        """Extract relationships from Python code."""
        relationships: list[Relationship] = []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return relationships

        file_id = f"file:{file_path}"

        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    relationships.append(
                        Relationship(
                            source_id=file_id,
                            target_id=f"module:{alias.name}",
                            relation_type=RelationType.IMPORTS,
                            line_number=node.lineno,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        relationships.append(
                            Relationship(
                                source_id=file_id,
                                target_id=f"module:{node.module}.{alias.name}",
                                relation_type=RelationType.IMPORTS,
                                line_number=node.lineno,
                            )
                        )

        # Extract class inheritance
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_id = generate_symbol_id("class", str(file_path), node.name)
                for base in node.bases:
                    base_name = self._get_name(base)
                    if base_name:
                        relationships.append(
                            Relationship(
                                source_id=class_id,
                                target_id=f"class:{base_name}",
                                relation_type=RelationType.INHERITS,
                                line_number=node.lineno,
                            )
                        )

        # Extract function calls (simplified)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = generate_symbol_id("function", str(file_path), node.name)

                # Find calls within this function
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_name = self._get_call_name(child)
                        if call_name:
                            relationships.append(
                                Relationship(
                                    source_id=func_id,
                                    target_id=f"function:{call_name}",
                                    relation_type=RelationType.CALLS,
                                    line_number=child.lineno if hasattr(child, "lineno") else None,
                                )
                            )

        # Add contains relationships
        for chunk in chunks:
            if chunk.symbol_type != SymbolType.FILE:
                relationships.append(
                    Relationship(
                        source_id=file_id,
                        target_id=chunk.id,
                        relation_type=RelationType.CONTAINS,
                    )
                )

        return relationships

    def _create_file_chunk(
        self, file_path: Path, content: str, lines: list[str]
    ) -> CodeChunk:
        """Create a file-level chunk."""
        # Extract module docstring
        docstring = None
        try:
            tree = ast.parse(content)
            docstring = ast.get_docstring(tree)
        except SyntaxError:
            pass

        return CodeChunk(
            id=generate_chunk_id(str(file_path), 1, len(lines)),
            file_path=str(file_path),
            language=self.language,
            symbol_name=file_path.stem,
            symbol_type=SymbolType.FILE,
            line_start=1,
            line_end=len(lines),
            content=content[:2000] if len(content) > 2000 else content,  # Limit size
            docstring=docstring,
            content_hash=hash_content(content),
        )

    def _parse_class(
        self, file_path: Path, node: ast.ClassDef, lines: list[str]
    ) -> CodeChunk:
        """Parse a class definition."""
        line_start = node.lineno
        line_end = self._get_end_line(node, lines)

        # Get class content
        content = "\n".join(lines[line_start - 1 : line_end])

        # Get docstring
        docstring = ast.get_docstring(node)

        # Build signature
        bases = [self._get_name(b) for b in node.bases if self._get_name(b)]
        signature = f"class {node.name}"
        if bases:
            signature += f"({', '.join(bases)})"

        return CodeChunk(
            id=generate_symbol_id("class", str(file_path), node.name),
            file_path=str(file_path),
            language=self.language,
            symbol_name=node.name,
            symbol_type=SymbolType.CLASS,
            line_start=line_start,
            line_end=line_end,
            content=content,
            docstring=docstring,
            signature=signature,
            content_hash=hash_content(content),
        )

    def _parse_function(
        self,
        file_path: Path,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
        parent: str | None = None,
    ) -> CodeChunk:
        """Parse a function or method definition."""
        line_start = node.lineno
        line_end = self._get_end_line(node, lines)

        # Get function content
        content = "\n".join(lines[line_start - 1 : line_end])

        # Get docstring
        docstring = ast.get_docstring(node)

        # Build signature
        args = self._get_function_args(node)
        returns = self._get_return_annotation(node)

        async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        signature = f"{async_prefix}def {node.name}({args})"
        if returns:
            signature += f" -> {returns}"

        symbol_type = SymbolType.METHOD if parent else SymbolType.FUNCTION

        # Include parent in symbol name for methods to avoid collisions
        symbol_full_name = f"{parent}.{node.name}" if parent else node.name

        return CodeChunk(
            id=generate_symbol_id(symbol_type.value, str(file_path), symbol_full_name),
            file_path=str(file_path),
            language=self.language,
            symbol_name=node.name,
            symbol_type=symbol_type,
            line_start=line_start,
            line_end=line_end,
            content=content,
            docstring=docstring,
            signature=signature,
            parent_symbol=parent,
            content_hash=hash_content(content),
        )

    def _get_end_line(self, node: ast.AST, lines: list[str]) -> int:
        """Get the end line of an AST node."""
        if hasattr(node, "end_lineno") and node.end_lineno:
            return node.end_lineno

        # Fallback: find the last line with content
        if hasattr(node, "body") and node.body:
            last_child = node.body[-1]
            return self._get_end_line(last_child, lines)

        return getattr(node, "lineno", len(lines))

    def _get_function_args(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Get function arguments as a string."""
        args = []

        # Regular arguments
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._get_name(arg.annotation)}"
            args.append(arg_str)

        # *args
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")

        # **kwargs
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        return ", ".join(args)

    def _get_return_annotation(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
        """Get return type annotation."""
        if node.returns:
            return self._get_name(node.returns)
        return None

    def _get_name(self, node: ast.AST) -> str | None:
        """Get the name from various AST node types."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_name(node.value)
            if value:
                return f"{value}.{node.attr}"
            return node.attr
        elif isinstance(node, ast.Subscript):
            value = self._get_name(node.value)
            slice_val = self._get_name(node.slice)
            if value and slice_val:
                return f"{value}[{slice_val}]"
            return value
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Tuple):
            elements = [self._get_name(e) for e in node.elts if self._get_name(e)]
            return ", ".join(elements)
        return None

    def _get_call_name(self, node: ast.Call) -> str | None:
        """Get the name of a called function."""
        return self._get_name(node.func)

    def _is_method(self, node: ast.FunctionDef | ast.AsyncFunctionDef, tree: ast.Module) -> bool:
        """Check if a function is a method (inside a class)."""
        for class_node in ast.walk(tree):
            if isinstance(class_node, ast.ClassDef):
                if node in class_node.body:
                    return True
        return False
