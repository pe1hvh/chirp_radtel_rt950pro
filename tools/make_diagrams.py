#!/usr/bin/env python3
"""Generate the sequence diagrams in ``docs/diagrams`` (``seq-01`` to ``seq-09``).

Each function below builds one diagram of ``docs/chirp-interface.md`` with
:class:`seqsvg.Seq`; :func:`main` writes them as SVG files. Run from the
repository root after changing a diagram, then check the result in a
browser:

    python3 tools/make_diagrams.py              # writes to docs/diagrams
    python3 tools/make_diagrams.py some/dir     # other output directory

The structure diagrams (``fto-*.svg``) are made by
``tools/make_fto_diagrams.py``.
"""

import sys
from pathlib import Path
from typing import Callable, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seqsvg import Seq  # noqa: E402  pylint: disable=wrong-import-position

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"
"""Default output directory: ``docs/diagrams`` of this repository."""


def driver_loading() -> Seq:
    """Diagram 1: how CHIRP loads the module and registers the driver.

    Described in ``docs/chirp-interface.md`` section 3.

    Returns:
        The diagram, ready to render.
    """
    s = Seq("1. Loading and registering the driver", [
        ("user", "User"),
        ("chirp", "CHIRP\n(wxui main)"),
        ("dir", "chirp.directory"),
        ("mod", "radtel_rt950pro.py\n(module)"),
    ])
    s.frame("alt", "option 1: Help > Load module from issue... (#12180)", "user", "mod")
    s.msg("user", "chirp", "issue 12180, pick newest radtel_rt950pro.py")
    s.self_call("chirp",
                "IssueModuleLoader saves attachment as\n"
                "temp file loaded-<id>-....py; load_module(file)")
    s.msg("chirp", "dir", "enable_reregistrations()")
    s.msg("chirp", "mod", "exec_module() as chirp.loaded.<temp file name>")
    s.els("option 2: file copied into chirp/drivers/")
    s.msg("user", "chirp", "start CHIRP")
    s.msg("chirp", "dir", "import_drivers()")
    s.msg("dir", "mod", "__import__('chirp.drivers.radtel_rt950pro')")
    s.end()
    s.self_call("mod", "define layers 1-5 (standard library only)")
    s.self_call("mod",
                "layer 6: from chirp import chirp_common, directory,\n"
                "errors, memmap, bitwise, settings; define classes")
    s.msg("mod", "dir", "@directory.register(RT950ProDriver)")
    s.self_call("dir", "DRV_TO_RADIO['Radtel_RT-950_Pro'] = RT950ProDriver")
    s.ret("dir", "mod", "class (unchanged)")
    s.ret("mod", "chirp", "module ready")
    s.note("chirp", "chirp", "Radtel / RT-950 Pro now in the\nradio list of Download and Open")
    return s


