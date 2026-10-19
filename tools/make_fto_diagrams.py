#!/usr/bin/env python3
"""Generate the structure diagrams in ``docs/diagrams`` (``fto-*.svg``).

Three hand-placed diagrams for ``docs/fto.md``:

* ``fto-layers.svg``: the six driver layers between CHIRP and the radio;
* ``fto-classes.svg``: the main classes and their relations;
* ``fto-write-plan.svg``: the clone image layout and the upload order.

Positions are fixed pixel coordinates, so after a change open the SVG in a
browser and check that nothing overlaps. Run from the repository root:

    python3 tools/make_fto_diagrams.py              # writes to docs/diagrams
    python3 tools/make_fto_diagrams.py some/dir     # other output directory

The sequence diagrams (``seq-*.svg``) are made by ``tools/make_diagrams.py``.
"""

# Design-size checks are disabled on purpose: each diagram is one function
# that places its boxes and lines at fixed coordinates; splitting it would
# only scatter the layout of one picture over several functions.
# pylint: disable=too-many-locals,too-many-statements,too-many-arguments
# pylint: disable=too-many-positional-arguments

import sys
from html import escape
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"
"""Default output directory: ``docs/diagrams`` of this repository."""

FONT = "Segoe UI, Helvetica, Arial, sans-serif"
"""Font family for titles, labels and descriptions."""
MONO = "Consolas, 'DejaVu Sans Mono', Menlo, monospace"
"""Font family for code names (classes, fields, addresses)."""
BLUE = "#0066CC"
"""House-style blue: titles, layer numbers, class names."""
INK = "#1F2937"
"""Colour of normal text, box borders and arrows."""
MUTED = "#6B7280"
"""Colour of secondary text and edge labels."""
LIGHT = "#F8F9FA"
"""Fill colour of the layer boxes."""
EDGE = "#9CA3AF"
"""Border colour of the layer boxes."""

Box = Tuple[float, float, float, float]
"""A drawn box as ``(x, y, width, height)`` in pixels."""


def _text(x, y, s: str, size: float = 12, anchor: str = "start", color: str = INK,
          weight: str = "normal", mono: bool = False) -> str:
    """Build one SVG ``<text>`` element.

    Args:
        x: Horizontal position in pixels (a number, or text already formatted).
        y: Baseline position in pixels.
        s: The text; XML special characters are escaped.
        size: Font size in pixels.
        anchor: ``start``, ``middle`` or ``end``.
        color: Fill colour.
        weight: ``normal`` or ``bold``.
        mono: Use ``MONO`` instead of ``FONT``.

    Returns:
        The SVG element as a string.
    """
    family = MONO if mono else FONT
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{escape(s)}</text>')


def _head(width: int, height: int, title: str) -> List[str]:
    """Start an SVG document: root element, arrow markers, background, title.

    Markers: ``arr`` (filled arrow head), ``tri`` (hollow triangle, for
    inheritance) and ``dia`` (filled diamond, for composition).

    Args:
        width: Width in pixels.
        height: Height in pixels.
        title: Title shown top left and used as ``aria-label``.

    Returns:
        The opening SVG parts; the caller appends to the list and closes it
        with ``</svg>``.
    """
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
            '<defs>'
            '<marker id="arr" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="9" '
            'markerHeight="9" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
            f'fill="{INK}"/></marker>'
            '<marker id="tri" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="13" '
            'markerHeight="13" orient="auto-start-reverse"><path d="M0,0 L12,6 L0,12 z" '
            f'fill="#FFFFFF" stroke="{INK}" stroke-width="1.2"/></marker>'
            '<marker id="dia" viewBox="0 0 14 10" refX="1" refY="5" markerWidth="15" '
            'markerHeight="11" orient="auto-start-reverse"><path d="M1,5 L7,1 L13,5 L7,9 z" '
            f'fill="{INK}"/></marker>'
            '</defs>',
            '<rect width="100%" height="100%" fill="#FFFFFF"/>',
            _text(24, 32, title, 15, weight="bold", color=BLUE)]


