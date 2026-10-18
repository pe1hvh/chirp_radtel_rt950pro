#!/usr/bin/env python3
"""Build the documentation page of ``radtel_rt950pro.py``: documents plus API.

pdoc renders the Google-style docstrings; this script adds the structure
that pdoc does not know about:

* **Documents.** The design documents in ``docs/`` (``DOCUMENTS``: the
  functional and technical design and the CHIRP interface description) are
  converted from Markdown and shown on the same page, above the API
  reference, with their own group in the side menu. The Markdown files stay
  the single source and still read correctly on GitHub:

  - headings get the anchor GitHub would give them, prefixed per document
    (``## 4. Download`` in ``chirp-interface.md`` becomes
    ``#interface-4-download``), so links between the documents keep working;
  - links to other files in the repository point to GitHub, for the branch
    being built; a link to the front page of the published documentation
    points to ``#api`` on the same page;
  - identifiers in backticks are linked to the API by pdoc's ``linkify``
    filter (in the template), exactly as in docstrings;
  - diagrams from ``docs/diagrams`` are copied next to the page and open at
    full size when clicked;
  - every link between documents is checked; a missing anchor stops the
    build;
  - each driver layer heading links back to the design chapter that
    describes that layer.

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

Usage (from the repository root):

    pip install "pdoc>=16,<17"
    python docs/build.py                  # writes the HTML to ./site
    python docs/build.py -o out           # other output directory
    python docs/build.py --branch develop # GitHub links to another branch
    DOCS_BRANCH=develop python docs/build.py  # same, via the environment

Only the standard library and pdoc (with its dependency markdown2) are
needed; CHIRP and pyserial are not.
"""

from __future__ import annotations

import argparse
import ast
import html
import importlib
import os
import posixpath
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import markdown2
import pdoc
import pdoc.render
import pdoc.render_helpers

ROOT = Path(__file__).resolve().parent.parent
"""Repository root (the directory that holds the driver)."""

MODULE = "radtel_rt950pro"
"""Name of the documented module."""

TEMPLATES = Path(__file__).resolve().parent / "templates"
"""Directory with the pdoc template overrides."""

_LAYER_RE = re.compile(r"#\s*(\d+)\.\s+(.+)")
"""Matches a layer title line such as ``# 1. Channel records``."""

DOCS = Path(__file__).resolve().parent
"""The ``docs`` directory that holds the Markdown documents and diagrams."""

DOCUMENTS: Tuple[Tuple[str, str, str], ...] = (
    ("fto.md", "design", "Design (FTO)"),
    ("chirp-interface.md", "interface", "CHIRP interface"),
)
"""Documents shown above the API reference, in page order.

Each entry is ``(file name in docs/, anchor prefix, menu label)``. The
prefix makes heading anchors unique on the page and is the anchor of the
document itself.
"""

DESIGN_PREFIX = "design"
"""Anchor prefix of the design document; its layer chapters are linked from
the layer headings of the API reference (:func:`layer_chapters`)."""

DIAGRAMS = "diagrams"
"""Directory (in ``docs/`` and in the output) holding the diagram images."""

REPO_URL = "https://github.com/pe1hvh/chirp_radtel_rt950pro"
"""GitHub repository; links to repository files that are not on the page go here."""

SITE_URL = "https://pe1hvh.github.io/chirp_radtel_rt950pro"
"""Published documentation; a link to its front page (without ``#``) becomes ``#api``."""

BRANCH_ENV = "DOCS_BRANCH"
"""Environment variable naming the branch for links to GitHub.

Used by the workflow; an environment variable rather than ``--branch``
because the workflow on one branch also runs the other branch's
``build.py``, which may not know newer options.
"""

API_ANCHOR = "api"
"""Anchor of the "API reference" heading on the page."""

TOC_LEVELS = (2, 3)
"""Heading levels of a document that are listed in the side menu."""

_HEADING_RE = re.compile(r"<h([2-6])>(.*?)</h\1>", re.S)
"""Matches a heading as written by markdown2 (without an ``id``)."""

_HREF_RE = re.compile(r'href="([^"]*)"')
"""Matches the target of a link in rendered HTML."""

_IMG_RE = re.compile(r"<img ([^>]*?)\s*/?>")
"""Matches an image tag in rendered HTML; group 1 holds its attributes."""

