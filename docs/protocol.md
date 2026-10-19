# RT-950 Pro clone protocol

115200 baud, 8N1, USB programming cable.

## Session

1. Send `PROGRAMBT9000U` → radio answers `0x06`.
2. Send `F` → 16-byte blob.
3. Send `M` → 12-byte model string (e.g. `RT-950      `).
4. Send `SEND` + 21-byte frame selecting one of 20 XOR keys → `0x06`.
5. Block transfers (below).
6. Send `E` to end the session.

## Handshake answers (measured)

Measured on 2026-10-19 with `tools/ident_dump.py` on one RT-950 Pro with
firmware 0.29 (shown on the radio under *About*), CPS V1.3.3.

| Command | Answer (hex) | ASCII |
|---|---|---|
| `PROGRAMBT9000U` | `06` | |
| `F` | `01 36 01 74 04 00 05 20 02 00 02 60 01 03 30 04` | |
| `M` | `52 54 2D 39 35 30 20 20 20 20 20 20` | `RT-950      ` |
| `SEND` frame | `06` | |

Interpretation of the `F` answer (inference, not confirmed by Radtel or the
CPS): the first twelve bytes read as three pairs of BCD frequencies in MHz,
which match the bands of the radio:

| Bytes | BCD | Probable meaning |
|---|---|---|
| 0–3 | `0136` `0174` | VHF band 136–174 MHz |
| 4–7 | `0400` `0520` | UHF band 400–520 MHz |
| 8–11 | `0200` `0260` | 200–260 MHz band |
| 12–15 | `01 03 30 04` | unknown |

The firmware version is in none of the answers (searched as ASCII `0.29`,
`029` and `29`, BCD `00 29`, binary `00 1D`, `1D 00` and `1D`), and not in
the clone image read with `0x52`/`0x54` either. The `M` answer does not say
"Pro". With the commands above the firmware version cannot be read.

Whether the `F` answer differs between firmware versions, and so could
tell the old 960-channel firmware from the 990-channel firmware, has not
been tested: only one radio with firmware 0.29 was measured.

## Blocks

Header: `cmd, addr_hi, addr_lo, 0x80`.

| Command | Meaning |
|---|---|
| `0x52` | read block, main space → radio answers 4-byte header + 0x80 bytes |
| `0x57` | write block, main space (header + 0x80 bytes) → `0x06` |
| `0x54` | read block, APRS space |
| `0x58` | write block, APRS space → `0x06` |

Payloads are XOR-ed with the session key, except bytes that are `0x00`, `0xFF`,
the key byte or its inverse; key bytes `0x20` (space) leave data unchanged.

## Timing used by the driver

Flash commits can take seconds. ACK time-outs (from NeonPlug's pacing):

| Blocks | ACK time-out | Pause after block |
|---|---|---|
| channels (`< 0x8000`) | 8 s | – |
| settings (`≥ 0x8000`) | 10 s | 50 ms |
| APRS (`0x58`) | 30 s | 100 ms + 500 ms settle before `E` |

## Write order used by the driver

Channels → VFO → function → DTMF → modulation params → modulation names →
zone names (`0xC000`) → APRS (`0x58`, only when changed). APRS stays last,
as in the vendor CPS.
