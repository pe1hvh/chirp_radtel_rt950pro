"""Neutral sample data: two zones with invented, logically named channels.

Used by the tests and by tools/make_sample_image.py. No real-world personal
data: names and repeater entries are fictitious.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("CHIRP_SRC"):
    sys.path.insert(0, os.environ["CHIRP_SRC"])
sys.path.insert(0, ROOT)

from chirp import chirp_common, memmap  # noqa: E402

import radtel_rt950pro as drv  # noqa: E402

ZONE_NAMES = ["VHF-LOCAL", "UHF-LOCAL"]

# (zone, channel, name, MHz, duplex, offset MHz, tmode, tone, mode)
CHANNELS = [
    (1, 1, "S20 CALL", 145.500, "", 0.0, "", 88.5, "FM"),
    (1, 2, "S21", 145.525, "", 0.0, "", 88.5, "FM"),
    (1, 3, "S22", 145.550, "", 0.0, "", 88.5, "FM"),
    (1, 4, "RPT-NORTH", 145.600, "-", 0.6, "Tone", 88.5, "FM"),
    (1, 99, "LAST-VHF", 145.575, "", 0.0, "", 88.5, "NFM"),
    (2, 1, "U-SIMPLEX", 433.500, "", 0.0, "", 88.5, "FM"),
    (2, 2, "RPT-SOUTH", 438.650, "-", 7.6, "Tone", 123.0, "FM"),
    (2, 3, "UHF-NARROW", 433.450, "", 0.0, "", 88.5, "NFM"),
]

_EMPTY_RECORD = b"\xFF" * 8 + b"\x00" * 12 + b"\xFF" * 12


def blank_image() -> bytes:
    """A clone image with empty channels, zeroed settings, empty zone names."""
    data = bytearray()
    for seg in drv.DEFAULT_SEGMENTS:
        if seg.start == 0x0000 and seg.read_command == 0x52:
            data += _EMPTY_RECORD * drv.CHANNEL_COUNT
            data += b"\xFF" * (seg.length - drv.CHANNEL_DATA_BYTES)
        elif seg.start == drv.ZONE_NAME_ADDRESS:
            data += b"\xFF" * seg.length
        elif seg.read_command == 0x54:
            aprs = bytearray(b"\x00" * seg.length)
            # CPS stores the custom message NUL-padded
            aprs[79:119] = b"Hello world!".ljust(40, b"\x00")
            data += aprs
        else:
            data += b"\x00" * seg.length
    assert len(data) == drv._SEGMENT_LENGTH
    return bytes(data)


def load(raw: bytes, fresh_read: bool = True):
    """Load raw bytes into a radio object as if just read from the radio."""
    radio = drv.RT950ProDriver(None)
    radio._mmap = memmap.MemoryMapBytes(raw)
    radio._metadata = {"rt950_layout": drv._LAYOUT_VERSION} if fresh_read else {}
    radio.process_mmap()
    return radio


def sample_radio():
    """Radio object filled with the neutral two-zone sample set."""
    radio = load(blank_image())
    zones = radio.get_sub_devices()
    for zone, number, name, mhz, duplex, offset, tmode, tone, mode in CHANNELS:
        mem = chirp_common.Memory()
        mem.number = number
        mem.empty = False
        mem.freq = int(round(mhz * 1_000_000))
        mem.name = name
        mem.duplex = duplex
        mem.offset = int(round(offset * 1_000_000))
        mem.tmode = tmode
        mem.rtone = tone
        mem.ctone = tone
        mem.mode = mode
        zones[zone - 1].set_memory(mem)
    for index, name in enumerate(ZONE_NAMES):
        radio._image.zone_names[index] = name
    # Present it as a fresh read of a radio holding this data
    return load(drv._build_clone_payload(radio._image))