def download() -> Seq:
    """Diagram 2: download from the radio, ``sync_in()``.

    Described in ``docs/chirp-interface.md`` section 4.

    Returns:
        The diagram, ready to render.
    """
    s = Seq("2. Download from radio (sync_in)", [
        ("user", "User"),
        ("dlg", "ChirpDownloadDialog\n+ CloneThread"),
        ("drv", "RT950ProDriver"),
        ("tr", "CloneSerialTransport"),
        ("radio", "RT-950 Pro"),
    ])
    s.msg("user", "dlg", "Radio > Download: port, Radtel, RT-950 Pro")
    s.msg("dlg", "drv", "detect_from_serial(serial)")
    s.ret("drv", "dlg", "NotImplementedError (no detection)")
    s.msg("dlg", "drv", "RT950ProDriver(serial)")
    s.self_call("drv",
                "__init__: _image=None, caches, flags\n"
                "CloneModeRadio.__init__ -> self.pipe = serial")
    s.msg("dlg", "drv", "status_fn = dialog._status; thread: sync_in()")
    s.msg("drv", "tr", "CloneSerialTransport(pipe, logger=LOG)")
    s.self_call("tr", "raise read/write timeouts to >= 3 s")
    s.self_call("drv", "Status(); transport.progress_cb = _progress")
    s.msg("drv", "tr", "read_clone()  (segments = DEFAULT_SEGMENTS)")
    s.msg("tr", "radio", "handshake()  (see diagram 3)")
    s.ret("radio", "tr", "model, XOR key")
    s.frame("loop", "277 blocks of 0x80 bytes, DEFAULT_SEGMENTS order", "drv", "radio")
    s.msg("tr", "radio", "cmd 0x52 / 0x54, addr_hi, addr_lo, 0x80")
    s.ret("radio", "tr", "4-byte header + 128 bytes")
    s.self_call("tr", "_apply_xor(payload); append")
    s.msg("tr", "drv", "progress_cb(done, 277, 'read')")
    s.msg("drv", "dlg", "status_fn(Status 'Reading channels 001-004...')")
    s.end()
    s.frame("alt", "all blocks read", "dlg", "radio")
    s.msg("tr", "radio", "E  (end session)")
    s.ret("tr", "drv", "raw image, 35,456 bytes")
    s.self_call("drv", "_mmap = MemoryMapBytes(raw)\n_metadata = {'rt950_layout': 4}")
    s.self_call("drv", "process_mmap()  (see diagram 8)")
    s.ret("drv", "dlg", "return")
    s.self_call("dlg", "dialog.complete()\nopen ChirpEditorSet (diagram 4)")
    s.els("CloneTransportError or any other exception (no 'E' sent)")
    s.ret("drv", "dlg", "RadioError('Clone read failed: ...')")
    s.self_call("dlg", "dialog.fail(...)")
    s.end()
    s.self_call("dlg", "finally: pipe.close()")
    return s


def clone_session() -> Seq:
    """Diagram 3: the clone session on the wire, handshake and block transfer.

    Described in ``docs/chirp-interface.md`` section 5.

    Returns:
        The diagram, ready to render.
    """
    s = Seq("3. Clone session on the wire (CloneSerialTransport)", [
        ("tr", "CloneSerialTransport"),
        ("radio", "RT-950 Pro"),
    ])
    s.divider("handshake()")
    s.self_call("tr", "reset_input_buffer(), reset_output_buffer()")
    s.msg("tr", "radio", "'PROGRAMBT9000U'")
    s.ret("radio", "tr", "0x06 (ACK)")
    s.msg("tr", "radio", "'F'")
    s.ret("radio", "tr", "16 bytes (logged only)")
    s.msg("tr", "radio", "'M'")
    s.ret("radio", "tr", "12 bytes ASCII model string (blank-padded)")
    s.self_call("tr",
                "_build_encryption_frame():\n"
                "'SEND' + code (0x10-0x14 | 0x20-0x24)\n"
                "+ 19 random indexes 0-19 + 0x00\n"
                "key = ENCRYPT_STRINGS[selected index]")
    s.msg("tr", "radio", "25-byte SEND frame")
    s.ret("radio", "tr", "0x06 (ACK) -> _xor_key set")
    s.divider("read_clone(): one block")
    s.msg("tr", "radio", "[0x52|0x54, addr_hi, addr_lo, 0x80]")
    s.ret("radio", "tr", "[header (4)] + [payload (128)]")
    s.self_call("tr", "_apply_xor(payload)  (decrypt)")
    s.divider("write_clone(): one block")
    s.self_call("tr", "_apply_xor(chunk)  (encrypt)")
    s.msg("tr", "radio", "[0x57|0x58, addr_hi, addr_lo, 0x80] + payload (128)")
    s.self_call("tr", "timeout: 8 s (< 0x8000), 10 s (>= 0x8000), 30 s (0x58)")
    s.frame("alt", "radio commits the block", "tr", "radio")
    s.ret("radio", "tr", "0x06 (ACK)")
    s.self_call("tr", "restore timeout; sleep 0.05 s (>= 0x8000)\nor 0.1 s + 0.5 s (0x58)")
    s.els("no byte before the timeout")
    s.self_call("tr",
                "CloneTransportError('No ACK for write cmd 0x57\n"
                "address 0xC000 (Serial read timed out)')")
    s.els("another byte than 0x06")
    s.self_call("tr", "CloneTransportError('Write ACK mismatch at ...')")
    s.end()
    s.divider("end of session")
    s.msg("tr", "radio", "'E'")
    return s


