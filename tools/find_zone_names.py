#!/usr/bin/env python3
"""Search the RT-950 Pro address space for known text. READ-ONLY.

Reads 0x80-byte blocks from address ranges the driver does not read, searches
them for the given strings (e.g. your zone names) and writes a dump of all
non-empty blocks. Nothing is written to the radio.

This is how the zone-name address (0xC000) was found.

Usage (with CHIRP's Python, which has pyserial):
    ~/.local/share/pipx/venvs/chirp/bin/python tools/find_zone_names.py \\
        /dev/ttyUSB0 "MyZone1" "MyZone2"

Close CHIRP first so the serial port is free.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import serial  # noqa: E402
import radtel_rt950pro as drv  # noqa: E402

# (read command, start, end) - ranges the driver does not (fully) read
RANGES = [
    (0x52, 0x8100, 0x9000),
    (0x52, 0x9100, 0xA000),
    (0x52, 0xA200, 0xB000),
    (0x52, 0xB200, 0xD000),
    (0x52, 0xD300, 0x10000),
    (0x54, 0x0080, 0x1000),
]


def read_block(transport, cmd, addr):
    transport._write(bytes((cmd, (addr >> 8) & 0xFF, addr & 0xFF, drv.READ_BLOCK)))
    block = transport._read_exact(drv.BLOCK_HEADER + drv.READ_BLOCK)
    return bytes(transport._apply_xor(bytearray(block[drv.BLOCK_HEADER:])))


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    needles = [arg.encode("ascii") for arg in sys.argv[2:]]
    port = serial.Serial(sys.argv[1], baudrate=115200, timeout=2, write_timeout=2)
    transport = drv.CloneSerialTransport(port, logger=drv.LOG)
    print("Radio:", transport.handshake())
    dump, found, stopped = {}, [], None
    try:
        for cmd, start, end in RANGES:
            print("Reading cmd 0x%02X  0x%04X-0x%04X" % (cmd, start, end - 1))
            for addr in range(start, end, drv.READ_BLOCK):
                try:
                    data = read_block(transport, cmd, addr)
                except Exception as exc:
                    stopped = (cmd, addr, exc)
                    break
                dump[(cmd, addr)] = data
                for needle in needles:
                    pos = data.find(needle)
                    if pos >= 0:
                        found.append((cmd, addr + pos, needle))
            if stopped:
                break
    finally:
        try:
            transport._write(drv.END_COMMAND)
        except Exception:
            pass
        transport.close()

    out = "rt950_dump_%s.txt" % time.strftime("%Y%m%d_%H%M%S")
    with open(out, "w") as fh:
        for (cmd, addr), data in sorted(dump.items()):
            if data in (b"\xFF" * len(data), b"\x00" * len(data)):
                continue
            for i in range(0, len(data), 16):
                row = data[i:i + 16]
                text = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
                fh.write("%02X %04X  %s  %s\n" % (cmd, addr + i, row.hex(" "), text))

    print()
    if stopped:
        print("Stopped at cmd 0x%02X address 0x%04X: %s" % stopped)
        print("Power-cycle the radio before using CHIRP again.")
    if found:
        print("FOUND:")
        for cmd, addr, needle in found:
            print("  cmd 0x%02X  address 0x%04X  %s" % (cmd, addr, needle.decode()))
    else:
        print("Search strings not found in the scanned ranges.")
    print("Dump (non-empty blocks only):", out)


if __name__ == "__main__":
    main()
