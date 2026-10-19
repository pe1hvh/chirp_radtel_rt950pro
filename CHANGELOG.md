# Changelog

## 0.1.5 — 2026-10-19

Bug fixes from tests on a real radio with the original CPS (V1.3.3,
firmware 0.29): values were set in the CPS, written to the radio and read
back raw, so every value below is the radio's own encoding. Also fixes the
known bugs listed in `docs/status.md`, except the unused `_ToneInfo`.
Uploads from CHIRP were checked the same way: only the edited bytes change.

### Added
- `tools/raw_dump.py`: reads the radio and saves the clone image as read
  (XOR-decoded, otherwise unchanged; read-only). Uses only the transport
  layer, so unlike a `.img` saved by CHIRP the bytes have not passed through
  the driver's encoders. Comparing both files from the same radio state shows
  which bytes the driver changes without an edit.
- `tests/test_radio_values.py`: regression tests for the values measured on
  the radio (neutral, invented frequencies).
- `tests/test_known_issues.py`: tests for the known issues fixed in this
  release.
- CHIRP `Cross` tone mode with all of CHIRP's cross modes. A channel with
  an RX tone only, a TX DCS only, two different CTCSS tones, two different
  DCS codes or mixed CTCSS/DCS is shown as `Cross` and written back unchanged. In the
  memory grid CHIRP asks for the cross mode after `Cross` is chosen; the
  memory's *Properties* dialog sets all tone fields at once.
- `docs/memory-map.md`: VFO record table, the global modulation parameters
  and a note on `0x9080–0x90FF`.

### Changed
- VFO settings now show the fields of the CPS *VFO Mode* screen, with its
  labels, choices and order: Rx Freq, Rx QT/DQT, Tx QT/DQT, Busy Lockout,
  Offset Dir, Signalling, Tx Power, Scramble, Bandwidth, Encryption,
  RxModulation, Freq Band, Step Freq, Offset Freq. The groups are named
  VFO-A to VFO-C. Rx and Tx QT/DQT are new in the settings.
- Learn FHSS and the offset direction "Split" are no longer shown for the
  VFOs (the CPS does not offer them); their stored values are kept.
- A stored VFO value the CPS does not offer is shown as `Unknown (<value>)`
  and is left unchanged when settings are applied. Exceptions: Tx Power
  above Low is read as Low, and an unknown DCS index (see Known issues).
- Freq Band is read-only (VHF/UHF), as in the CPS, and follows Rx Freq when
  that is edited: VHF below 300 MHz, UHF from 300 MHz (boundary measured
  with the CPS).
- Broadcast/Modulation settings use the CPS labels and lists: Work Mode
  (VFO Mode, CH Mode), Modulation Mode (FM, AM, LSB, USB, CW), AM and SSB
  Step Freq, AM and SSB Rx Gain (AGC, 0dB, −1dB to −35dB). A value that is
  not set is shown as `Not set` and kept. Current channels are 0-14.
- Settings apply runs only the callbacks of settings that were changed.
- Of the function segment only `0x9000–0x907F` is written; `0x9080–0x90FF`,
  whose meaning is unknown and which the radio changes, is left to the
  radio. An upload is one block shorter.
- Busy Lockout is an OFF/ON list instead of a checkbox, and Bandwidth lists
  Wide first, as in the CPS.

### Fixed
- VFO power was always read as High. Changing any other setting then wrote
  High back, so a Low or Middle VFO became High.
- VFO step: only 6 of the radio's 10 steps were known and from 8.33 kHz on
  the labels were wrong. Applying settings changed a VFO on 20, 25, 50 or
  100 kHz to 2.5 kHz. Now 2.5, 5.0, 6.25, 8.33, 10.0, 12.5, 20.0, 25.0, 50.0
  and 100.0 kHz (stored 0-9).
- VFO band was set to 0 on every settings apply; the radio stores 0 VHF and
  1 UHF.
- VFO Signalling showed the stored value (0-15); the CPS shows it plus one
  and the radio stores 0-14. Now 1-15 as in the CPS.
