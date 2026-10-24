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
| `0x9000–0x90FF` | 0x100 | Function settings (0x60 bytes used; see note on 0x9080) | yes | `0x9000–0x907F` only | HW |
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

**Note on 0x9080–0x90FF.** The driver uses `0x9000–0x905F`. On the test radio
`0x9080–0x90FF` was all `0xFF` in one dump and held data in the next, after
the CPS had written the radio: mostly a shifted copy of `0x9000–0x905F`,
some `0x00` bytes and `3A 65` (HW). What this area is, and whether the CPS or
the radio writes it, is not known. The driver reads the whole segment but
writes only the first block, `0x9000–0x907F`, and leaves `0x9080–0x90FF` to
the radio; an upload from CHIRP left that area unchanged on the test radio
(HW).

**Channel Divide (`0x9026`).** Byte 6 of the second 32-byte part of the
function settings. `0` = *Zone CH Mode*, `1` = *All CH Mode* (CPS labels)
(HW: dumps after the CPS wrote each mode differed only in this byte). The
setting changes only how the radio presents the channels: Zone CH Mode as
10 zones × 99, All CH Mode as one list 1–990 in which channel *n* is slot
*n*, so the zones follow each other and empty slots stay empty. The channel
memory itself is the same in both modes.

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
| 20 | 12 | Name (GB2312, `0xFF` padded) |

Empty slot: RX frequency is `0xFF`.

## VFO record (32 bytes, at `0x8000 + 32 * n`, n = 0 A, 1 B, 2 C)

Values as stored, with the label the CPS *VFO Mode* screen shows. All rows HW:
written with the CPS (V1.3.3, firmware 0.29) and read back.

| Offset | Size | Field | Stored values (CPS label) |
|---|---|---|---|
| 0 | 8 | Rx Freq | one decimal digit per byte, 10 Hz units |
| 8 | 2 | Rx QT/DQT | as the channel tone: `00 00` OFF, `nn 00` 1-based DCS index (1–105 N, 106–210 I), else CTCSS × 10, little-endian |
| 10 | 2 | Tx QT/DQT | as Rx QT/DQT |
| 13 | 1 | Busy Lockout | bit 0: 0 OFF, 1 ON |
| 14 | 1 | Offset Dir, Signalling | bits 5-4: 0 None, 1 Plus, 2 Minus; low nibble 0-14 (CPS shows 1-15) |
| 16 | 1 | Scramble, Tx Power | high nibble 0 OFF, 1-8 (Scramble 1-8); low nibble 0 High, 1 Middle, 2 Low |
| 17 | 1 | Bandwidth, Encryption, RxModulation | bit 6: 0 Wide, 1 Narrow; bits 5-4: 0 OFF, 1-3 (Encryption 1-3); bit 0: 0 FM, 1 AM; bit 7 learn FHSS (not shown by the CPS; from the driver source, not confirmed) |
| 18 | 1 | Freq Band | low nibble 0 VHF, 1 UHF. Read-only in the CPS, which derives it from Rx Freq: VHF below 300 MHz, UHF from 300 MHz (boundary measured with the CPS). The driver sets it the same way when Rx Freq is edited |
| 19 | 1 | Step Freq | low nibble 0-9: 2.5, 5.0, 6.25, 8.33, 10.0, 12.5, 20.0, 25.0, 50.0, 100.0 kHz |
| 20 | 7 | Offset Freq | one decimal digit per byte, 100 Hz units |

Bytes 12, 15 and 27-31 were `0xFF` on the test radio.

## Modulation parameters (`0xB000`, global fields)

Fields of the CPS *FM/AM/SSB Modulation* screen that are not part of the
FM, AM or SSB channel tables. `0xFF` means not set. Labels and lists as in
the CPS. On the radio (HW) the first value of each list was read back, and
AM = 1 for Modulation Mode; the other values follow the order of the CPS
list (not confirmed).

| Offset | Field | Stored values (CPS label) |
|---|---|---|
| 32 | FM current channel | 0–14 |
| 33 | Work Mode | 0 VFO Mode, 1 CH Mode |
| 66 | AM current channel | 0–14 |
| 67 | Modulation Mode | 0 FM, 1 AM, 2 LSB, 3 USB, 4 CW |
| 68 | AM Rx Gain | 0 AGC, 1 0dB, 2–36 −1dB to −35dB |
| 149 | SSB current channel | 0–14 |
| 150 | SSB Step Freq | 0 1K, 1 5K, 2 10K, 3 100K, 4 500K, 5 1000K |
| 151 | AM Step Freq | 0 1K, 1 5K, 2 10K, 3 100K |
| 152 | SSB Rx Gain | as AM Rx Gain |

## Zone name record (16 bytes, at `0xC000 + 16 * (zone - 1)`)

ASCII name, padded with `0xFF` (or `0x00`). The driver reads up to 16 bytes;
an edited name is written with at most 12 characters, an unedited name as it
was read, keeping the padding byte the radio already uses.
The CPS (*Cur Zone Name*) cuts a name to 12 characters; a 12-character name
was written with the CPS and read back (HW).

## APRS space (read `0x54`, write `0x58`)

| Range | Size | Content | Status |
|---|---|---|---|
| `0x0000–0x007F` | 0x80 | APRS settings; custom message at offset 79 (40 bytes, NUL-padded by the CPS) | read and write: HW |

Writing with `0x58` works: written and read back on the test radio (HW),
first reported by NeonPlug. Writing with `0x55` gets no ACK (HW). The driver
only writes this block when APRS settings were changed.