def layers() -> str:
    """Build ``fto-layers.svg``: CHIRP, the six driver layers and the radio.

    Each layer row shows its number, name, main objects and what it does;
    the left column names the data form at that level.

    Returns:
        The complete SVG document.
    """
    s = _head(1180, 880, "Driver layers of radtel_rt950pro.py")
    x0, w = 210, 720
    # CHIRP box
    s.append(f'<rect x="{x0}" y="54" width="{w}" height="56" rx="6" fill="#E8EEF7" '
             f'stroke="{EDGE}"/>')
    s.append(_text(x0 + w / 2, 77, "CHIRP (wxui editors, clone dialogs, chirp_common, settings, "
                   "directory)", 12.5, "middle", weight="bold"))
    s.append(_text(x0 + w / 2, 97, "calls: sync_in, sync_out, get/set_memory, get/set_settings, "
                   "get_sub_devices, process_mmap, save_mmap", 11, "middle", MUTED, mono=True))
    rows = [
        ("6", "CHIRP integration",
         "RT950ProDriver (registered), RT950ProRadio, RT950ProZoneRadio x 10",
         "Memory <-> ChannelRecord, RadioSettings tree + apply callbacks,\n"
         "write options and _WRITE_PLAN, legacy-image upgrade, CHIRP stand-ins"),
        ("5", "Transport", "CloneSerialTransport, CloneSegment, DEFAULT_SEGMENTS",
         "PROGRAMBT9000U handshake, XOR key, 0x80-byte blocks,\n"
         "ACK time-outs 8 / 10 / 30 s, progress callback"),
        ("4", "Image", "RadioImage, parse_zone_names, encode_zone_names",
         "35,456-byte image <-> parsed sections; keeps remainder and\n0x7BC0-0x7FFF verbatim"),
        ("3", "Settings API", "SettingSpec, SettingsError, get_/set_*_value, DTMF accessors",
         "validated access by key (_FUNCTION_SPECS, _APRS_SPECS)"),
        ("2", "Settings sections",
         "VFOSettings, FunctionSettings, DTMFSettings, Modulation*, APRSSettings",
         "parse_* / encode_* per block; read-modify-write on stored bytes"),
        ("1", "Channel records", "ChannelRecord, ToneSetting, enums, BCD / GB2312 codecs",
         "32-byte channel record; unchanged record = original bytes"),
    ]
    y = 128
    row_h = 108
    for num, name, objects, what in rows:
        s.append(f'<rect x="{x0}" y="{y}" width="{w}" height="{row_h - 14}" rx="6" '
                 f'fill="{LIGHT}" stroke="{EDGE}"/>')
        s.append(f'<rect x="{x0}" y="{y}" width="46" height="{row_h - 14}" rx="6" '
                 f'fill="{BLUE}"/>')
        s.append(f'<rect x="{x0 + 30}" y="{y}" width="16" height="{row_h - 14}" fill="{BLUE}"/>')
        s.append(_text(x0 + 23, y + (row_h - 14) / 2 + 7, num, 20, "middle", "#FFFFFF", "bold"))
        s.append(_text(x0 + 62, y + 24, name, 14, weight="bold", color=BLUE))
        s.append(_text(x0 + 62, y + 45, objects, 11.5, mono=True))
        for k, line in enumerate(what.split("\n")):
            s.append(_text(x0 + 62, y + 66 + 15 * k, line, 11.5, color=MUTED))
        y += row_h
    # radio box
    s.append(f'<rect x="{x0}" y="{y}" width="{w}" height="50" rx="6" fill="#E8EEF7" '
             f'stroke="{EDGE}"/>')
    s.append(_text(x0 + w / 2, y + 30, "RT-950 Pro over the USB programming cable "
                   "(115200 baud, 8N1)", 12.5, "middle", weight="bold"))
    # left: data form per layer
    forms = [(128 + 47, "Memory,\nRadioSettings"), (128 + row_h + 47, "bytes on\nthe wire"),
             (128 + 2 * row_h + 47, "image bytes\n<-> RadioImage"),
             (128 + 3 * row_h + 47, "key / value"),
             (128 + 4 * row_h + 47, "block bytes\n<-> dataclass"),
             (128 + 5 * row_h + 47, "32 bytes\n<-> record")]
    for form_y, label in forms:
        for k, line in enumerate(label.split("\n")):
            s.append(_text(x0 - 18, form_y - 6 + 15 * k, line, 11.5, "end", MUTED))
    # right: dependency arrow
    ax = x0 + w + 40
    s.append(f'<line x1="{ax}" y1="{128 + 6 * row_h - 30}" x2="{ax}" y2="140" stroke="{INK}" '
             f'stroke-width="1.4" marker-end="url(#arr)"/>')
    s.append(_text(ax + 14, 330, "each layer uses only", 11.5, color=MUTED))
    s.append(_text(ax + 14, 346, "the layers below it", 11.5, color=MUTED))
    s.append(_text(ax + 14, 372, "(layer 6 also feeds", 11.5, color=MUTED))
    s.append(_text(ax + 14, 388, "layer 5 with the", 11.5, color=MUTED))
    s.append(_text(ax + 14, 404, "write plan)", 11.5, color=MUTED))
    s.append("</svg>")
    return "\n".join(s) + "\n"


