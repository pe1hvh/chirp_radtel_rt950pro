#!/usr/bin/env python3
"""Build the API documentation of ``radtel_rt950pro.py``, grouped by driver layer.

pdoc renders the Google-style docstrings; this script adds the structure
that pdoc does not know about:

* **Layers and sections.** The driver source is divided by banner
  comments::

      # ====================
      # 1. Channel records          <- layer
      # ====================
      # --------------------
      # Encoding helpers            <- section within the current layer
      # --------------------

  Every module-level class, function and constant is assigned to the layer
  and section in which it is defined. The menu and the page follow that
  order, so the documentation mirrors the program structure. A new class
  lands in the right layer automatically.

* **Public and private.** At module level an object is public when it is
  listed in ``__all__``; inside a class a member is public unless its name
  starts with one underscore (dunder methods such as ``__init__`` are
  public). Private objects are documented too and marked with a closed
  lock; public ones get an open lock.

* **Exclusions.** Code inside module-level ``try``/``except`` blocks is not
  documented: those blocks only hold the optional imports and the CHIRP
  stand-in classes used when CHIRP is not installed.

Usage (from the repository root)::

    pip install pdoc
    python docs/build.py            # writes the HTML to ./site
    python docs/build.py -o out     # other output directory

Only the standard library and pdoc are needed; CHIRP and pyserial are not.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdoc
import pdoc.render

ROOT = Path(__file__).resolve().parent.parent
"""Repository root (the directory that holds the driver)."""

MODULE = "radtel_rt950pro"
"""Name of the documented module."""

TEMPLATES = Path(__file__).resolve().parent / "templates"
"""Directory with the pdoc template overrides."""

_LAYER_RE = re.compile(r"#\s*(\d+)\.\s+(.+)")
"""Matches a layer title line such as ``# 1. Channel records``."""


def _banners(lines: List[str]) -> List[Tuple[int, int, str]]:
    """Find the layer and section banners in the source.

    A layer banner is a ``# N. Title`` line between two ``# ====`` rules; a
    section banner is a ``# Title`` line directly below a ``# ----`` rule.
    Trailing dashes after a section title are dropped.

    Args:
        lines: Source lines of the module.

    Returns:
        ``(line_number, level, title)`` tuples in source order; ``level`` is
        1 for a layer and 2 for a section. Line numbers are 1-based.
    """
    found = []
    for i in range(1, len(lines) - 1):
        above, line, below = lines[i - 1], lines[i], lines[i + 1]
        if above.startswith("# ====") and below.startswith("# ===="):
            found.append((i + 1, 1, line.lstrip("#").strip()))
        elif (above.startswith("# ----") and line.startswith("# ")
              and not line.startswith("# ---")):
            title = re.sub(r"\s*-+$", "", line[2:]).strip()
            found.append((i + 1, 2, title))
    return found


def _layer_descriptions(docstring: str) -> Dict[str, str]:
    """Read the one-line description of each layer from the module docstring.

    The module docstring lists the layers as ``N. Title: description``,
    possibly wrapped over several lines.

    Args:
        docstring: The module docstring.

    Returns:
        Mapping of layer number (as text) to its description, with Sphinx
        roles such as ``:class:`X``` reduced to ``X``.
    """
    result: Dict[str, str] = {}
    current: Optional[str] = None
    for raw in docstring.splitlines():
        line = raw.strip()
        match = re.match(r"(\d+)\.\s+[^:]+:\s*(.*)", line)
        if match:
            current = match.group(1)
            result[current] = match.group(2)
        elif current and line and raw.startswith("   "):
            result[current] += " " + line
        else:
            current = None
    for key, text in result.items():
        text = re.sub(r":\w+:`([^`]+)`", r"\1", text)
        result[key] = text.replace("``", "")
    return result


def _member_kind(node: ast.FunctionDef) -> str:
    """Classify a method definition.

    Args:
        node: A function definition inside a class body.

    Returns:
        ``"constructor"`` for ``__init__``, ``"property"`` for a method
        decorated with ``@property``, otherwise ``"method"``.
    """
    if node.name == "__init__":
        return "constructor"
    for deco in node.decorator_list:
        if isinstance(deco, ast.Name) and deco.id == "property":
            return "property"
    return "method"


def _member_is_public(name: str) -> bool:
    """Tell whether a class member is public.

    Args:
        name: Member name.

    Returns:
        False for names with one leading underscore; True for all other
        names, including dunder methods such as ``__init__``.
    """
    if name.startswith("__") and name.endswith("__"):
        return True
    return not name.startswith("_")


