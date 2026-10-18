# Changelog

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
