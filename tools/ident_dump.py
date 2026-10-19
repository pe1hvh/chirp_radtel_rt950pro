#!/usr/bin/env python3
"""Show every byte the RT-950 Pro returns during the clone handshake. READ-ONLY.

The driver keeps only the trimmed model string (for example ``RT-950``)
and the XOR key from the handshake, and logs the 16-byte answer to ``F``
at debug level only. This tool runs the driver's own
:meth:`radtel_rt950pro.CloneSerialTransport.handshake`, records every byte
sent and received, ends the session with ``E`` and prints each exchange in
hexadecimal and ASCII. No memory is read and nothing is written to the
radio's memory: only the handshake string, ``F``, ``M``, the 25-byte
``SEND`` key frame and ``E`` are sent.

Purpose: find out whether the radio reports its firmware version (shown on
the radio under the menu *About*) in the handshake. With ``--expect`` the
answers are searched for that version in the usual encodings.

Structure:

1. Recording transport: a transport subclass that logs all traffic.
2. Analysis: hex/ASCII lines and the version search.
3. Command line: argument parsing and ``main``.

Usage (with CHIRP's Python, which has pyserial; close CHIRP first so the
serial port is free):

    ~/.local/share/pipx/venvs/chirp/bin/python tools/ident_dump.py /dev/ttyUSB0
    ~/.local/share/pipx/venvs/chirp/bin/python tools/ident_dump.py /dev/ttyUSB0 --expect 0.29
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import radtel_rt950pro as drv  # noqa: E402  pylint: disable=wrong-import-position

__all__ = [
    "Exchange",
    "RecordingTransport",
    "hex_ascii",
    "version_patterns",
    "find_version",
    "identify",
    "main",
]

Exchange = Tuple[str, bytes]
"""One recorded transfer: direction (``"TX"`` sent, ``"RX"`` received) and
the bytes exactly as on the wire (not XOR-decoded)."""

# ===========================================================================
# 1. Recording transport
# ===========================================================================


class RecordingTransport(drv.CloneSerialTransport):
    """Clone transport that records every byte sent and received.

    Behaves exactly like :class:`radtel_rt950pro.CloneSerialTransport`; the
    overridden helpers call the originals and only append to
    :attr:`exchanges`.
    """

    def __init__(self, *args, **kwargs) -> None:
        """Create the transport and an empty log.

        Args:
            *args: Passed unchanged to
                :class:`radtel_rt950pro.CloneSerialTransport` (the port).
            **kwargs: Passed unchanged (``logger``, ``rng``).
        """
        super().__init__(*args, **kwargs)
        self.exchanges: List[Exchange] = []
        """All transfers in order, as ``(direction, bytes)``."""

    def _write(self, data: bytes) -> None:
        """Record ``data`` as sent, then send it with the driver's code.

        Args:
            data: Raw bytes to write.

        Raises:
            CloneTransportError: If the port reports a short write.
            OSError: If the port fails (``serial.SerialException``, including
                ``serial.SerialTimeoutException`` on a write timeout).
        """
        self.exchanges.append(("TX", bytes(data)))
        super()._write(data)

    def _read_exact(self, size: int) -> bytes:
        """Read with the driver's code, then record what arrived.

        Args:
            size: Number of bytes to read.

        Returns:
            Exactly ``size`` bytes as received.

        Raises:
            CloneTransportError: If the port times out first; nothing is
                recorded for that read.
            OSError: If the port fails (``serial.SerialException``).
        """
        data = super()._read_exact(size)
        self.exchanges.append(("RX", data))
        return data


# ===========================================================================
# 2. Analysis
# ===========================================================================


def hex_ascii(data: bytes) -> str:
    """Format bytes as hex followed by printable ASCII.

    Args:
        data: Bytes to format.

    Returns:
        Hex bytes separated by spaces, two spaces, then the ASCII form
        between bars with non-printable bytes (outside 0x20-0x7E) as ``.``,
        e.g. ``52 54 2D  |RT-|``.
    """
    text = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in data)
    return f"{data.hex(' ').upper()}  |{text}|"


def version_patterns(version: str) -> List[Tuple[str, bytes]]:
    """List the byte forms in which a version like ``0.29`` may be stored.

    Args:
        version: Version as shown on the radio, ``<major>.<minor>`` with
            decimal digits, e.g. ``0.29``; a leading ``v``/``ver`` is ignored.

    Returns:
        ``(description, bytes)`` pairs: ASCII with and without the dot
        (``0.29``, ``029``, ``29``), BCD (``00 29``) and binary
        (``00 1D``, ``1D 00``, ``1D``), each for the example ``0.29``.
        Duplicates are removed, the first description is kept. BCD is only
        included when both parts are below 100, binary only when both are
        below 256.

    Raises:
        ValueError: If ``version`` is not ``<major>.<minor>`` with ASCII
            digits.
    """
    text = version.lower()
    for prefix in ("ver", "v"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    major_s, sep, minor_s = text.partition(".")
    if not sep or not all(part.isascii() and part.isdigit() for part in (major_s, minor_s)):
        raise ValueError(f"version must look like 0.29, got {version!r}")
    major, minor = int(major_s), int(minor_s)
    candidates = [
        ("ASCII", f"{major_s}.{minor_s}".encode()),
        ("ASCII without dot", f"{major_s}{minor_s}".encode()),
        ("ASCII minor", minor_s.encode()),
    ]
    if major < 100 and minor < 100:
        candidates.append(
            ("BCD major minor", bytes((int(f"{major:02d}", 16), int(f"{minor:02d}", 16))))
        )
    if major < 256 and minor < 256:
        candidates += [
            ("binary major minor", bytes((major, minor))),
            ("binary minor major", bytes((minor, major))),
            ("binary minor", bytes((minor,))),
        ]
    seen = set()
    result = []
    for name, pattern in candidates:
        if pattern not in seen:
            seen.add(pattern)
            result.append((name, pattern))
    return result


def find_version(exchanges: Sequence[Exchange], version: str) -> List[str]:
    """Search the received bytes for a version.

    Args:
        exchanges: Recorded transfers; only ``"RX"`` entries are searched.
        version: Version as shown on the radio, e.g. ``0.29``.

    Returns:
        One line per hit: answer number (1-based, counting received
        answers only), byte offset in that answer, encoding and bytes;
        empty if nothing matches.

    Raises:
        ValueError: If ``version`` is not ``<major>.<minor>`` with digits.
    """
    patterns = version_patterns(version)
    hits = []
    answers = [data for direction, data in exchanges if direction == "RX"]
    for number, data in enumerate(answers, start=1):
        for name, pattern in patterns:
            start = data.find(pattern)
            while start >= 0:
                hits.append(
                    f"answer {number} offset {start}: {name} ({pattern.hex(' ').upper()})"
                )
                start = data.find(pattern, start + 1)
    return hits


def identify(port: str) -> List[Exchange]:
    """Run the handshake on ``port``, end the session and return the log.

    Opens the port at the driver's default speed (115200 baud), calls the
    driver's handshake, sends ``E`` and closes the port. On an error the
    port is still closed, but ``E`` is not sent.

    Args:
        port: Serial device of the programming cable, e.g. ``/dev/ttyUSB0``.

    Returns:
        All transfers in order. If the handshake fails, the exception is
        raised and the transfers so far are lost; check that the radio is
        on and not still in clone mode (switch it off and on), then run
        again.

    Raises:
        drv.CloneTransportError: On a timeout or protocol error, or when
            pyserial is not installed.
        OSError: If the port cannot be opened or fails during the transfer
            (``serial.SerialException`` is a subclass).
    """
    config = drv.CloneSerialConfig(port)
    with RecordingTransport.open(config, logger=drv.LOG) as transport:
        transport.handshake()
        transport._write(drv.END_COMMAND)  # pylint: disable=protected-access  # end session
        return list(transport.exchanges)


# ===========================================================================
# 3. Command line
# ===========================================================================

_LABELS = {
    drv.HANDSHAKE_STRING: "handshake string",
    b"F": "F",
    b"M": "M",
    drv.END_COMMAND: "E (end)",
}
"""Readable names for the fixed commands; the random key frame is printed as
``SEND key frame``."""


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse the command line, run the handshake and print the result.

    Args:
        argv: Arguments without the program name; ``None`` uses
            ``sys.argv[1:]``.

    Returns:
        Exit status: 0 on success, 1 when the handshake failed.

    Raises:
        SystemExit: From argparse: code 2 on invalid arguments (including an
            empty or invalid ``--expect``), code 0 for ``--help``.
    """
    parser = argparse.ArgumentParser(
        description="Show the RT-950 Pro handshake answers in hex (read-only)."
    )
    parser.add_argument("port", help="serial port of the cable, e.g. /dev/ttyUSB0")
    parser.add_argument("--expect", help="version shown on the radio, e.g. 0.29")
    args = parser.parse_args(argv)
    if args.expect is not None:
        try:
            version_patterns(args.expect)
        except ValueError as exc:
            parser.error(str(exc))
    print(f"Driver version: {drv.__version__}")
    try:
        exchanges = identify(args.port)
    except (drv.CloneTransportError, OSError) as exc:
        print(f"Handshake failed: {exc}", file=sys.stderr)
        return 1
    answer = 0
    for direction, data in exchanges:
        if direction == "TX":
            label = _LABELS.get(data, "SEND key frame" if data[:4] == b"SEND" else "?")
            print(f"TX {label} ({len(data)} bytes)")
        else:
            answer += 1
            print(f"  RX answer {answer} ({len(data)} bytes): {hex_ascii(data)}")
    if args.expect is not None:
        hits = find_version(exchanges, args.expect)
        print(f"Search for {args.expect}:")
        for line in hits or ["  no match"]:
            print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