def _class_members(node: ast.ClassDef) -> List[dict]:
    """List the members defined in a class body, in source order.

    Collected are methods, class-level assignments (fields, Enum values,
    class constants) and instance attributes assigned as ``self.name`` in
    any method. Each name is listed once, at its first definition.

    Args:
        node: The class definition.

    Returns:
        Dicts with ``name``, ``kind`` (``constructor``, ``property``,
        ``method`` or ``field``) and ``public``.
    """
    members: Dict[str, dict] = {}

    def add(name: str, kind: str) -> None:
        if name not in members:
            members[name] = {"name": name, "kind": kind,
                             "public": _member_is_public(name)}

    for item in node.body:
        if isinstance(item, ast.FunctionDef):
            add(item.name, _member_kind(item))
        elif isinstance(item, (ast.Assign, ast.AnnAssign)):
            target = item.targets[0] if isinstance(item, ast.Assign) else item.target
            if isinstance(target, ast.Name):
                add(target.id, "field")
    for item in node.body:
        if not isinstance(item, ast.FunctionDef):
            continue
        for sub in ast.walk(item):
            if isinstance(sub, (ast.Assign, ast.AnnAssign)):
                targets = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
                for target in targets:
                    if (isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"):
                        add(target.attr, "field")
    return list(members.values())


def _locate(banners: List[Tuple[int, int, str]], line: int) -> Tuple[Optional[str], str]:
    """Find the layer and section that contain a source line.

    Args:
        banners: Result of :func:`_banners`.
        line: 1-based line number of a definition.

    Returns:
        ``(layer_title, section_title)``; the layer is ``None`` before the
        first layer banner, the section is empty before the first section
        banner of that layer.
    """
    layer, section = None, ""
    for number, level, title in banners:
        if number > line:
            break
        if level == 1:
            layer, section = title, ""
        else:
            section = title
    return layer, section


def _module_items(tree: ast.Module, public: set) -> List[Tuple[int, dict]]:
    """List the module-level classes, functions and constants.

    Code inside ``try``/``except`` and other compound statements is skipped;
    a name assigned twice is listed once, at its first definition.

    Args:
        tree: Parsed module.
        public: Names listed in ``__all__``.

    Returns:
        ``(line_number, item)`` pairs in source order; an item has ``name``,
        ``kind``, ``public`` and, for classes, ``members``.
    """
    items: List[Tuple[int, dict]] = []
    seen = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            item = {"name": node.name, "kind": "class",
                    "members": _class_members(node)}
        elif isinstance(node, ast.FunctionDef):
            item = {"name": node.name, "kind": "function"}
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if not isinstance(target, ast.Name) or target.id.startswith("__"):
                continue
            item = {"name": target.id, "kind": "constant"}
        else:
            continue  # imports, try/except blocks, expressions
        if item["name"] in seen:
            continue
        seen.add(item["name"])
        item["public"] = item["name"] in public
        items.append((node.lineno, item))
    return items


def _finish_layer(layer: dict) -> dict:
    """Sort the items of a layer and count them.

    Args:
        layer: A layer whose ``sections`` maps section title to items.

    Returns:
        The same layer with ``sections`` as a list of ``{"title", "items"}``
        (items ordered classes, functions, constants; public first) and
        ``counts`` (total, per kind, private).
    """
    order = {"class": 0, "function": 1, "constant": 2}
    sections = []
    all_items: List[dict] = []
    for title, section_items in layer["sections"].items():
        section_items.sort(key=lambda i: (order[i["kind"]], not i["public"]))
        sections.append({"title": title, "items": section_items})
        all_items.extend(section_items)
    layer["sections"] = sections
    layer["counts"] = {
        "total": len(all_items),
        "class": sum(i["kind"] == "class" for i in all_items),
        "function": sum(i["kind"] == "function" for i in all_items),
        "constant": sum(i["kind"] == "constant" for i in all_items),
        "private": sum(not i["public"] for i in all_items),
    }
    return layer


def build_tree(source: str, exported: List[str]) -> List[dict]:
    """Group the module-level objects by layer and section.

    Args:
        source: Source code of the driver module.
        exported: The module's ``__all__``; these objects are public.

    Returns:
        A list of layers. Each layer has ``number``, ``title``, ``short``
        (title without the part after a colon), ``description``,
        ``counts`` and ``sections``; each section has ``title`` (empty for
        objects before the first section banner) and ``items``. An item has
        ``name``, ``kind`` (``class``, ``function`` or ``constant``),
        ``public`` and, for classes, ``members``. Items are ordered classes,
        functions, constants; within each kind public before private.
    """
    tree = ast.parse(source)
    banners = _banners(source.splitlines())
    descriptions = _layer_descriptions(ast.get_docstring(tree) or "")

    layers: Dict[str, dict] = {}
    for line, item in _module_items(tree, set(exported)):
        layer_title, section_title = _locate(banners, line)
        layer_title = layer_title or "0. Module"
        if layer_title not in layers:
            match = _LAYER_RE.match("# " + layer_title)
            number = match.group(1) if match else "0"
            layers[layer_title] = {
                "number": number,
                "title": layer_title,
                "short": layer_title.split(":")[0],
                "description": descriptions.get(number, ""),
                "sections": {},
            }
        layers[layer_title]["sections"].setdefault(section_title, []).append(item)
    return [_finish_layer(layer) for layer in layers.values()]


def documented_qualnames(tree: List[dict]) -> List[str]:
    """List the qualified names of every object shown in the documentation.

    Args:
        tree: Result of :func:`build_tree`.

    Returns:
        Module-level names and ``Class.member`` names.
    """
    names = []
    for layer in tree:
        for section in layer["sections"]:
            for item in section["items"]:
                names.append(item["name"])
                for member in item.get("members", []):
                    names.append(f"{item['name']}.{member['name']}")
    return names


def main(argv: Optional[List[str]] = None) -> int:
    """Build the HTML documentation.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", default="site",
                        help="output directory (default: site)")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(ROOT))
    sys.dont_write_bytecode = True
    module = importlib.import_module(MODULE)
    source = (ROOT / f"{MODULE}.py").read_text(encoding="utf-8")
    tree = build_tree(source, list(module.__all__))
    shown = documented_qualnames(tree)

    # pdoc documents exactly the module-level names in __all__. Widen it on
    # the imported module object (not in the source) so private objects are
    # documented as well; public/private is taken from the original list.
    module.__all__ = [n for n in shown if "." not in n]

    pdoc.render.configure(docformat="google", template_directory=TEMPLATES)
    pdoc.render.env.globals["layers"] = tree
    pdoc.render.env.globals["shown"] = set(shown)
    pdoc.pdoc(MODULE, output_directory=Path(args.output))
    print(f"Documentation written to {args.output}/ "
          f"({len(shown)} objects in {len(tree)} layers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
