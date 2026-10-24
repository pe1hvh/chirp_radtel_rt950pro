# RT-950 Pro — CHIRP driver: memory map and status (updated 2026-10-24)

Radio: Radtel RT-950 Pro, firmware 0.29 (10 x 99 zones). Vendor CPS: RT-950PRO_CPS v1.3.3 (20260622).
Base: experimental driver by 2E0NBS (NathanBarguss/Chirp_Radtel-RT-950-Pro @254d2cd, MIT), modified.

## This repository
- Name: `chirp_radtel_rt950pro`, one clean first commit (0.1.0), author PE1HVH, MIT with copyright Nathan Barguss 2025 + PE1HVH 2026. No Claude lines in the commit.
- Content: radtel_rt950pro.py (single file), LICENSE, README (English), CHANGELOG, docs/memory-map.md, docs/protocol.md, tools/ (find_zone_names, raw_dump, ident_dump, check_docstrings, make_sample_image, chirp_list_left, diagram generators), tests/ (neutral test set: VHF-LOCAL and UHF-LOCAL).
- Installation in the README: (1) Help → Load module from issue 12180 (per session, only while the issue is open, warning "not a recognized CHIRP developer"); (2) copy to `~/.local/share/pipx/venvs/chirp/lib/python3.*/site-packages/chirp/drivers/` (may be gone after a reinstall or a new Python version; not for the Windows installer).
- No dependencies other than CHIRP (with pyserial); pytest only for the tests; Python ≥ 3.10.

## Code quality (2026-10-18)
- pylint 10.00/10 (default settings, max. 100 characters), pydocstyle Google convention clean, pydoc works with and without CHIRP and without pyserial. Without CHIRP the radio cannot be used: `get_features`, `get_settings`, `get_memory` and `set_memory` raise `RadioError` (0.1.6).
- One `__all__` with the complete public API (previously the last `__all__ = ["RT950ProRadio"]` overwrote the others, so pydoc showed only that class).
- Google-style docstrings for all classes, functions (including private and nested ones, and the CHIRP stand-ins) and module constants; since 0.1.6 enforced by `tools/check_docstrings.py` for the driver, `tools/*.py` and `docs/build.py`.
- Behaviour demonstrably unchanged: an AST diff without docstrings shows only intended changes; an old/new comparison through real CHIRP (read, memories, set_memory, zones, settings, write plan) is byte-identical.
- Fixed latent bug: `get_logger` did not exist (NameError for a transport without a logger).
- CHIRP's own style check (tools/cpep8.py, pep8/flake8) uses 79 characters; reformat before a PR.
- Automatic documentation: the GitHub Action `.github/workflows/docs.yml` checks the docstrings (pydocstyle, pydoclint) and builds the documentation with `docs/build.py` (pdoc, Google style, grouped by driver layer, template in `docs/templates/`) and publishes it on GitHub Pages (Settings → Pages → Source: GitHub Actions): <https://pe1hvh.github.io/chirp_radtel_rt950pro>.

## Confirmed on the real radio (PE1HVH)
| Address / cmd | Content | Read | Write |
|---|---|---|---|
| 0x52/0x57 0x0000–0x7BBF | 990 channels x 32 bytes = 10 zones x 99 (zone n channel k = slot (n-1)*99+k) | ok | ok |
| 0x52/0x57 0x8000, 0x9000, 0xA000, 0xB000, 0xD000 | VFO, function, DTMF, modulation | ok | ok |
| 0x52/0x57 0xC000–0xC09F | 10 zone names x 16 bytes (NoodNetOv at 0xC000 … ZoneTen at 0xC090) | ok | ok |
| 0x52/0x57 0x9026 | Channel Divide: 0 = Zone CH Mode, 1 = All CH Mode (2026-10-24: two raw dumps after the CPS wrote each mode; only this byte differed) | ok | ok (0.1.7) |
| 0x54/0x58 0x0000 | APRS (128 bytes) | ok | ok with 0x58 (written and read back); 0x55 gets NO ACK |