_EMPTY_HEAD_RE = re.compile(r"<thead>\s*<tr>(?:\s*<th[^>]*>\s*</th>)+\s*</tr>\s*</thead>")
"""Matches a table header row whose cells are all empty (``| | |`` tables)."""

_LAYER_CHAPTER_RE = re.compile(r"^[A-Z]\d+\.\s+Layers?\s+(\d+)(?:\s+and\s+(\d+))?")
"""Matches a design chapter about one driver layer, or two joined by *and*,
e.g. ``B5. Layer 1`` or ``B6. Layers 2 and 3``."""


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


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def github_slug(text: str, used: Optional[Dict[str, int]] = None) -> str:
    """Turn a heading into the anchor GitHub gives it.

    Tags are removed, the text is lower-cased, every character that is not
    a letter, digit, underscore, hyphen or space is dropped and spaces
    become hyphens; so ``8. Memory ↔ channel record mapping`` becomes
    ``8-memory--channel-record-mapping``. A slug that is already taken gets
    ``-1``, ``-2``, ... appended until it is free, as GitHub does
    (headings ``a``, ``a``, ``a-1`` give ``a``, ``a-1``, ``a-1-1``).

    Args:
        text: Heading text, possibly with inline HTML.
        used: Slugs already given in the same document, mapped to the last
            suffix number used for them; updated in place. ``None`` disables
            the duplicate handling.

    Returns:
        The anchor, without ``#``.
    """
    plain = html.unescape(re.sub(r"<[^>]+>", "", text))
    slug = re.sub(r"[^\w\- ]", "", plain.strip().lower()).replace(" ", "-")
    if used is not None:
        base, number = slug, used.get(slug, 0)
        while slug in used:
            number += 1
            slug = f"{base}-{number}"
        used[base] = number
        used[slug] = 0
    return slug