def _box(s: List[str], x: float, y: float, w: float, title: str, lines: List[str],
         stereo: Optional[str] = None, fill: str = "#FFFFFF") -> Box:
    """Draw a UML-style class box and return where it is.

    Args:
        s: SVG parts to append to.
        x: Left edge in pixels.
        y: Top edge in pixels.
        w: Width in pixels; the height follows from the number of lines.
        title: Class name, drawn in bold blue.
        lines: Member lines below a divider, in monospace.
        stereo: Optional stereotype shown as ``«stereo»`` above the name.
        fill: Fill colour (light blue for CHIRP classes).

    Returns:
        The box as ``(x, y, width, height)``.
    """
    h = 30 + 16 * len(lines) + (14 if stereo else 0) + (8 if lines else 0)
    s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{fill}" '
             f'stroke="{INK}" stroke-width="1.1"/>')
    text_y = y + 18
    if stereo:
        s.append(_text(x + w / 2, text_y, f"«{stereo}»", 10.5, "middle", MUTED))
        text_y += 14
    s.append(_text(x + w / 2, text_y + 2, title, 12.5, "middle", BLUE, "bold"))
    top = text_y + 10
    if lines:
        s.append(f'<line x1="{x}" y1="{top}" x2="{x + w}" y2="{top}" stroke="{INK}" '
                 f'stroke-width="0.8"/>')
        for k, line in enumerate(lines):
            s.append(_text(x + 8, top + 16 + 16 * k, line, 11, mono=True))
    return (x, y, w, h)