def open_editor() -> Seq:
    """Diagram 4: CHIRP opens the editor with one tab per zone and reads memories.

    Described in ``docs/chirp-interface.md`` section 7.

    Returns:
        The diagram, ready to render.
    """
    s = Seq("4. Opening the editor: zones as sub-devices", [
        ("es", "ChirpEditorSet"),
        ("me", "ChirpMemEdit\n(one per zone)"),
        ("zone", "RT950ProZoneRadio\n(zone z)"),
        ("drv", "RT950ProDriver\n(parent)"),
        ("img", "RadioImage"),
    ])
    s.msg("es", "drv", "get_features()")
    s.ret("drv", "es", "bounds 1-990, has_sub_devices, has_settings")
    s.msg("es", "drv", "get_sub_devices()")
    s.frame("loop", "z = 1 .. 10", "zone", "drv")
    s.msg("drv", "zone", "RT950ProZoneRadio(self, z)")
    s.self_call("zone", "_first = (z-1)*99; VARIANT = _zone_label()\nshares parent._memory_cache")
    s.end()
    s.ret("drv", "es", "10 sub-devices")
    s.msg("es", "drv", "link_device_metadata(zones)")
    s.self_call("drv", "zone._metadata = parent._metadata[VARIANT]")
    s.note("es", "es", "10 devices > 2: wx.Treebook\n(tab list on the right)")
    s.frame("loop", "each zone", "es", "img")
    s.msg("es", "me", "ChirpMemEdit(zone); tab 'Memories (1 VHF-LOCAL)'")
    s.msg("me", "zone", "get_features()")
    s.ret("zone", "me", "bounds 1-99, no sub-devices, no settings")
    s.frame("loop", "each row n = 1 .. 99 (lazy)", "me", "img")
    s.msg("me", "zone", "get_memory(n)")
    s.msg("zone", "drv", "get_memory((z-1)*99 + n)")
    s.frame("alt", "number not in _memory_cache", "zone", "img")
    s.msg("drv", "img", "channels[number - 1]")
    s.ret("img", "drv", "ChannelRecord")
    s.self_call("drv",
                "_channel_to_memory(): freq, duplex/offset,\n"
                "tones, mode, power, skip, extra")
    s.self_call("drv", "_memory_cache[number] = mem")
    s.end()
    s.ret("drv", "zone", "Memory")
    s.self_call("zone", "mem.dupe(); mem.number = n")
    s.ret("zone", "me", "Memory (number n)")
    s.msg("me", "zone", "get_memory_extra(mem)  (comment from metadata)")
    s.end()
    s.end()
    s.note("es", "drv",
           "has_settings: a ChirpSettingsEdit is created for the parent\n"
           "(get_settings() runs when that tab is first selected, diagram 6)")
    return s


