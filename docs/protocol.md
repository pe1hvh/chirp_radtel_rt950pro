# RT-950 Pro clone protocol

115200 baud, 8N1, USB programming cable.

## Session

1. Send `PROGRAMBT9000U` → radio answers `0x06`.
2. Send `F` → 16-byte blob.
3. Send `M` → 12-byte model string (e.g. `RT-950      `).
4. Send `SEND` + 21-byte frame selecting one of 20 XOR keys → `0x06`.
5. Block transfers (below).
6. Send `E` to end the session.

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