- VFO Scramble offered 0-9; the radio knows OFF and 1-8.
- Channel encryption 3 was reset to 0 when a channel was edited; the radio
  knows 0-3.
- Ranges of settings without a CHIRP field, as the CPS lists them: PF1
  Short/Long 0-7, PF2 Short/Long 0-6 (were 0-31), Timed Beacon Time 0-9
  (was 0-60), Radio Symbol 0-4 (was 0-99).
- Zone names of more than 10 characters failed to load in the settings
  ("must be between 0 and 10 chars") and the field was left out. The CPS and
  the radio use up to 12 characters; the driver now does too. A longer
  name written by other software (the slot holds 16 bytes) also loads and
  is kept unless it is edited.
- DCS polarity: the radio's inverted DCS (`I`) is shown as CHIRP's reverse
  polarity `R` and `R` is written as `I`. Before, an inverted DCS channel
  showed an invalid polarity and `R` could not be saved.
- RX-only tones and mixed CTCSS/DCS were lost when such a channel was
  edited (now CHIRP `Cross`, see Added).
- Applying settings turned values that were not set (`0xFF`) into defaults,
  for example after merely opening the settings and applying one edit.
- Unset modulation fields (`0xFF`) were written as `0x00` on every upload;
  the modulation and APRS encoders now write only edited fields, so unusual
  stored bytes are kept.
- An edited channel record lost the high nibbles of bytes 12 and 13.
- `set_memory` modified CHIRP's frozen memory object for a DTCS memory with
  TX code 0.
- A modulation channel name or APRS custom message in GB2312 could be cut
  inside a two-byte character.
- A negative DTMF code group index was accepted.

### Known issues
- A VFO tone with a DCS index the driver does not know is shown as OFF;
  choosing OFF then does not clear it.

## 0.1.4 — 2026-10-19

### Added
- `__version__` in `radtel_rt950pro.py` (and a `Version` line in the header
  comment), so a downloaded copy of the driver shows which version it is.
  It equals the latest entry in this changelog and the release tag
  `v<version>` on GitHub; 0.1.3 is the first tagged release (`v0.1.3`).
- The documentation page shows the version after the module name in its
  heading, e.g. `radtel_rt950pro (v0.1.4)`. `docs/build.py` passes the
  driver's `__version__` to the template; without it no version is shown.

### Changed
- Template `docs/templates/module.html.jinja2`: replaces pdoc's
  `module_name()` heading with one that adds the version.

## 0.1.3 — 2026-10-19

Documentation only. The driver's code is unchanged.

### Added
- `docs/chirp-interface.md`: how CHIRP and the driver interact — entry
  points, declared features, download, wire protocol, opening images,
  zones as sub-devices, memory and tone mapping, settings, saving and
  upload — with nine sequence diagrams (`docs/diagrams/seq-*.svg`).
  Verified against the CHIRP source (kk7ds/chirp `0a9be8e`).
- `docs/fto.md`: functional and technical design — functions, safety
  rules, layers, data model, per-layer design, write plan, error mapping,
  logging, tests — with layer, class and write-plan diagrams
  (`docs/diagrams/fto-*.svg`).
- Five observations from the interface analysis, documented in
  `docs/chirp-interface.md` §15 (not fixed): APRS/channel 961-990
  snapshots are not refreshed after an upload; memory comments are not
  found after a zone rename; read progress text past channel 990; repeated
  payload builds in `sync_out()`; the developer Browser tab shows stale
  bytes after an edit and its own edits are lost.

- The documentation page (`radtel_rt950pro.html`) now shows both documents
  above the API reference, with a *Documents* group in the side menu.
  `docs/build.py` converts the Markdown with pdoc's markdown2 settings, gives
  headings GitHub-style anchors per document (`design-…`, `interface-…`),
  links names in code font to the API, sends links to other Markdown files to
  GitHub for the built branch (`--branch`, default the current git branch),
  copies `docs/diagrams` next to the page (click opens full size), stops on
  a broken link between documents, and links each API layer heading to its
  design chapter.
