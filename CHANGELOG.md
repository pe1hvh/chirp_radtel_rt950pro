# Changelog

## Unreleased

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

### Changed
- README: repository layout lists the new documents; the documentation
  section describes the combined page and the `develop` build.
- Template `docs/templates/module.html.jinja2`: *Documents* menu group,
  document sections, *API reference* heading, table and diagram styling.
- Workflow `.github/workflows/docs.yml`: sets `DOCS_BRANCH` (main /
  develop) per build, so links from the documents to GitHub point to the
  branch that was built. An environment variable instead of `--branch`, so
  the older `build.py` on main ignores it until develop is merged.

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