def classes() -> str:
    """Build ``fto-classes.svg``: the main classes and their relations.

    Shows inheritance (hollow triangle), composition (diamond) and use or
    creation (dashed arrow) between the driver, image, record, settings
    and transport classes and the CHIRP classes they meet.

    Returns:
        The complete SVG document.
    """
    s = _head(1500, 860, "Main classes and their relations")
    boxes: Dict[str, Box] = {}
    boxes["clone"] = _box(s, 40, 60, 250, "CloneModeRadio",
                          ["pipe, _mmap, _metadata", "load_mmap(), save_mmap()"],
                          "CHIRP chirp_common", "#E8EEF7")
    boxes["radio"] = _box(s, 40, 220, 330, "RT950ProRadio", [
        "_image: RadioImage", "_memory_cache: dict[int, Memory]",
        "_zone_names_valid, _legacy_960",
        "_aprs_original, _high_channels_original",
        "sync_in(), sync_out(), process_mmap()",
        "get/set_memory(), get/set_settings()",
        "get_sub_devices(), _write_options()"])
    boxes["drv"] = _box(s, 40, 500, 200, "RT950ProDriver", ["(no members)"],
                        "directory.register")
    boxes["zone"] = _box(s, 430, 500, 300, "RT950ProZoneRadio", [
        "_parent: RT950ProRadio", "_zone (1-10), _first = (z-1)*99",
        "VARIANT = '1 VHF-LOCAL'", "_image -> parent._image (property)",
        "get/set_memory(1-99) -> parent"])
    boxes["img"] = _box(s, 470, 60, 330, "RadioImage", [
        "channels: list[ChannelRecord] (990)",
        "vfo: list[VFOSettings] (3)", "function, dtmf, modulation, aprs",
        "zone_names: list[str] (10)", "remainder, channel_extra: bytes",
        "from_bytes(), to_bytes(), save()"])
    boxes["ch"] = _box(s, 900, 60, 270, "ChannelRecord", [
        "rx_hz, tx_hz, name, power, ...", "rx_tone, tx_tone: ToneSetting",
        "_raw_bytes, _original_state", "from_bytes(), to_bytes()"])
    boxes["tone"] = _box(s, 1240, 60, 230, "ToneSetting", [
        "mode: ToneMode", "ctcss_hz | dcs_code, dcs_polarity",
        "_raw_bytes, _original_state"])
    boxes["sect"] = _box(s, 900, 250, 330, "Settings sections", [
        "VFOSettings (3 x 32 bytes)", "FunctionSettings.values{key}",
        "DTMFSettings (ID, mode, 22 groups)",
        "ModulationSettings + 16 x ModulationChannelEntry",
        "APRSSettings.fields{key}"], "dataclasses")
    boxes["api"] = _box(s, 1280, 270, 190, "SettingSpec",
                        ["kind, min/max,", "choices, max_length", "+ SettingsError"], "layer 3")
    boxes["tr"] = _box(s, 900, 470, 330, "CloneSerialTransport", [
        "serial, logger, progress_cb", "_xor_key, _model, _rng",
        "handshake(), read_clone()", "write_clone(data, segments)"])
    boxes["seg"] = _box(s, 1280, 470, 190, "CloneSegment",
                        ["read/write_command", "start, length"])
    boxes["err"] = _box(s, 900, 680, 330, "CloneTransportError", ["(RuntimeError)"])
    boxes["set"] = _box(s, 260, 700, 470, "RadioSettings tree", [
        "RadioSettingGroup / RadioSetting per field",
        "apply callbacks write into the settings sections",
        "and RadioImage.zone_names"],
        "CHIRP chirp.settings", "#E8EEF7")

    def mid(key: str, side: str) -> Tuple[float, float]:
        """Return the middle of one side of a box.

        Args:
            key: Key of the box in ``boxes``.
            side: ``t`` (top), ``b`` (bottom), ``l`` (left) or ``r`` (right).

        Returns:
            The point as ``(x, y)``.
        """
        x, y, w, h = boxes[key]
        return {"t": (x + w / 2, y), "b": (x + w / 2, y + h), "l": (x, y + h / 2),
                "r": (x + w, y + h / 2)}[side]

    def line(p1, p2, marker_end: Optional[str] = "arr", dash: bool = False,
             marker_start: Optional[str] = None, label: Optional[str] = None,
             lx: float = 0, ly: float = 0) -> None:
        """Draw a relation line, optionally with markers and a label.

        Args:
            p1: Start point ``(x, y)``.
            p2: End point ``(x, y)``.
            marker_end: Marker id at the end (``arr``, ``tri``) or ``None``.
            dash: Draw dashed (use, creation, delegation).
            marker_start: Marker id at the start (``dia`` for composition).
            label: Text at the middle of the line, or ``None``.
            lx: Horizontal offset of the label from the middle.
            ly: Vertical offset of the label from the middle.
        """
        d = ' stroke-dasharray="6 4"' if dash else ""
        ms = f' marker-start="url(#{marker_start})"' if marker_start else ""
        me = f' marker-end="url(#{marker_end})"' if marker_end else ""
        s.append(f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" '
                 f'stroke="{INK}" stroke-width="1.2"{d}{ms}{me}/>')
        if label:
            s.append(_text((p1[0] + p2[0]) / 2 + lx, (p1[1] + p2[1]) / 2 + ly, label, 11,
                           color=MUTED))

    rx, ry, rw, rh = boxes["radio"]
    zx, zy, zw, zh = boxes["zone"]
    ix, iy, iw, ih = boxes["img"]
    sx, sy, sw, _sh = boxes["sect"]
    # inheritance (hollow triangle at the parent)
    line((165, ry), (165, boxes["clone"][1] + boxes["clone"][3]), "tri")
    line((140, boxes["drv"][1]), (140, ry + rh), "tri")
    line((zx + 40, zy), (rx + rw - 40, ry + rh), "tri")
    s.append(_text(zx + 46, zy - 30, "inherits", 11, color=MUTED))
    # zone -> parent (delegation)
    line((zx + 170, zy), (rx + rw, ry + rh - 30), "arr", dash=True)
    s.append(_text(zx + 150, zy - 12, "_parent: delegates get/set_memory", 11, color=MUTED))
    s.append(_text(zx + zw - 36, zy + zh + 16, "x 10", 11.5, color=MUTED, weight="bold"))
    # composition
    line((rx + rw, ry + 40), (ix, iy + ih / 2), None, marker_start="dia", label="_image",
         lx=-30, ly=10)
    line((ix + iw, iy + 40), (boxes["ch"][0], boxes["ch"][1] + 40), None, marker_start="dia",
         label="990", lx=-14, ly=-6)
    line((boxes["ch"][0] + boxes["ch"][2], boxes["ch"][1] + 40),
         (boxes["tone"][0], boxes["tone"][1] + 40), None,
         marker_start="dia", label="2", lx=-4, ly=-6)
    line((ix + iw, iy + ih - 16), (sx, sy + 40), None, marker_start="dia",
         label="0..1 each", lx=8, ly=-2)
    line((sx + sw, sy + 60), (boxes["api"][0], sy + 60), "arr", dash=True)
    s.append(_text(sx + sw + 4, sy + 52, "validated", 10.5, color=MUTED))
    # transport
    line((rx + rw, ry + rh - 60), (boxes["tr"][0], boxes["tr"][1] + 40), "arr", dash=True)
    s.append(_text(640, 448, "creates in sync_in() / sync_out()", 11, color=MUTED))
    line((boxes["tr"][0] + boxes["tr"][2], boxes["tr"][1] + 40),
         (boxes["seg"][0], boxes["seg"][1] + 40), "arr", dash=True)
    s.append(_text(boxes["tr"][0] + boxes["tr"][2] + 8, boxes["tr"][1] + 32, "uses", 10.5,
                   color=MUTED))
    line(mid("tr", "b"), mid("err", "t"), "arr", dash=True, label="raises", lx=8, ly=4)
    # settings
    line((320, ry + rh), (320, boxes["set"][1]), "arr", dash=True)
    s.append(_text(326, 640, "get_settings() builds", 11, color=MUTED))
    s.append("</svg>")
    return "\n".join(s) + "\n"