- Diagram generators in `tools/`: `seqsvg.py` (renders sequence diagrams as
  SVG), `make_diagrams.py` (the nine sequence diagrams) and
  `make_fto_diagrams.py` (the three structure diagrams). They regenerate all
  12 files in `docs/diagrams` byte-identical; `docs/fto.md` B13 describes how
  to run them. Standard library only.

### Changed
- README: repository layout lists the new documents; the documentation
  section describes the combined page and the `develop` build.
- Template `docs/templates/module.html.jinja2`: *Documents* menu group,
  document sections, *API reference* heading, table and diagram styling.
- Workflow `.github/workflows/docs.yml`: sets `DOCS_BRANCH` (main /
  develop) per build, so links from the documents to GitHub point to the
  branch that was built. An environment variable instead of `--branch`, so
  the older `build.py` on main ignores it until develop is merged.
- Workflow `.github/workflows/docs.yml`: the docstring check also runs
  pylint's missing-docstring checks with no exemption for names starting
  with `_`. pydocstyle only checks the names in `__all__`, so a private (or
  unlisted) class, function or method without a docstring passed unnoticed.
  Nested functions are still not checked. README and `docs/fto.md` B13
  describe the check.

### Fixed
- `docs/memory-map.md`: the channel name is GB2312, not ASCII, as in the
  code (`ChannelRecord`, `_encode_name`).

### Known issues (found while checking the page, not fixed)
- Already in 0.1.2: pdoc gives docstring section headings the same `id` on
  every object (`returns`, `arguments`, `raises`, `warning`, `yields`,
  `byte-layout`), and one link points to `#_CloneModeRadio` (a CHIRP
  stand-in that is not documented).

## 0.1.2 — 2026-10-18

Documentation only. The driver's code is unchanged: an AST comparison with
all docstrings removed shows no difference, and the tests pass.

### Added
- Every documented object has a meaningful docstring: all classes,
  functions, methods, fields, instance attributes and constants, public and
  private, with every parameter, return value and yield described (377
  objects). The 23 instance attributes that had none now have one.
- Two independent reviews checked all docstrings against the code; their
  51 findings were corrected or completed (see Fixed).
- `docs/build.py`: builds the documentation grouped by driver layer and
  section, taken from the banner comments in the source; private objects
  are documented as well.
- New pdoc template (`docs/templates/module.html.jinja2`):
  - side menu "Driver layers" with layers 1-6, their sections, and per
    class Constructor, Fields, Properties and Methods;
  - public objects first with an open lock, private ones after a dashed
    line with a closed lock; yellow locks for methods and functions,
    orange for classes, properties, fields and constants; a legend;
  - item counts per layer and section, with a breakdown on hover;
  - "Expand all", "Collapse all" and "Hide private" buttons; the menu
    opens and highlights the entry of the current anchor;
  - a heading with a one-line description per layer on the page.
- The docs workflow checks docstrings (pydocstyle, pydoclint) before
  building and stops on a missing parameter, return value or yield.

### Changed
- Workflow builds with `python docs/build.py`; pdoc pinned to 16.x.
- README: documentation section describes menu, locks and local build.
- `.gitignore`: `site/`, `doclint.txt`.

### Fixed
- Docstrings that did not match the code, among others: the module
  docstring's read-modify-write and 0x7BC0-0x7FFF claims, `LOG`,
  `_encode_name`, `encode_vfo_section`, `encode_function_section`,
  `encode_dtmf_section`, `encode_aprs_section`, `parse_aprs_section`,
  `_build_write_plan`, `RT950ProRadio._memsize`, `set_memory`, `sync_in`,
  `_build_vfo_group`, `_update_tones_from_memory`, `get_dtmf_code_group`.
- Literal `::` after "Memory layout" and "Byte layout" in the rendered page.
- Example zone names in docstrings are neutral.

