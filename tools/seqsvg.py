"""Render sequence diagrams as standalone SVG files, without dependencies.

Used for the sequence diagrams in ``docs/diagrams``, in the house style of
the documentation: white background, participant boxes in #0066CC with white
text, messages in a monospace font, returns dashed, ``alt``/``loop`` frames,
yellow notes and full-width section dividers.

A diagram is built in Python and rendered in two passes: the first pass
assigns every event a vertical position and records how wide it is, the
second writes the SVG. Column gaps between participants grow until every
message label fits, so labels never overlap.

Example:
    from pathlib import Path
    from seqsvg import Seq

    s = Seq("1. Download", [("ui", "CHIRP"), ("drv", "Driver"), ("radio", "Radio")])
    s.msg("ui", "drv", "sync_in()")
    s.frame("loop", "every block", "drv", "radio")
    s.msg("drv", "radio", "read block")
    s.ret("radio", "drv", "128 bytes")
    s.end()
    s.self_call("drv", "process_mmap()")
    Path("docs/diagrams/seq-01-download.svg").write_text(s.render(), encoding="utf-8")

Text widths are estimated from the character count (``CHAR_W``), so check
every new diagram visually (open the SVG in a browser).
"""

# Design-size checks are disabled on purpose: the event handlers mirror the
# SVG elements they draw (position, size, colours as parameters), and
# splitting them further would only hide that one-to-one mapping.
# pylint: disable=too-many-arguments,too-many-positional-arguments
# pylint: disable=too-many-locals,too-many-branches

from html import escape
from typing import List, Tuple

__all__ = ["Seq", "text_width"]

FONT = "Segoe UI, Helvetica, Arial, sans-serif"
"""Font family for titles, participant names, notes and frame labels."""
MONO = "Consolas, 'DejaVu Sans Mono', Menlo, monospace"
"""Font family for message labels and self-call texts."""
CHAR_W = 6.9
"""Estimated width in pixels of one 12 px character."""
HEAD_H = 40
"""Height in pixels of a participant box."""
BLUE = "#0066CC"
"""House-style blue: participant boxes, title and divider text."""
INK = "#1F2937"
"""Colour of normal text and solid arrows."""
MUTED = "#6B7280"
"""Colour of return labels and dashed return arrows."""
LINE = "#9CA3AF"
"""Colour of the dashed lifelines."""
NOTE_BG = "#FFF8DC"
"""Fill colour of a note."""
NOTE_BD = "#D4B106"
"""Border colour of a note."""
FRAME_BD = "#7A8CA5"
"""Border colour of ``alt``/``loop`` frames."""
FRAME_TAB = "#E8EEF7"
"""Fill colour of the tab that holds a frame's kind."""
DIV_BG = "#F8F9FA"
"""Fill colour of a section divider."""


def text_width(text: str, mono: bool = False) -> float:
    """Estimate the pixel width of the longest line of a text.

    Args:
        text: Text, possibly spread over lines (backslash-n).
        mono: Use the (slightly wider) monospace estimate.

    Returns:
        Width in pixels at 12 px font size.
    """
    width = CHAR_W * (1.05 if mono else 1.0)
    return max(len(line) for line in text.split("\n")) * width


def _text(x: float, y: float, s: str, *, anchor: str = "start", size: float = 12,
          color: str = INK, weight: str = "normal", mono: bool = False,
          italic: bool = False) -> str:
    """Build one SVG ``<text>`` element.

    Args:
        x: Horizontal position in pixels.
        y: Baseline position in pixels.
        s: The text; XML special characters are escaped.
        anchor: ``start``, ``middle`` or ``end``.
        size: Font size in pixels.
        color: Fill colour.
        weight: ``normal`` or ``bold``.
        mono: Use ``MONO`` instead of ``FONT``.
        italic: Render in italics.

    Returns:
        The SVG element as a string.
    """
    family = MONO if mono else FONT
    style = ' font-style="italic"' if italic else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" '
            f'font-size="{size}" fill="{color}" text-anchor="{anchor}" '
            f'font-weight="{weight}"{style}>{escape(s)}</text>')