def edit_memory() -> Seq:
    """Diagram 5: editing or deleting a memory in a zone tab.

    Described in ``docs/chirp-interface.md`` section 9.

    Returns:
        The diagram, ready to render.
    """
    s = Seq("5. Editing or deleting a memory in a zone tab", [
        ("user", "User"),
        ("me", "ChirpMemEdit"),
        ("zone", "RT950ProZoneRadio\n(zone z)"),
        ("drv", "RT950ProDriver"),
        ("ch", "ChannelRecord\n(slot k)"),
    ])
    s.msg("user", "me", "edit a cell of row n")
    s.msg("me", "zone", "set_memory(FrozenMemory(mem))")
    s.self_call("zone", "check 1 <= n <= 99\nglob = mem.dupe(); glob.number = (z-1)*99 + n")
    s.msg("zone", "drv", "set_memory(glob)")
    s.self_call("drv", "check 1 <= k <= 990; _require_image()")
    s.msg("drv", "ch", "_apply_memory_to_channel(glob, channel)")
    s.frame("alt", "glob.empty", "drv", "ch")
    s.self_call("ch", "rx_hz = tx_hz = None; name = ''")
    s.els("not empty")
    s.self_call("ch",
                "rx/tx from freq + duplex/offset; name\n"
                "_update_tones_from_memory()\n"
                "scrambler 0-8, encryption 0-2 from extra\n"
                "learn_fhss=False, fhss_code=None\n"
                "band rules (airband AM/RX-only, 18-64 MHz FM)\n"
                "mode/bandwidth, power, scan_add")
    s.end()
    s.note("ch", "ch", "state differs from _original_state:\nto_bytes() rebuilds the 32 bytes")
    s.self_call("drv", "_memory_cache[k] = _channel_to_memory(k, channel)")
    s.ret("drv", "zone", "")
    s.ret("zone", "me", "")
    s.msg("me", "zone", "set_memory_extra(mem)  (comment into metadata)")
    s.msg("me", "zone", "get_memory(n)  (refresh row)")
    s.ret("zone", "me", "sanitised copy from the cache")
    s.divider("Delete row n")
    s.msg("user", "me", "Delete")
    s.msg("me", "zone", "erase_memory(n)")
    s.self_call("zone", "chirp_common.Radio.erase_memory():\nMemory(number=n, empty=True)")
    s.msg("zone", "drv", "set_memory(...) as above, empty branch")
    s.msg("me", "zone", "erase_memory_extra(n)")
    return s


def settings() -> Seq:
    """Diagram 6: the Settings tab; how CHIRP reads and applies the settings.

    Described in ``docs/chirp-interface.md`` section 10.

    Returns:
        The diagram, ready to render.
    """
    s = Seq("6. Settings tab: get_settings / set_settings", [
        ("user", "User"),
        ("se", "ChirpSettingsEdit"),
        ("drv", "RT950ProDriver"),
        ("bld", "_build_*_group /\n_apply_* callbacks"),
        ("img", "RadioImage sections"),
    ])
    s.msg("user", "se", "select the Settings tab (first time)")
    s.msg("se", "drv", "get_settings()")
    s.self_call("drv", "_require_image()")
    s.msg("drv", "bld", "_build_vfo_group(image.vfo)")
    s.msg("drv", "bld",
          "_build_modulation_group, _build_function_group,\n"
          "_build_aprs_group, _build_dtmf_group (if present)")
    s.msg("drv", "bld", "_build_zone_group(image)")
    s.self_call("bld", "RadioSetting per field\nset_apply_callback(_apply_..., section object)")
    s.ret("bld", "drv", "RadioSettingGroup objects")
    s.ret("drv", "se", "RadioSettings(*groups)")
    s.msg("user", "se", "change a value")
    s.self_call("se",
                "_apply_settings(): new value into the setting\n"
                "copy.deepcopy(settings); drop immutable/uninitialised")
    s.msg("se", "drv", "set_settings(copy)")
    s.self_call("drv", "isinstance(settings, RadioSettings); walk()")
    s.frame("loop", "every RadioSetting with an apply callback", "drv", "img")
    s.msg("drv", "bld", "run_apply_callback()")
    s.msg("bld", "img",
          "e.g. set_function_value(), vfo.freq_band = ...,\n"
          "image.zone_names[i] = name[:10]")
    s.frame("alt", "SettingsError / KeyError / IndexError / ValueError", "drv", "img")
    s.ret("bld", "drv", "errors.RadioError(message)")
    s.ret("drv", "se", "exception -> error dialog")
    s.end()
    s.end()
    s.self_call("drv", "_memory_cache.clear()")
    s.ret("drv", "se", "return")
    s.note("drv", "img",
           "The callback is a closure over the original setting and section\n"
           "objects, so the deep copy still updates the driver's RadioImage.")
    return s


