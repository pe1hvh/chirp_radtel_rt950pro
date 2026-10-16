# CHIRP driver for the Radtel RT-950 Pro

A [CHIRP](https://chirpmyradio.com) driver for the Radtel RT-950 Pro with full
support for the radio's **10 zones × 99 channels**, including zone names.

> **Experimental.** A driver bug can mis-program your radio. Always keep a
> backup (CPS `.dat` and a CHIRP `.img`) before writing to the radio.

## Status

| Function | Read | Write |
|---|---|---|
| 990 channels (10 zones × 99) | ✅ | ✅ |
| Zone names | ✅ | ✅ |
| VFO, function, DTMF, modulation settings | ✅ | ✅ |
| APRS settings | ✅ | ⚠️ via cmd `0x58`, see below |

Tested on hardware: Radtel RT-950 Pro, firmware **0.29** (10 × 99 zones),
cross-checked against the vendor CPS **RT-950_CPS v1.3.3**.
Zones were introduced in firmware 0.24; older 960-channel firmware is not
supported for writing channels 961–990.

APRS writes use command `0x58` as reported by NeonPlug; `0x55` (used by earlier
drivers) gets no acknowledgement. The APRS block is only written when you
change an APRS setting.

## What it looks like in CHIRP

Each zone is its own memory tab, named after the zone, with channels 1–99:
`Memories (1 VHF-LOCAL)`, `Memories (2 UHF-LOCAL)`, … Zone names are edited
under **Settings → Zone Names** (max. 10 characters).

CHIRP places this list of tabs on the right. `tools/chirp_list_left.py` can
move it to the left, but it modifies your CHIRP installation (see the script).

## Installation

Save `radtel_rt950pro.py` in a fixed place, e.g. `~/radio/`, and start CHIRP
with it. Developer mode is not needed:

```
chirp --module ~/radio/radtel_rt950pro.py
```

Optionally make that the default with an alias in `~/.bashrc`:

```
alias chirp='chirp --module ~/radio/radtel_rt950pro.py'
```

Then: *Radio → Download from radio*, vendor **Radtel**, model **RT-950 Pro**.

## Safety measures in the driver

- Only data that was read from the radio is written back. Images made with
  older versions of this driver never write zone names.
- `0x7800–0x7BFF` (channels 961–990) is only written when one of those
  channels changed; nothing past `0x7BFF` is ever written. Another project
  reports calibration-like data in this area on some units.
- The APRS block is only written when an APRS setting changed.
- A failed write names the command and address, e.g.
  `No ACK for write cmd 0x57 address 0xC000`.

## Repository layout

| Path | Content |
|---|---|
| `radtel_rt950pro.py` | the driver (single file, as CHIRP expects) |
| `docs/memory-map.md` | confirmed memory map |
| `docs/protocol.md` | clone protocol and timing |
| `tools/find_zone_names.py` | read-only scan of the radio for known text |
| `tools/make_sample_image.py` | sample `.img` with two invented zones |
| `tools/chirp_list_left.py` | optional CHIRP patch: zone list on the left |
| `tests/` | tests against the CHIRP source tree |

## Tests

```
git clone https://github.com/kk7ds/chirp ~/src/chirp
CHIRP_SRC=~/src/chirp python3 -m pytest tests
```

The tests use a neutral, invented two-zone channel set (`tests/sample.py`).

## Origin and credits

- **Nathan G. Barguss, 2E0NBS** — original driver,
  [NathanBarguss/Chirp_Radtel-RT-950-Pro](https://github.com/NathanBarguss/Chirp_Radtel-RT-950-Pro)
  (MIT); this repository starts from upstream commit `254d2cd`.
- **[NeonPlug](https://github.com/infamy/NeonPlug)** (MIT) — APRS write
  command `0x58`, ACK timing, and the warning about `0x7800–0x7FFF`
  (facts only, no code).
- **CHIRP's RT-920 driver** — the idea of fixed 10 × 99 zones; no code taken.
- Discussion: [CHIRP issue #12180](https://chirpmyradio.com/issues/12180).

## License

MIT — see [LICENSE](LICENSE). Copyright © 2025 Nathan G. Barguss (2E0NBS),
© 2026 PE1HVH.

73 de PE1HVH