class Seq:
    """A sequence diagram: participants plus an ordered list of events.

    Events are added with :meth:`msg`, :meth:`ret`, :meth:`self_call`,
    :meth:`note`, :meth:`frame` / :meth:`els` / :meth:`end` and
    :meth:`divider`, in the order they happen; :meth:`render` returns the
    SVG. Participants are referred to by their key.
    """

    def __init__(self, title: str, participants: List[Tuple[str, str]]) -> None:
        """Create an empty diagram.

        Args:
            title: Title shown top left, e.g. ``"2. Download from radio"``.
            participants: ``(key, label)`` pairs, left to right; a label may
                contain backslash-n for two lines.
        """
        self.title = title
        """Diagram title."""
        self.parts = participants
        """The ``(key, label)`` pairs of the participants, left to right."""
        self.idx = {key: i for i, (key, _label) in enumerate(participants)}
        """Participant key to column index."""
        self.events: List[tuple] = []
        """Recorded events as tuples; the first element is the event kind."""

    # ------------------------------------------------------------------
    # Event API
    # ------------------------------------------------------------------

    def msg(self, a: str, b: str, label: str, ret: bool = False) -> None:
        """Add a message (call) from one participant to another.

        Args:
            a: Key of the sender.
            b: Key of the receiver.
            label: Text above the arrow; backslash-n for more lines.
            ret: Draw it as a return (dashed, grey, open arrow head).
        """
        self.events.append(("msg", a, b, label, ret))

    def ret(self, a: str, b: str, label: str = "") -> None:
        """Add a return message (dashed arrow).

        Args:
            a: Key of the participant that returns.
            b: Key of the participant that receives the result.
            label: Text above the arrow; may be empty.
        """
        self.msg(a, b, label, ret=True)

    def self_call(self, a: str, label: str) -> None:
        """Add a call of a participant to itself (a loop to the right).

        Args:
            a: Key of the participant.
            label: Text right of the loop; backslash-n for more lines.
        """
        self.events.append(("self", a, label))

    def note(self, a: str, b: str, text: str) -> None:
        """Add a yellow note.

        Args:
            a: Key of the first participant the note spans.
            b: Key of the last participant; the same as ``a`` centres the
                note on that lifeline.
            text: Note text; backslash-n for more lines.
        """
        self.events.append(("note", a, b, text))

    def frame(self, kind: str, label: str, a: str, b: str) -> None:
        """Open an alt, loop or opt frame; close it with :meth:`end`.

        Args:
            kind: Word in the frame's tab, e.g. ``"alt"`` or ``"loop"``.
            label: Condition shown in italics next to the tab.
            a: Key of the leftmost participant the frame must cover.
            b: Key of the rightmost participant; the frame also widens to
                cover everything drawn inside it.
        """
        self.events.append(("frame", kind, label, a, b))

    def els(self, label: str) -> None:
        """Start the next branch of the open ``alt`` frame (dashed line).

        Args:
            label: Condition of the branch.
        """
        self.events.append(("else", label))

    def end(self) -> None:
        """Close the most recently opened frame."""
        self.events.append(("end",))

    def divider(self, label: str) -> None:
        """Add a full-width band that starts a new part of the diagram.

        Args:
            label: Text in the band, e.g. ``"handshake()"``.
        """
        self.events.append(("div", label))

    # ------------------------------------------------------------------
    # Layout and rendering
    # ------------------------------------------------------------------

    def _columns(self) -> Tuple[List[float], List[float], float]:
        """Compute the x position of every lifeline.

        Gaps start from the participant box widths and grow until every
        message label, self-call text and note fits between its lifelines.

        Returns:
            ``(xs, head_widths, right_extra)``: lifeline positions, box
            widths, and extra room needed right of the last lifeline.
        """
        n = len(self.parts)
        head_w = [max(110, text_width(label) + 28) for _key, label in self.parts]
        gaps = [head_w[i] / 2 + head_w[i + 1] / 2 + 30 for i in range(n - 1)]
        right_extra = 0.0

        def widen(i: int, j: int, need: float) -> None:
            """Spread extra width over the gaps between columns i and j.

            Args:
                i: Left column index.
                j: Right column index (greater than ``i``).
                need: Width the gaps together must reach.
            """
            have = sum(gaps[i:j])
            if have < need:
                for g in range(i, j):
                    gaps[g] += (need - have) / (j - i)

        for ev in self.events:
            if ev[0] == "msg":
                i, j = sorted((self.idx[ev[1]], self.idx[ev[2]]))
                if j > i:
                    widen(i, j, text_width(ev[3]) + 30)
            elif ev[0] == "self":
                i = self.idx[ev[1]]
                need = text_width(ev[2]) + 46
                if i < n - 1:
                    gaps[i] = max(gaps[i], need)
                else:
                    right_extra = max(right_extra, need)
            elif ev[0] == "note":
                i, j = sorted((self.idx[ev[1]], self.idx[ev[2]]))
                need = text_width(ev[3]) + 24
                if i == j:
                    if i > 0:
                        gaps[i - 1] = max(gaps[i - 1], need / 2 + 10)
                    if i < n - 1:
                        gaps[i] = max(gaps[i], need / 2 + 10)
                    else:
                        right_extra = max(right_extra, need / 2)
                else:
                    widen(i, j, need - 40)
        xs = [30 + head_w[0] / 2]
        for gap in gaps:
            xs.append(xs[-1] + gap)
        return xs, head_w, right_extra

    def render(self) -> str:
        """Lay out all events and return the diagram as an SVG document.

        One function on purpose: the vertical cursor, the frame stack and the
        extents are shared by every event kind.

        Returns:
            A complete ``<svg>`` document with a white background.
        """
        xs, head_w, right_extra = self._columns()
        state = {"y": 54.0 + HEAD_H + 22, "frames": [], "drawn": [], "divs": [],
                 "ext": [min(xs) - head_w[0] / 2, max(xs) + head_w[-1] / 2 + right_extra]}
        for ev in self.events:
            getattr(self, f"_ev_{ev[0]}")(state, xs, *ev[1:])
        bottom = state["y"] + 18
        ext = state["ext"]
        shift = -min(0.0, ext[0] - 20)
        width, height = ext[1] + 30 + shift, bottom + 20
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
               f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" '
               f'role="img" aria-label="{escape(self.title)}">',
               '<defs>'
               '<marker id="solid" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="9" '
               f'markerHeight="9" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
               f'fill="{INK}"/></marker>'
               '<marker id="open" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="9" '
               'markerHeight="9" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10" '
               f'fill="none" stroke="{MUTED}" stroke-width="1.4"/></marker>'
               '</defs>',
               '<rect width="100%" height="100%" fill="#FFFFFF"/>',
               f'<g transform="translate({shift:.1f},0)">',
               _text(xs[0] - head_w[0] / 2, 36, self.title, size=15, weight="bold",
                     color=BLUE)]
        for dy, label in state["divs"]:
            svg.append(f'<rect x="{ext[0] - 10:.1f}" y="{dy:.1f}" '
                       f'width="{ext[1] - ext[0] + 20:.1f}" height="24" fill="{DIV_BG}" '
                       f'stroke="#D1D5DB" stroke-width="0.8"/>')
            svg.append(_text(ext[0], dy + 16, label, weight="bold", color=BLUE))
        for x in xs:
            svg.append(f'<line x1="{x:.1f}" y1="{54 + HEAD_H:.1f}" x2="{x:.1f}" '
                       f'y2="{bottom:.1f}" stroke="{LINE}" stroke-width="1" '
                       f'stroke-dasharray="4 4"/>')
        svg.extend(state["drawn"])
        for i, (_key, label) in enumerate(self.parts):
            x, w = xs[i], head_w[i]
            svg.append(f'<rect x="{x - w / 2:.1f}" y="54.0" width="{w:.1f}" '
                       f'height="{HEAD_H}" rx="4" fill="{BLUE}"/>')
            lines = label.split("\n")
            for k, line in enumerate(lines):
                y = 54 + HEAD_H / 2 + 4 - 7 * (len(lines) - 1) + 14 * k
                svg.append(_text(x, y, line, anchor="middle", color="#FFFFFF",
                                 weight="bold"))
        svg.append("</g></svg>")
        return "\n".join(svg) + "\n"

    # One handler per event kind; each advances state["y"] and records what
    # it drew and how wide it is.

    @staticmethod
    def _extend(state: dict, xmin: float, xmax: float) -> None:
        """Record the horizontal extent of something just drawn.

        Args:
            state: Render state (see :meth:`render`).
            xmin: Leftmost x in pixels.
            xmax: Rightmost x in pixels.
        """
        if state["frames"]:
            frame = state["frames"][-1]
            frame["xmin"] = min(frame["xmin"], xmin)
            frame["xmax"] = max(frame["xmax"], xmax)
        state["ext"][0] = min(state["ext"][0], xmin)
        state["ext"][1] = max(state["ext"][1], xmax)

    def _ev_msg(self, state: dict, xs: List[float], a: str, b: str, label: str,
                is_ret: bool) -> None:
        """Draw a message arrow with its label.

        Args:
            state: Render state.
            xs: Lifeline positions.
            a: Sender key.
            b: Receiver key.
            label: Label text.
            is_ret: Draw dashed as a return.
        """
        xa, xb = xs[self.idx[a]], xs[self.idx[b]]
        lines = label.split("\n") if label else []
        state["y"] += 16 * max(len(lines), 1) + 4
        y, mid = state["y"], (xa + xb) / 2
        for k, line in enumerate(lines):
            state["drawn"].append(_text(mid, y - 6 - 15 * (len(lines) - 1 - k), line,
                                        anchor="middle", color=MUTED if is_ret else INK,
                                        mono=True, size=11.5))
        dash = ' stroke-dasharray="5 4"' if is_ret else ""
        marker = "url(#open)" if is_ret else "url(#solid)"
        state["drawn"].append(f'<line x1="{xa:.1f}" y1="{y:.1f}" x2="{xb:.1f}" y2="{y:.1f}" '
                              f'stroke="{MUTED if is_ret else INK}" stroke-width="1.3"{dash} '
                              f'marker-end="{marker}"/>')
        half = text_width(label, True) / 2 if label else 0
        self._extend(state, min(xa, xb, mid - half), max(xa, xb, mid + half))
        state["y"] += 12

    def _ev_self(self, state: dict, xs: List[float], a: str, label: str) -> None:
        """Draw a self-call loop with its text.

        Args:
            state: Render state.
            xs: Lifeline positions.
            a: Participant key.
            label: Text right of the loop.
        """
        xa = xs[self.idx[a]]
        lines = label.split("\n")
        state["y"] += 10
        y = state["y"]
        h = max(18, 15 * len(lines) + 4)
        state["drawn"].append(f'<path d="M{xa:.1f},{y:.1f} h28 v{h:.1f} h-26" fill="none" '
                              f'stroke="{INK}" stroke-width="1.3" marker-end="url(#solid)"/>')
        for k, line in enumerate(lines):
            state["drawn"].append(_text(xa + 36, y + 12 + 15 * k, line, mono=True, size=11.5))
        self._extend(state, xa, xa + 36 + text_width(label, True))
        state["y"] += h + 14

    def _ev_note(self, state: dict, xs: List[float], a: str, b: str, label: str) -> None:
        """Draw a note box.

        Args:
            state: Render state.
            xs: Lifeline positions.
            a: First participant key.
            b: Last participant key.
            label: Note text.
        """
        i, j = sorted((self.idx[a], self.idx[b]))
        lines = label.split("\n")
        w = text_width(label) + 24
        if i == j:
            x0, x1 = xs[i] - w / 2, xs[i] + w / 2
        else:
            x0 = min(xs[i] - 20, (xs[i] + xs[j]) / 2 - w / 2)
            x1 = max(xs[j] + 20, (xs[i] + xs[j]) / 2 + w / 2)
        state["y"] += 10
        y, h = state["y"], 16 * len(lines) + 10
        state["drawn"].append(f'<rect x="{x0:.1f}" y="{y:.1f}" width="{x1 - x0:.1f}" '
                              f'height="{h:.1f}" fill="{NOTE_BG}" stroke="{NOTE_BD}" '
                              f'stroke-width="1" rx="3"/>')
        for k, line in enumerate(lines):
            state["drawn"].append(_text(x0 + 10, y + 17 + 16 * k, line, size=11.5))
        self._extend(state, x0, x1)
        state["y"] += h + 8

    def _ev_frame(self, state: dict, xs: List[float], kind: str, label: str,
                  a: str, b: str) -> None:
        """Open a frame; it is drawn when :meth:`_ev_end` closes it.

        Args:
            state: Render state.
            xs: Lifeline positions.
            kind: Tab text.
            label: Condition text.
            a: Leftmost participant key.
            b: Rightmost participant key.
        """
        i, j = sorted((self.idx[a], self.idx[b]))
        pad = 74 - len(state["frames"]) * 12
        state["y"] += 12
        state["frames"].append({"kind": kind, "label": label, "top": state["y"],
                                "xmin": xs[i] - pad, "xmax": xs[j] + pad, "elses": []})
        state["y"] += 30

    def _ev_else(self, state: dict, _xs: List[float], label: str) -> None:
        """Record a branch line of the open frame.

        Args:
            state: Render state.
            _xs: Lifeline positions (unused).
            label: Branch condition.
        """
        state["y"] += 6
        state["frames"][-1]["elses"].append((state["y"], label))
        state["y"] += 26

    def _ev_end(self, state: dict, _xs: List[float]) -> None:
        """Close and draw the innermost frame, behind what it contains.

        Args:
            state: Render state.
            _xs: Lifeline positions (unused).
        """
        frame = state["frames"].pop()
        state["y"] += 8
        top, bottom = frame["top"], state["y"]
        x0, x1 = frame["xmin"] - 6, frame["xmax"] + 6
        tab_w = text_width(frame["kind"]) + 16
        parts = [f'<rect x="{x0:.1f}" y="{top:.1f}" width="{x1 - x0:.1f}" '
                 f'height="{bottom - top:.1f}" fill="none" stroke="{FRAME_BD}" '
                 f'stroke-width="1.1" rx="2"/>',
                 f'<path d="M{x0:.1f},{top:.1f} h{tab_w:.1f} v12 l-8,8 h{-(tab_w - 8):.1f} z" '
                 f'fill="{FRAME_TAB}" stroke="{FRAME_BD}" stroke-width="1.1"/>',
                 _text(x0 + 7, top + 14, frame["kind"], weight="bold", size=11.5)]
        if frame["label"]:
            parts.append(_text(x0 + tab_w + 8, top + 14, frame["label"], size=11.5,
                               italic=True))
        for ey, elabel in frame["elses"]:
            parts.append(f'<line x1="{x0:.1f}" y1="{ey:.1f}" x2="{x1:.1f}" y2="{ey:.1f}" '
                         f'stroke="{FRAME_BD}" stroke-dasharray="6 4" stroke-width="1"/>')
            parts.append(_text(x0 + 8, ey + 16, elabel, size=11.5, italic=True))
        state["drawn"][:0] = parts
        self._extend(state, x0 - 8, x1 + 8)
        state["y"] += 6

    def _ev_div(self, state: dict, _xs: List[float], label: str) -> None:
        """Record a section divider band.

        Args:
            state: Render state.
            _xs: Lifeline positions (unused).
            label: Band text.
        """
        state["y"] += 14
        state["divs"].append((state["y"], label))
        state["y"] += 34