0xC800 (zone names on the RT-920) is NOT the address on the RT-950 Pro.
On PE1HVH's radio 0x7800–0x7FFF is all 0xFF (empty channels 961–990).
DCS list in the driver: 210 codes; index 1–105 = N, 106–210 = I (polarity "I", not CHIRP's "R").

## From the CPS changelog (RT-950PRO_CPS, primary source: start-up notice of CPS v1.3.3)
- v1.0.5 (20250916): "channel division" added (the setting *Channel Divide*, byte 0x9026; in CHIRP since 0.1.7); v1.2.0 (20251114): editing zone names + CHIRP CSV export; v1.1.0/1.1.1 (Oct 2025): CHIRP CSV import.
- v1.2.1 (20251129): channel memory changed from 960 (15 zones x 64) to 990 (10 zones x 99). So zones already existed before 0.24, only as 15 x 64.
- v1.2.2 (20251203): storage structure changed; CPS files from before 1.2.2 no longer open.
- v1.3.0 (20260209) and v1.3.3 (20260622): new settings (rx interruption, breathing light, NOAA alarm, backlight, power-on delay, VFO scan range; APRS working channel, channel mute, tx data reporting, beacon pop-up time). Probably in the function/APRS blocks; offsets unknown.

## From other sources
- NeonPlug (infamy/NeonPlug PR #197, merged 2026-10-10): first report of APRS write 0x58; ACK wait time up to 30 s.
- NeonPlug: never write 0x7800–0x7FFF and ≥0xE000 — calibration-like data on one owner's radio (probably 960-channel firmware). Not verified by PE1HVH.
- Fork Dadud/Chirp_Radtel-RT-950-Pro (Kyle Brockman, Dec 2025): CHANNEL_COUNT 990 but still reads 0x0000–0x7800 → inconsistent layout; no zones; APRS still 0x55.
- CHIRP issue #12180: open (status New), no driver merged; FW 0.24 (251201) belongs to the transition to 10 x 99.

## Risk
- Radios with old 960-channel firmware (15 x 64): 960 x 32 = 0x7800, so channels end at 0x77FF. A driver that writes 990 channels (up to 0x7BBF) overwrites 0x7800–0x7BBF there — exactly the area where NeonPlug saw calibration-like data. The driver must detect the firmware/layout and refuse to write on 960-channel firmware (or write only up to 0x77FF). Inference, not tested.
- New settings from CPS 1.3.x: the driver must treat settings blocks as read-modify-write, never build them from default values.

## Known bugs (found in the review of 2026-10-18; fixed items marked)
1. *Fixed in 0.1.5* (Freq Band is read-only and follows Rx Freq, as in the CPS). VFO band becomes 0 on every settings apply: `_apply_vfo_freq_band` read a list value with `_value_as_int`; CHIRP returns the label text → 0. Tested: band 2 → 0, byte 0x8012 becomes 0x00.
2. *Fixed in 0.1.5* (I↔R translated; checked on a radio). DCS polarity: the radio uses "I", CHIRP "R". Inverted DCS from the radio gives CHIRP polarity "IN"/"NI" (invalid); "R" from CHIRP raises `ValueError: Unsupported DCS code D023R` when encoding. Fixed by translating I↔R in `_tone_to_chirp` and `_tone_from_chirp`.
3. *Fixed in 0.1.5* (CHIRP `Cross` with all its cross modes; checked on a radio). Tones without CHIRP "Cross": RX-only tone and mixed CTCSS/DCS are lost when such a channel is edited.
4. *Fixed in 0.1.5* (only changed settings are applied). Settings apply turns "not set" (0xFF) into a default value (e.g. APRS → write_aprs becomes True after merely opening and applying).
5. *Removed in 0.1.6.* `_ToneInfo` was unused.
6. *Fixed in 0.1.5.* VFO power is always decoded as HIGH: `parse_vfo_section` uses `min(raw, PowerLevel.HIGH.value)` (= 0). Editing any other VFO field writes High back to byte 16. Fix: `PowerLevel.LOW.value`, as in `ChannelRecord.from_bytes`.
7. *Fixed in 0.1.5* (only edited fields are written). `encode_modulation_sections` writes unset fields (`None`, parsed from 0x0000/0xFFFF and 0x00/0xFF) as 0x00, so an all-0xFF parameter block changes 144 bytes without any edit; the block is part of every upload.
8. *Fixed in 0.1.5* (the memory is no longer modified). `RT950ProRadio.set_memory` modifies CHIRP's `FrozenMemory` for a DTCS memory with TX code 0 (`mem.tmode = ""`); fix: work on `mem.dupe()`.
9. *Fixed in 0.1.5* (ranges now as in the CPS, checked on a radio). Range/mask mismatches: `key_side1/2_short/long` allow 0-31 but are stored in 4 bits; APRS `timed_beacon_time` (0-60) and `radio_symbol` (0-99) likewise; channel encryption 3 is offered in CHIRP but reset to 0.
10. *Fixed in 0.1.5* (stored values kept unless edited; high nibbles of bytes 12-13 kept). `encode_aprs_section` normalises out-of-range stored values without an edit; an edited channel record loses the high nibbles of bytes 12-13.

Bugs 6-10 were found in the independent docstring review of 2026-10-18 and confirmed with tests; all are fixed in 0.1.5, each with a test.

## Route to official CHIRP
- PR on kk7ds/chirp: tests pass, rebased, `Fixes/Related to #12180`, test image `tests/images/Radtel_RT-950_Pro.img`, MemoryMapBytes, files GPLv3 or without licence text.
- The current driver (MIT, own architecture) does not fit; proposal: RT-950 Pro as a subclass of the RT-920 driver (radtel_rt900.py), as Fred Trimble suggested earlier.
- The "Developer" role on chirpmyradio.com (decides the warning on Load module from issue) is granted by the maintainer (Dan Smith, KK7DS); no fixed criteria found.
- Proposal drafted in English for issue #12180 (questions: subclass wanted?, review by Fred?, test image with neutral channels ok?).

## Open
- A VFO tone with a DCS index the driver does not know is shown as OFF; choosing OFF then does not clear it.
- Find out what `0x9080–0x90FF` is (see the memory map). Since 0.1.5 the driver writes only `0x9000–0x907F` of the function segment.
- Compare the handshake (PROGRAMBT9000U + XOR) with the RT-920 protocol.
- Add firmware/layout detection (960 vs 990) before writing. The firmware version cannot be read with the known commands (`docs/protocol.md`, *Handshake answers*); the 16-byte `F` answer is a candidate if it differs between firmware versions (not tested).
- Await the maintainers' response to the proposal in #12180.
