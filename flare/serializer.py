"""
Function serialization for remote execution
"""

import inspect
import ast
import hashlib
from typing import Any
from collections.abc import Callable as CallableType


class FunctionSerializer:
    """
    Serializes Python functions for remote execution.
    Handles:
    - Function source code extraction
    - Import statement detection
    - Closure variable capture
    """

    @staticmethod
    def serialize(fn: CallableType[..., object]) -> dict[str, Any]:  # type: ignore[misc]
        """
        Serialize a function to be executed remotely.

        Returns:
            {
                'code': str,           # Complete executable code
                'name': str,           # Function name
                'id': str,             # Unique function ID (hash)
                'imports': List[str],  # Required imports
            }
        """
        # Extract source code
        try:
            source = inspect.getsource(fn)
        except OSError as e:
            raise ValueError(
                (
                    f"Cannot serialize function '{fn.__name__}': {e}. "
                    "Functions must be defined in a file, not interactively."
                )
            )

        # Remove decorator lines (e.g., @app.function())
        source_lines = source.split("\n")
        cleaned_lines = []
        for line in source_lines:
            stripped = line.strip()
            # Skip decorator lines
            if (
                stripped.startswith("@")
                and not stripped.startswith("@staticmethod")
                and not stripped.startswith("@classmethod")
            ):
                continue
            cleaned_lines.append(line)

        # Remove common leading indentation but preserve relative indentation
        cleaned_source = "\n".join(cleaned_lines)
        # Use textwrap.dedent to remove common leading whitespace while preserving structure
        import textwrap

        cleaned_source = textwrap.dedent(cleaned_source)

        # Parse AST to find imports needed by the function
        # We include module-level imports but filter out 'flare' imports
        # since those are only needed for decorators, not for execution
        try:
            imports = FunctionSerializer._extract_function_imports(fn)
        except Exception:
            imports = []

        # Generate unique function ID (hash of source)
        function_id = (
            f"{fn.__name__}_{hashlib.sha256(cleaned_source.encode()).hexdigest()[:8]}"
        )

        # Build complete executable code
        code_parts = []

        # Add imports
        if imports:
            code_parts.extend(imports)
            code_parts.append("")  # Blank line after imports

        # Add function definition
        code_parts.append(cleaned_source)

        return {
            "code": "\n".join(code_parts),
            "name": fn.__name__,
            "id": function_id,
            "imports": imports,
        }

    @staticmethod
    def _extract_function_imports(fn: CallableType[..., object]) -> list[str]:
        """
        Extract import statements needed by the function.

        This looks at the entire module to find all imports, but filters out
        imports that are only used for decorators (like 'import flare').
        """
        imports = []
        try:
            # Get the full source file of the module containing this function
            module = inspect.getmodule(fn)
            if not module:
                return []
            module_source = inspect.getsource(module)
            tree = ast.parse(module_source)

            # Extract all module-level imports
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Skip flare imports (only needed for decorators)
                        if alias.name == "flare" or alias.name.startswith("flare."):
                            continue
                        if alias.asname:
                            imports.append(f"import {alias.name} as {alias.asname}")
                        else:
                            imports.append(f"import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    # Skip flare imports
                    if node.module and (
                        node.module == "flare" or node.module.startswith("flare.")
                    ):
                        continue

                    module = node.module or ""
                    names = ", ".join(
                        f"{alias.name} as {alias.asname}"
                        if alias.asname
                        else alias.name
                        for alias in node.names
                    )
                    if node.level:  # Relative import
                        dots = "." * node.level
                        imports.append(f"from {dots}{module} import {names}")
                    else:
                        imports.append(f"from {module} import {names}")
        except Exception:
            pass

        # Deduplicate while preserving order
        seen = set()
        unique_imports = []
        for imp in imports:
            if imp not in seen:
                seen.add(imp)
                unique_imports.append(imp)

        return unique_imports

    @staticmethod
    def _extract_imports(source: str) -> list[str]:
        """Extract import statements from source code"""
        imports = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.asname:
                            imports.append(f"import {alias.name} as {alias.asname}")
                        else:
                            imports.append(f"import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    names = ", ".join(
                        f"{alias.name} as {alias.asname}"
                        if alias.asname
                        else alias.name
                        for alias in node.names
                    )
                    if node.level:  # Relative import
                        dots = "." * node.level
                        imports.append(f"from {dots}{module} import {names}")
                    else:
                        imports.append(f"from {module} import {names}")
        except SyntaxError:
            pass  # Ignore syntax errors, just skip imports

        # Deduplicate while preserving order
        seen = set()
        unique_imports = []
        for imp in imports:
            if imp not in seen:
                seen.add(imp)
                unique_imports.append(imp)

        return unique_imports