def save_image() -> Seq:
    """Diagram 7: saving a ``.img`` file.

    Described in ``docs/chirp-interface.md`` section 11.

    Returns:
        The diagram, ready to render.
    """
    s = Seq("7. Saving a .img file", [
        ("user", "User"),
        ("es", "ChirpEditorSet"),
        ("drv", "RT950ProDriver"),
        ("img", "RadioImage"),
        ("base", "CloneModeRadio\n(CHIRP base)"),
    ])
    s.msg("user", "es", "File > Save")
    s.msg("es", "drv", "save(filename)")
    s.self_call("drv", "save() -> save_mmap(filename)")
    s.self_call("drv", "_refresh_mmap()")
    s.msg("drv", "img", "_build_clone_payload(image) -> image.to_bytes()")
    s.self_call("img",
                "channels: to_bytes() (unchanged = raw bytes)\n"
                "keep 0x7BC0-0x7FFF (channel_extra)\n"
                "encode VFO, function, DTMF, modulation,\n"
                "APRS, zone names on top of remainder")
    s.ret("img", "drv", "payload, 35,456 bytes")
    s.self_call("drv", "_mmap = MemoryMapBytes(payload)\n_parse_memobj()  (Browser view)")
    s.msg("drv", "base", "super().save_mmap(filename)")
    s.self_call("base", "write mmap bytes\n+ MAGIC + base64(JSON metadata)")
    s.note("base", "base",
           "metadata: rclass, vendor, model,\n"
           "variant, chirp_version, rt950_layout,\n"
           "one entry per zone VARIANT")
    s.ret("base", "drv", "")
    s.ret("drv", "es", "")
    return s


def load_image() -> Seq:
    """Diagram 8: opening a ``.img`` file and ``process_mmap()``.

    Described in ``docs/chirp-interface.md`` section 6.

    Returns:
        The diagram, ready to render.
    """
    s = Seq("8. Opening a .img file and process_mmap()", [
        ("user", "User"),
        ("dir", "chirp.directory"),
        ("base", "CloneModeRadio\n(CHIRP base)"),
        ("drv", "RT950ProDriver"),
        ("img", "RadioImage"),
    ])
    s.msg("user", "dir", "File > Open  x.img")
    s.self_call("dir",
                "get_radio_by_image(): _strip_metadata()\n"
                "match vendor 'Radtel', model 'RT-950 Pro'")
    s.msg("dir", "drv", "DynamicRadioAlias(filename)  (subclass of RT950ProDriver)")
    s.self_call("drv", "__init__: state first, then super().__init__")
    s.msg("drv", "base", "CloneModeRadio.__init__(filename)")
    s.self_call("base", "load_mmap(): _metadata from file\n_mmap = MemoryMapBytes(data)")
    s.msg("base", "drv", "process_mmap()")
    s.frame("alt", "len == 35,456 and rt950_layout >= 4", "base", "img")
    s.self_call("drv", "_zone_names_valid = True")
    s.els("len == 35,456, no or older rt950_layout")
    s.self_call("drv", "zone-name segment := 0xFF; names not written")
    s.els("len == 35,200 (990 channels, no zone names)")
    s.self_call("drv", "append 0x100 bytes 0xFF")
    s.els("len == 33,152 (old 960-slot driver)")
    s.self_call("drv",
                "_legacy_960 = True; insert 0x800 x 0xFF at 0x7800\n"
                "+ 0x100 x 0xFF zone names")
    s.end()
    s.msg("drv", "img", "RadioImage.from_bytes(data)")
    s.self_call("img",
                "990 x ChannelRecord.from_bytes()\n"
                "parse VFO/function/DTMF/modulation/APRS\n"
                "parse_zone_names(); keep remainder, channel_extra")
    s.frame("alt", "parsed", "base", "img")
    s.ret("img", "drv", "RadioImage")
    s.self_call("drv", "_memory_cache.clear(); _parse_memobj()\n_log_channel_extra()")
    s.self_call("drv",
                "payload = _build_clone_payload(image)\n"
                "_aprs_original = APRS block\n"
                "_high_channels_original = payload[0x7800:0x7C00]\n"
                "(on any exception both stay None: nothing optional is written)")
    s.ret("drv", "dir", "radio object -> ChirpEditorSet (diagram 4)")
    s.els("ValueError (too short, invalid BCD, ...)")
    s.ret("drv", "dir", "errors.RadioError('Failed to parse memory map: ...')")
    s.end()
    return s


