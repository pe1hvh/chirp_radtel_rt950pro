#!/usr/bin/env python3
"""Check that every module, class and function has a docstring, nested ones too.

pydocstyle only checks names it considers public (for a module with
``__all__``: the names in it), pydoclint skips objects without a docstring,
and pylint's ``missing-function-docstring`` skips functions nested inside
functions.
This tool walks the syntax tree (:mod:`ast`) of each file and reports every
module, class, function and method without a docstring, wherever it is
defined, nested functions and classes inside ``try``/``except`` blocks
included. Lambdas are skipped (a lambda cannot have a docstring).

Structure:

1. Check: find the objects without a docstring.
2. Command line: argument parsing and ``main``.

Usage (from the repository root; no dependencies):

    python3 tools/check_docstrings.py radtel_rt950pro.py tools/*.py docs/build.py

Exit status 0 when everything is documented, 1 when something is missing
(one line per object: ``file:line: kind name``), 2 on invalid arguments.
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import List, Optional, Sequence

__all__ = ["missing_docstrings", "main"]

# ===========================================================================
# 1. Check
# ===========================================================================

_KINDS = {
    ast.ClassDef: "class",
    ast.FunctionDef: "function",
    ast.AsyncFunctionDef: "function",
}
"""Node types that must have a docstring, with the word used in the report."""


def missing_docstrings(source: str, filename: str = "<string>") -> List[str]:
    """List the module, classes and functions in ``source`` without a docstring.

    Args:
        source: Python source text.
        filename: Name used in the report lines and in syntax errors.

    Returns:
        One line per object without a docstring, in line order, e.g.
        ``build.py:261: function add``; the module itself is reported as
        ``build.py:1: module``. Empty when everything is documented.

    Raises:
        SyntaxError: If ``source`` is not valid Python.
    """
    tree = ast.parse(source, filename=filename)
    missing = []
    if ast.get_docstring(tree) is None:
        missing.append((1, f"{filename}:1: module"))
    for node in ast.walk(tree):
        kind = _KINDS.get(type(node))
        if kind and ast.get_docstring(node) is None:
            missing.append((node.lineno, f"{filename}:{node.lineno}: {kind} {node.name}"))
    return [line for _, line in sorted(missing)]


# ===========================================================================
# 2. Command line
# ===========================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Check the files on the command line and print what is missing.

    Args:
        argv: File paths; ``None`` uses ``sys.argv[1:]``.

    Returns:
        Exit status: 0 when every object has a docstring, 1 otherwise or
        when a file cannot be read, decoded as UTF-8 or parsed.

    Raises:
        SystemExit: From argparse: code 2 when no file is given, code 0 for
            ``--help``.
    """
    parser = argparse.ArgumentParser(
        description="Report modules, classes and functions without a docstring."
    )
    parser.add_argument("files", nargs="+", help="Python files to check")
    args = parser.parse_args(argv)
    problems = []
    for name in args.files:
        try:
            problems += missing_docstrings(Path(name).read_text(encoding="utf-8"), name)
        except (OSError, SyntaxError, ValueError) as exc:  # ValueError: not UTF-8
            problems.append(f"{name}: cannot check: {exc}")
    for line in problems:
        print(line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
