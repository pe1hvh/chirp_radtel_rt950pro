# Changelog

## 0.1.0 — 2026-10-15

First release of this repository, based on the driver by Nathan G. Barguss
(2E0NBS), upstream commit `254d2cd`.
Tested on an RT-950 Pro with firmware 0.29; cross-checked against vendor
CPS RT-950_CPS v1.3.3.

### Added
- 990 channels in 10 zones × 99 (was 960); each zone is its own CHIRP tab
  with channels 1–99.
- Zone names at `0xC000` (10 × 16 bytes): read, shown as tab names, editable
  under Settings → Zone Names, written back.
- APRS write with command `0x58` (was `0x55`, which the radio does not ACK),
  confirmed on hardware; only when APRS settings changed; 30 s ACK time-out.
- Per-block ACK time-outs and pauses for flash commits.
- Error messages name the command and address of a failed block.
- Raw memory view for CHIRP's developer-mode Browser tab.
- Tests with a neutral two-zone sample set; tools for scanning the radio
  and for building a sample image.

### Fixed
- APRS custom message with NUL padding (as stored by the CPS) caused a CHIRP
  settings error.
- Edits were not stored in a saved `.img` (memory map was not refreshed).
- "Illegal set on attribute" warning: the driver modified CHIRP's frozen
  memory object.

### Safety
- `0x7800–0x7BFF` only written when channels 961–990 changed; nothing past
  `0x7BFF` written.
- Images from older driver versions never write zone names; 960-channel
  images never write past `0x7800`.