def write_plan() -> str:
    """Build ``fto-write-plan.svg``: image layout and the upload order.

    The top row shows the segments of the clone image in read order with
    their write rule; the channel area is drawn compressed. Below it, the
    upload order of ``_WRITE_PLAN`` with block counts.

    Returns:
        The complete SVG document.
    """
    s = _head(1160, 490, "Clone image layout (read order) and write plan")
    segments = [  # label, address, length, write rule, colour
        ("channels 1-960", "0x0000", 0x7800, "always", "#CFE2F7"),
        ("ch. 961-990", "0x7800", 0x3C0, "only if changed", "#FDE2B8"),
        ("unused", "0x7BC0", 0x440, "0x7BC0-0x7BFF only\nwith 961-990; rest never", "#E5E7EB"),
        ("VFO", "0x8000", 0x100, "always", "#CFE2F7"),
        ("function", "0x9000", 0x100, "0x9000-0x907F\nalways", "#CFE2F7"),
        ("DTMF", "0xA000", 0x200, "always", "#CFE2F7"),
        ("mod. params", "0xB000", 0x200, "always", "#CFE2F7"),
        ("mod. names", "0xD000", 0x300, "always", "#CFE2F7"),
        ("APRS", "APRS 0x0000", 0x80, "only if changed,\nlast", "#FDE2B8"),
        ("zone names", "0xC000", 0x100, "if read from\n0xC000", "#D7F0DD"),
    ]

    def seg_width(n: int) -> float:
        """Drawn width of a segment; the large channel area is compressed.

        Args:
            n: Segment length in bytes.

        Returns:
            Width in pixels.
        """
        if n >= 0x7800:
            return 200
        return max(88, 80 + n / 0x300 * 30)

    x = 30
    y = 90
    s.append(_text(30, 70, "Image (.img) = DEFAULT_SEGMENTS in read order, 35,456 bytes "
                   "(channel area not to scale)", 12, color=MUTED))
    for label, addr, n, rule, col in segments:
        w = seg_width(n)
        s.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="54" fill="{col}" '
                 f'stroke="{INK}" stroke-width="0.9"/>')
        s.append(_text(x + w / 2, y + 22, label, 11.5, "middle", weight="bold"))
        s.append(_text(x + w / 2, y + 40, f"{n:#x} B", 10.5, "middle", MUTED, mono=True))
        s.append(_text(x + 3, y + 70, addr, 10, "start", MUTED, mono=True))
        for k, line in enumerate(rule.split("\n")):
            s.append(_text(x + w / 2, y + 92 + 14 * k, line, 10.5, "middle", INK))
        x += w
    # write order
    y2 = 300
    s.append(_text(30, y2 - 18, "Upload order (_WRITE_PLAN), as filtered by _write_options():",
                   12, color=MUTED))
    order = [("1  channels 0x0000-0x77FF (240 blocks)\n    or 0x0000-0x7BFF (248 blocks)",
              "#CFE2F7"),
             ("2  VFO 0x8000 (2)", "#CFE2F7"), ("3  function 0x9000 (1)", "#CFE2F7"),
             ("4  DTMF 0xA000 (4)", "#CFE2F7"), ("5  mod. params 0xB000 (4)", "#CFE2F7"),
             ("6  mod. names 0xD000 (6)", "#CFE2F7"),
             ("7  zone names 0xC000 (2), if valid", "#D7F0DD"),
             ("8  APRS, cmd 0x58 (1), if changed", "#FDE2B8")]
    x = 30
    row_y = y2
    for k, (label, col) in enumerate(order):
        lines = label.split("\n")
        w = max(len(part) for part in lines) * 7.3 + 24
        h = 30 + 14 * (len(lines) - 1)
        if k == 4:
            x = 30
            row_y += 70
        s.append(f'<rect x="{x:.1f}" y="{row_y}" width="{w:.1f}" height="{h}" rx="4" '
                 f'fill="{col}" stroke="{INK}" stroke-width="0.9"/>')
        for j, line in enumerate(lines):
            s.append(_text(f"{x + 10:.1f}", row_y + 19 + 14 * j, line, 11.5, mono=True))
        if k not in (3, 7):
            s.append(f'<line x1="{x + w + 4:.1f}" y1="{row_y + 15}" x2="{x + w + 26:.1f}" '
                     f'y2="{row_y + 15}" stroke="{INK}" stroke-width="1.2" '
                     f'marker-end="url(#arr)"/>')
        x += w + 32
    s.append(_text(30, row_y + 80, "Total: 257 blocks minimum (no zone names, no APRS) to 268 "
                   "maximum. Every block: header 0x57/0x58, addr_hi, addr_lo, 0x80 + 128 "
                   "XOR-ed bytes; radio answers 0x06.", 11.5, color=MUTED))
    s.append(_text(30, row_y + 100, "Never written: 0x7C00-0x7FFF, 0x9080-0x90FF, anything from 0xE000. "
                   "Legacy 960-slot images never write 0x7800-0x7BFF.", 11.5, color=MUTED))
    s.append("</svg>")
    return "\n".join(s) + "\n"


DIAGRAMS: Dict[str, Callable[[], str]] = {
    "fto-layers.svg": layers,
    "fto-classes.svg": classes,
    "fto-write-plan.svg": write_plan,
}
"""Output file name to the function that builds that diagram."""


def main() -> int:
    """Write every diagram of ``DIAGRAMS`` as an SVG file.

    The output directory is the first command-line argument, or
    ``DEFAULT_OUT``; it is created if needed.

    Returns:
        Process exit code (0).
    """
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    for name, build in DIAGRAMS.items():
        (out / name).write_text(build(), encoding="utf-8")
        print("wrote", out / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