def current_branch(root: Path) -> str:
    """Return the git branch of the working tree, for links to GitHub.

    Args:
        root: Directory inside the repository.

    Returns:
        The branch name, or ``"main"`` when git is not available, the tree
        is not a repository or the checkout is detached.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root,
            capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return "main"
    branch = result.stdout.strip()
    return branch if branch and branch != "HEAD" else "main"


def _rewrite_href(href: str, prefix: str, prefixes: Dict[str, str], blob: str) -> str:
    """Translate a link target of a document to its target on the page.

    Args:
        href: Link target as written in the Markdown file.
        prefix: Anchor prefix of the document that contains the link.
        prefixes: File name to anchor prefix of every document on the page.
        blob: Base URL of the repository on GitHub for the built branch,
            ending in ``/`` (``…/blob/develop/``).

    Returns:
        ``#prefix-anchor`` for a link within the document; the prefixed
        anchor (or the document anchor) for a link to another document on
        the page; ``#api`` for a link to the front page of the published
        documentation; ``diagrams/...`` and absolute URLs (``http:``,
        ``https:``, ``mailto:``) unchanged; any other relative link
        (``memory-map.md``, ``../README.md``) as a GitHub URL of that file,
        resolved against ``docs/``.
    """
    if href.startswith("#"):
        return f"#{prefix}-{href[1:]}"
    if href.rstrip("/") in (SITE_URL, f"{SITE_URL}/radtel_rt950pro.html",
                            f"{SITE_URL}/index.html"):
        return f"#{API_ANCHOR}"
    if re.match(r"[a-z][a-z0-9+.-]*:", href) or href.startswith(DIAGRAMS + "/"):
        return href
    path, _, anchor = href.partition("#")
    path = path.split("?")[0]
    if path.startswith("./"):
        path = path[2:]
    if path in prefixes:
        return f"#{prefixes[path]}-{anchor}" if anchor else f"#{prefixes[path]}"
    target = posixpath.normpath(posixpath.join("docs", path))
    return f"{blob}{target}" + (f"#{anchor}" if anchor else "")


def _image_size(path: Path) -> Optional[Tuple[int, int]]:
    """Read the width and height of an SVG image.

    Args:
        path: Image file; only ``.svg`` files are read.

    Returns:
        ``(width, height)`` in pixels from the ``width`` and ``height``
        attributes of the ``<svg>`` element, or ``None`` when the file is
        missing, not an SVG or has no numeric size.
    """
    if path.suffix.lower() != ".svg" or not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        head = handle.read(2000)
    match = re.search(r'<svg[^>]*\swidth="(\d+(?:\.\d+)?)"[^>]*\sheight="(\d+(?:\.\d+)?)"', head)
    if not match:
        return None
    return round(float(match.group(1))), round(float(match.group(2)))


def _markdown(text: str) -> str:
    """Convert Markdown to HTML with pdoc's markdown2 settings.

    Heading anchors and the table of contents are left out; the caller
    assigns GitHub-style anchors itself.

    Args:
        text: Markdown source.

    Returns:
        The HTML.
    """
    extras = {key: value for key, value in pdoc.render_helpers.markdown_extensions.items()
              if key not in ("header-ids", "toc")}
    return str(markdown2.markdown(
        text, extras=extras, link_patterns=pdoc.render_helpers.markdown_link_patterns))


def render_document(path: Path, prefix: str, prefixes: Dict[str, str], blob: str) -> dict:
    """Convert one Markdown document into HTML for the page.

    The first line (``# Title``) becomes the document title; the rest is
    converted with :func:`_markdown`. All headings, the title included, get
    prefixed GitHub anchors (the title's anchor is put on the document
    heading), empty table header rows (from ``| | |`` key/value tables) are
    removed, images are lazy-loaded and wrapped in a link to the full-size
    file, and link targets are rewritten by :func:`_rewrite_href`.

    Images must live in ``docs/diagrams`` (only that directory is copied)
    and must not themselves be links; identifiers in ``alt`` texts or file
    names should be avoided, because pdoc's ``linkify`` in the template also
    scans attribute values.

    Args:
        path: The Markdown file.
        prefix: Anchor prefix of this document.
        prefixes: File name to anchor prefix of every document on the page.
        blob: Base URL of the repository on GitHub for the built branch.

    Returns:
        Dict with ``id`` (the prefix), ``title`` (HTML), ``title_anchor``
        (the prefixed GitHub anchor of the title), ``html`` (the body, not
        yet linkified), ``toc`` (``(anchor, text, level)`` for the headings
        of ``TOC_LEVELS``), ``anchors`` (all heading anchors and the prefix)
        and ``links`` (every in-page link target, without ``#``, for
        :func:`check_links`).
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    title = re.sub(r"^<p>|</p>\s*$", "", _markdown(lines[0].lstrip("#").strip()).strip())
    body = _markdown("\n".join(lines[1:]))
    toc: List[Tuple[str, str, int]] = []
    used: Dict[str, int] = {}
    title_anchor = f"{prefix}-{github_slug(title, used)}"
    anchors: Set[str] = {prefix, title_anchor}

    def heading(match: re.Match) -> str:
        """Give a heading its prefixed anchor and record it.

        Args:
            match: A :data:`_HEADING_RE` match.

        Returns:
            The heading with an ``id`` attribute.
        """
        level, text = int(match.group(1)), match.group(2)
        anchor = f"{prefix}-{github_slug(text, used)}"
        anchors.add(anchor)
        if level in TOC_LEVELS:
            toc.append((anchor, html.unescape(re.sub(r"<[^>]+>", "", text)), level))
        return f'<h{level} id="{anchor}">{text}</h{level}>'

    def image(match: re.Match) -> str:
        """Wrap an image in a link to itself and load it lazily.

        Width and height are taken from the image file (see
        :func:`_image_size`) so the browser reserves the space before the
        image loads; otherwise lazy loading would shift the page and links
        to anchors below the image would land in the wrong place.

        Args:
            match: An :data:`_IMG_RE` match.

        Returns:
            The linked image.
        """
        attrs = match.group(1)
        src = re.search(r'src="([^"]*)"', attrs)
        target = src.group(1) if src else ""
        size = _image_size(path.parent / target) if target else None
        if size:
            attrs += f' width="{size[0]}" height="{size[1]}"'
        return (f'<a class="diagram" href="{target}" target="_blank" rel="noopener" '
                f'title="Open full size"><img {attrs} loading="lazy"></a>')

    body = _HEADING_RE.sub(heading, body)
    body = _EMPTY_HEAD_RE.sub("", body)
    body = _IMG_RE.sub(image, body)
    links: List[str] = []

    def href(match: re.Match) -> str:
        """Rewrite one link target and record it when it is an anchor.

        Args:
            match: An :data:`_HREF_RE` match.

        Returns:
            The rewritten ``href`` attribute.
        """
        target = _rewrite_href(html.unescape(match.group(1)), prefix, prefixes, blob)
        if target.startswith("#"):
            links.append(target[1:])
        return f'href="{html.escape(target, quote=True)}"'

    body = _HREF_RE.sub(href, body)
    return {"id": prefix, "title": title, "title_anchor": title_anchor, "html": body,
            "toc": toc, "anchors": anchors, "links": links}


def check_links(documents: List[dict]) -> List[str]:
    """Find links between documents whose anchor does not exist.

    Only targets that equal a document prefix or start with it followed by
    ``-`` are checked; other ``#`` targets (``#api``, layer and API anchors)
    are not checked.

    Args:
        documents: Results of :func:`render_document`.

    Returns:
        One message per broken link, empty when all links resolve.
    """
    anchors = set().union(*(doc["anchors"] for doc in documents))
    prefixes = tuple(doc["id"] for doc in documents)
    errors = []
    for doc in documents:
        for target in doc["links"]:
            ours = any(target == p or target.startswith(p + "-") for p in prefixes)
            if ours and target not in anchors:
                errors.append(f"{doc['id']}: link to missing anchor #{target}")
    return errors


def layer_chapters(document: dict) -> Dict[str, List[Tuple[str, str]]]:
    """Map driver layers to the design chapters that describe them.

    A chapter heading such as ``B6. Layers 2 and 3 — settings`` links
    layers 2 and 3 to that chapter.

    Args:
        document: The rendered design document (:func:`render_document`).

    Returns:
        Layer number (as text) to a list of ``(anchor, label)``; the label is
        the chapter number, e.g. ``B6``.
    """
    result: Dict[str, List[Tuple[str, str]]] = {}
    for anchor, text, _level in document["toc"]:
        match = _LAYER_CHAPTER_RE.match(text)
        if not match:
            continue
        label = text.split(".")[0]
        for number in filter(None, match.groups()):
            result.setdefault(number, []).append((anchor, label))
    return result


def build_documents(branch: str) -> List[dict]:
    """Render every entry of ``DOCUMENTS``.

    Args:
        branch: Git branch for links to GitHub.

    Returns:
        The rendered documents in page order, each with the extra key
        ``label`` (menu text).

    Raises:
        SystemExit: If a link between the documents points to a missing
            anchor.
    """
    prefixes = {name: prefix for name, prefix, _label in DOCUMENTS}
    blob = f"{REPO_URL}/blob/{branch}/"
    documents = []
    for name, prefix, label in DOCUMENTS:
        document = render_document(DOCS / name, prefix, prefixes, blob)
        document["label"] = label
        documents.append(document)
    errors = check_links(documents)
    if errors:
        raise SystemExit("Broken document links:\n  " + "\n  ".join(errors))
    return documents


def main(argv: Optional[List[str]] = None) -> int:
    """Build the HTML page: documents, API reference and diagrams.

    Renders ``DOCUMENTS``, runs pdoc with the template in ``docs/templates``
    and copies ``docs/diagrams`` into the output directory. The branch for
    links to GitHub is ``--branch``, else ``$DOCS_BRANCH``, else the current
    git branch (``main`` as last resort).

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code (0 on success).

    Raises:
        SystemExit: On invalid arguments or a broken link between documents.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", default="site",
                        help="output directory (default: site)")
    parser.add_argument("--branch", default=None,
                        help="branch for links to GitHub (default: $DOCS_BRANCH, "
                             "else the current git branch)")
    args = parser.parse_args(argv)
    branch = args.branch or os.environ.get(BRANCH_ENV) or current_branch(ROOT)
    documents = build_documents(branch)

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
    pdoc.render.env.globals["documents"] = documents
    design = next((d for d in documents if d["id"] == DESIGN_PREFIX), None)
    pdoc.render.env.globals["layer_chapters"] = layer_chapters(design) if design else {}
    pdoc.render.env.globals["api_anchor"] = API_ANCHOR
    output = Path(args.output)
    pdoc.pdoc(MODULE, output_directory=output)
    shutil.copytree(DOCS / DIAGRAMS, output / DIAGRAMS, dirs_exist_ok=True)
    print(f"Documentation written to {args.output}/ "
          f"({len(documents)} documents, {len(shown)} objects in {len(tree)} layers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
