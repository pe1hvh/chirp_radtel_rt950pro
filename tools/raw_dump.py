#!/usr/bin/env python3
"""Read the RT-950 Pro and save the clone image as read, before any encoding. READ-ONLY.

When CHIRP saves a ``.img`` file, the driver first rebuilds the memory map
from its parsed image (``RT950ProRadio.save_mmap``), so a saved file
already shows the driver's encoders at work (for example on the modulation
and APRS blocks). This tool uses only the driver's transport layer
(:class:`radtel_rt950pro.CloneSerialTransport`): it reads every segment of
``DEFAULT_SEGMENTS`` and writes the decrypted bytes unchanged. Nothing is
parsed or encoded, and no write commands are sent: only the handshake, the
read commands and the closing ``E``.

Comparing this file with the same number of leading bytes of a ``.img``
that CHIRP saved from the same radio state shows which bytes the driver
changes without any edit.

Structure:

1. Constants: default file name pattern.
2. Output: segment table and file writing.
3. Command line: argument parsing and ``main``.

Usage (with CHIRP's Python, which has pyserial; close CHIRP first so the
serial port is free):

    ~/.local/share/pipx/venvs/chirp/bin/python tools/raw_dump.py /dev/ttyUSB0
    ~/.local/share/pipx/venvs/chirp/bin/python tools/raw_dump.py /dev/ttyUSB0 raw.bin

The output file has the same layout as the image part of a CHIRP ``.img``:
the segments of ``DEFAULT_SEGMENTS`` concatenated in order. A CHIRP ``.img``
adds its metadata after these bytes.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import radtel_rt950pro as drv  # noqa: E402  pylint: disable=wrong-import-position

__all__ = ["DEFAULT_NAME", "segment_table", "dump", "main"]

# ===========================================================================
# 1. Constants
# ===========================================================================

DEFAULT_NAME = "rt950pro-raw-%Y%m%d-%H%M%S.bin"
"""Default output file name, a :func:`time.strftime` pattern (local time)."""

# ===========================================================================
# 2. Output
# ===========================================================================


def segment_table(segments: Sequence[drv.CloneSegment]) -> List[str]:
    """Describe where each radio segment lands in the output file.

    Args:
        segments: Segments in image order, normally ``drv.DEFAULT_SEGMENTS``.

    Returns:
        One line per segment: file offset, read command, radio address
        and length, all in hexadecimal, e.g.
        ``file 0x08000  cmd 0x52  radio 0x8000  len 0x0100``.
    """
    lines = []
    offset = 0
    for seg in segments:
        lines.append(
            f"file 0x{offset:05X}  cmd 0x{seg.read_command:02X}  "
            f"radio 0x{seg.start:04X}  len 0x{seg.length:04X}"
        )
        offset += seg.length
    return lines


def dump(port: str, out_path: Path) -> int:
    """Read the radio and write the raw image to ``out_path``.

    Opens ``port`` at the driver's default speed (115200 baud), performs
    the handshake (printing the model string), reads ``drv.DEFAULT_SEGMENTS``
    and closes the port. The
    file is written only after the complete read succeeded.

    Args:
        port: Serial device of the programming cable, e.g. ``/dev/ttyUSB0``.
        out_path: Output file; overwritten if it exists.

    Returns:
        Number of bytes written.

    Raises:
        drv.CloneTransportError: On a timeout or protocol error, or when
            pyserial is not installed.
        OSError: If the port cannot be opened or fails during the transfer,
            or the file cannot be written (``serial.SerialException`` and
            ``serial.SerialTimeoutException`` are subclasses).
    """
    config = drv.CloneSerialConfig(port)
    with drv.CloneSerialTransport.open(config, logger=drv.LOG) as transport:
        model = transport.handshake()
        print(f"Radio model: {model}")
        data = transport.read_clone()
    out_path.write_bytes(data)
    return len(data)


# ===========================================================================
# 3. Command line
# ===========================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse the command line, read the radio and report the result.

    Args:
        argv: Arguments without the program name; ``None`` uses
            ``sys.argv[1:]``.

    Returns:
        Exit status: 0 on success, 1 when the read or write failed
        (argparse exits with 2 on invalid arguments).
    """
    parser = argparse.ArgumentParser(
        description="Read the RT-950 Pro and save the raw clone image (read-only)."
    )
    parser.add_argument("port", help="serial port of the cable, e.g. /dev/ttyUSB0")
    parser.add_argument(
        "output",
        nargs="?",
        help="output file (default: " + DEFAULT_NAME.replace("%", "%%") + ")",
    )
    args = parser.parse_args(argv)
    out_path = Path(args.output or time.strftime(DEFAULT_NAME))
    print(f"Driver version: {drv.__version__}")
    try:
        size = dump(args.port, out_path)
    except (drv.CloneTransportError, OSError) as exc:
        print(f"Read failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {size} bytes to {out_path}")
    for line in segment_table(drv.DEFAULT_SEGMENTS):
        print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
