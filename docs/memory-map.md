# RT-950 Pro memory map

Status legend: **HW** = confirmed on a real RT-950 Pro (firmware 0.29),
**ext** = from another
source, not yet confirmed here.

## Main address space (read `0x52`, write `0x57`, blocks of 0x80 bytes)

| Range | Size | Content | Read | Write | Status |
|---|---|---|---|---|---|
| `0x0000–0x7BBF` | 990 × 32 | Channels: 10 zones × 99. Zone *z*, channel *k* is slot `(z-1)*99 + k` | yes | yes | HW |
| `0x7800–0x7BBF` | 30 × 32 | Channels 961–990 (part of the row above) | yes | only when one of them changed | HW, see note |
| `0x7BC0–0x7FFF` | 0x440 | Unused (all `0xFF` on the test radio) | yes | never | HW |
| `0x8000–0x80FF` | 0x100 | VFO A/B/C | yes | yes | HW |
| `0x9000–0x90FF` | 0x100 | Function settings | yes | yes | HW |
| `0xA000–0xA1FF` | 0x200 | DTMF | yes | yes | HW |
| `0xB000–0xB1FF` | 0x200 | Modulation parameters (FM/AM/SSB) | yes | yes | HW |
| `0xC000–0xC09F` | 10 × 16 | Zone names | yes | yes | HW |
| `0xD000–0xD2FF` | 0x300 | Modulation channel names | yes | yes | HW |
| `0xE000–` | | Unknown, possibly calibration | no | never | ext (NeonPlug) |

**Note on 0x7800–0x7FFF.** On firmware with 10 × 99 zones this holds channels
961–990. NeonPlug reports calibration-like data there on another unit (probably
older 960-channel firmware) and changed TX behaviour after writing it. The
driver therefore only writes `0x7800–0x7BFF` when one of channels 961–990 was
edited, and never writes past `0x7BFF`.

## Channel record (32 bytes)

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | RX frequency |
| 4 | 4 | TX frequency |
| 8 | 2 | RX tone (CTCSS/DCS) |
| 10 | 2 | TX tone |
| 12 | 1 | Signalling group (low nibble) |
| 13 | 1 | PTT ID (low nibble) |
| 14 | 1 | Scrambler (high nibble), power (low nibble) |
| 15 | 1 | Flags: b7 learn FHSS, b6 narrow, b5-4 encryption, b3 busy lockout, b2 scan add, b1 TX enable, b0 AM |
| 16 | 4 | FHSS code |
| 20 | 12 | Name (ASCII, `0xFF` padded) |

Empty slot: RX frequency is `0xFF`.

## Zone name record (16 bytes, at `0xC000 + 16 * (zone - 1)`)

ASCII name, padded with `0xFF` (or `0x00`). The driver reads up to 16 bytes and
writes at most 10 characters, keeping the padding byte the radio already uses.
The maximum length accepted by the radio has not been tested.

## APRS space (read `0x54`, write `0x58`)

| Range | Size | Content | Status |
|---|---|---|---|
| `0x0000–0x007F` | 0x80 | APRS settings; custom message at offset 79 (40 bytes, NUL-padded by the CPS) | read: HW |

Writing with `0x55` gets no ACK on the test radio (HW). NeonPlug writes with
`0x58` and reports the radio accepts it (ext); the driver uses `0x58` and only
writes this block when APRS settings were changed.