def upload() -> Seq:
    """Diagram 9: upload to the radio, ``sync_out()``.

    Described in ``docs/chirp-interface.md`` section 12.

    Returns:
        The diagram, ready to render.
    """
    s = Seq("9. Upload to radio (sync_out)", [
        ("user", "User"),
        ("dlg", "ChirpUploadDialog\n+ CloneThread"),
        ("drv", "RT950ProDriver"),
        ("plan", "_write_options /\n_build_write_plan"),
        ("tr", "CloneSerialTransport"),
        ("radio", "RT-950 Pro"),
    ])
    s.msg("user", "dlg", "Radio > Upload, port")
    s.msg("dlg", "drv", "set_pipe(serial); status_fn; thread: sync_out()")
    s.self_call("drv", "check pipe and _image")
    s.self_call("drv", "payload = _build_clone_payload(image)\n(ValueError here: nothing sent yet)")
    s.msg("drv", "tr", "CloneSerialTransport(pipe, logger=LOG)")
    s.msg("drv", "plan", "_write_options()")
    s.self_call("plan",
                "write_aprs = APRS bytes != _aprs_original\n"
                "channel_bytes = 0x7C00 if 0x7800-0x7BFF changed\n"
                "  and not _legacy_960, else 0x7800\n"
                "write_zone_names = _zone_names_valid")
    s.ret("plan", "drv", "options")
    s.msg("drv", "plan", "_build_write_plan(payload, **options)")
    s.self_call("plan",
                "_WRITE_PLAN order: channels, VFO, function,\n"
                "DTMF, mod. params, mod. names, zone names, APRS")
    s.ret("plan", "drv", "segments, data (258-269 blocks)")
    s.msg("drv", "tr", "write_clone(data, segments=...)")
    s.msg("tr", "radio", "handshake()  (diagram 3)")
    s.frame("loop", "each 0x80-byte block in plan order", "drv", "radio")
    s.msg("tr", "radio", "0x57 (or 0x58 for APRS) + XOR payload")
    s.ret("radio", "tr", "0x06 within 8 / 10 / 30 s")
    s.msg("tr", "drv", "progress_cb(done, total, 'write')")
    s.msg("drv", "dlg", "status_fn('Writing channels ...' / 'Writing Zone names...')")
    s.end()
    s.frame("alt", "all blocks acknowledged", "dlg", "radio")
    s.msg("tr", "radio", "'E'")
    s.self_call("drv", "_mmap = MemoryMapBytes(payload); _parse_memobj()")
    s.ret("drv", "dlg", "return -> dialog.complete()")
    s.els("CloneTransportError mentioning 'cmd 0x58' (no 'E' sent)")
    s.ret("drv", "dlg",
          "RadioError('All channels, settings and zone names\n"
          "were written, but ... APRS block (cmd 0x58) ...')")
    s.els("any other exception (no 'E' sent)")
    s.ret("drv", "dlg", "RadioError('Clone write failed: ...')")
    s.end()
    return s


DIAGRAMS: Dict[str, Callable[[], Seq]] = {
    "seq-01-driver-loading.svg": driver_loading,
    "seq-02-download.svg": download,
    "seq-03-clone-session.svg": clone_session,
    "seq-04-open-editor.svg": open_editor,
    "seq-05-edit-memory.svg": edit_memory,
    "seq-06-settings.svg": settings,
    "seq-07-save-image.svg": save_image,
    "seq-08-load-image.svg": load_image,
    "seq-09-upload.svg": upload,
}
"""Output file name to the function that builds that diagram."""


def main() -> int:
    """Write every diagram of ``DIAGRAMS`` as an SVG file.

    The output directory is the first command-line argument, or
    ``DEFAULT_OUT``; it is created if needed.

    Returns:
        Process exit code (0).
    """
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    for name, build in DIAGRAMS.items():
        (out / name).write_text(build().render(), encoding="utf-8")
        print("wrote", out / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