### Known issues (found in the review, documented in the code, not fixed)
- VFO power is always decoded as HIGH (`parse_vfo_section`); editing any
  other VFO field writes High power back.
- `encode_modulation_sections` turns unset (0xFF) fields into 0x00 without
  any edit (144 bytes for an all-0xFF block); the block is part of every
  upload.
- `set_memory` modifies CHIRP's (frozen) memory object for a DTCS memory
  with TX code 0.
- Range/mask mismatches: `key_side1/2_short/long` (0-31 allowed, 4 bits
  stored), APRS `timed_beacon_time` (0-60) and `radio_symbol` (0-99) (4 bits
  stored); channel encryption 3 offered in CHIRP but reset to 0.
- `encode_aprs_section` normalises out-of-range stored values; an edited
  channel record loses the high nibbles of bytes 12-13.

## 0.1.1 — 2026-10-18

Code quality and documentation. Channel, settings and clone behaviour are
unchanged: an old/new comparison through CHIRP (read, memories, zones,
settings, write plan) gives byte-identical results.

### Added
- Docstrings (Google style) for every class, function, method and module
  constant, including private and nested helpers. Byte layouts of the
  channel record, VFO entry, modulation block and clone protocol are
  documented in the code.
- Module docstring with the memory map and the layer structure of the
  driver.
- GitHub Actions workflow `.github/workflows/docs.yml`: renders the
  Google-style docstrings with pdoc on every push to `main` and publishes
  the API documentation on GitHub Pages. A pdoc template override
  (`docs/templates/module.html.jinja2`) titles the pages "Radtel RT-950 Pro
  driver for CHIRP" and groups the side menu into collapsible sections
  (Classes, Functions, Variables) with expandable classes, "Expand all" /
  "Collapse all" buttons, and a menu that opens at the current anchor.
- README links to the published documentation:
  <https://pe1hvh.github.io/chirp_radtel_rt950pro>.
- `docs/status.md`: development status, sources, risks and known bugs
  (English; replaces the Dutch `docs/rt950pro-chirp-geheugenkaart.md`).

### Changed
- One `__all__` listing the complete public API. Previously six `__all__`
  lists overwrote each other and pydoc showed only `RT950ProRadio`.
- The module imports without CHIRP and without pyserial, so pydoc and
  documentation builds work anywhere. `CloneSerialTransport.open()` now
  raises `CloneTransportError` when pyserial is missing and no
  `serial_class` is given.
- pylint score 10.00/10 (default settings, 100-character lines; was 9.07).
  Deliberate `except Exception` blocks carry an inline reason; design-size
  checks are disabled module-wide with a justification.
- pydocstyle (Google convention) reports no issues.

### Fixed
- `CloneSerialTransport` without a logger raised `NameError`
  (`get_logger` did not exist).
- `Callable` was used without being imported.
- Removed dead code: an unused `settings` stand-in with seven
  self-assignments and the never-read attribute `_channel_write_bytes`.
- Outdated comments still referred to APRS write command `0x55`.
- Side menu of the documentation did not collapse: the template in the
  repository was the title-only version.
- README named the vendor CPS `RT-950_CPS`; it is `RT-950PRO_CPS`.

### Known issues
- Applying settings resets the VFO frequency band to 0: the band list
  value is read as an integer (`_apply_vfo_freq_band`).
- Inverted DCS: the radio uses polarity `I`, CHIRP uses `R`. An inverted
  code from the radio gives an invalid CHIRP polarity (`IN`); `R` from
  CHIRP raises `ValueError` when encoding.
- RX-only tones and mixed CTCSS/DCS are lost when such a channel is edited
  (no CHIRP `Cross` mode).
- Applying settings turns unset (0xFF) values into defaults, so the APRS
  block is written even when nothing was changed by the user.

## 0.1.0 — 2026-10-15

First release of this repository, based on the driver by Nathan G. Barguss
(2E0NBS), upstream commit `254d2cd`.
Tested on an RT-950 Pro with firmware 0.29; cross-checked against vendor
CPS RT-950PRO_CPS v1.3.3.

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
