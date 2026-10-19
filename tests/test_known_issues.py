"""Regression tests for the known issues fixed in 0.1.5 without a radio.

Each test reproduces one known issue from docs/status.md with neutral,
invented data and fails on the driver before the fix.

    CHIRP_SRC=/path/to/chirp python3 -m pytest tests
"""

# The tests inspect the parsed image (radio._image), as test_driver.py does.
# pylint: disable=protected-access

import pytest

from sample import blank_image, drv, load
from chirp import chirp_common


FUNC_OFFSET = 0x8100
"""Image offset of the function block (radio address 0x9000)."""

APRS_OFFSET = 0x8900
"""Image offset of the APRS block (radio address 0x0000, command 0x54)."""


def _radio_with_channel(rx_tone, tx_tone, raw_patch=None):
    """Return a radio whose channel 1 is a simplex channel with given tones.

    Args:
        rx_tone: :class:`ToneSetting` for receive.
        tx_tone: :class:`ToneSetting` for transmit.
        raw_patch: Optional ``{byte index: value}`` applied to the channel's
            32 bytes before loading.

    Returns:
        The loaded driver.
    """
    record = drv.ChannelRecord.from_bytes(bytes(32))
    record.rx_hz = record.tx_hz = 145_500_000
    record.rx_tone = rx_tone
    record.tx_tone = tx_tone
    record.name = "TEST"
    record.scan_add = True
    record.tx_enabled = True
    data = bytearray(record.to_bytes())
    for index, value in (raw_patch or {}).items():
        data[index] = value
    image = bytearray(blank_image())
    image[0:32] = data
    return load(bytes(image))


def _tones(radio):
    """Return the rx and tx tone of channel 1 as the CPS writes them.

    Args:
        radio: A loaded driver.

    Returns:
        tuple: ``(rx, tx)`` display strings, e.g. ``("67.0", "D023N")``.
    """
    channel = radio._image.channels[0]
    return channel.rx_tone.to_display(), channel.tx_tone.to_display()


# --- tones: inverted DCS, Cross, frozen memory ----------------------------------

def test_inverted_dcs_reads_as_chirp_reverse_polarity():
    """Radio polarity I is shown to CHIRP as R."""
    radio = _radio_with_channel(drv.ToneSetting.dcs(23, "I"), drv.ToneSetting.dcs(23, "I"))
    mem = radio.get_memory(1)
    assert (mem.tmode, mem.dtcs, mem.dtcs_polarity) == ("DTCS", 23, "RR")


def test_chirp_reverse_polarity_is_written_as_inverted():
    """CHIRP polarity R is stored as the radio's I, without an error."""
    radio = _radio_with_channel(drv.ToneSetting.off(), drv.ToneSetting.off())
    mem = radio.get_memory(1)
    mem.tmode = "DTCS"
    mem.dtcs = 23
    mem.dtcs_polarity = "RN"
    radio.set_memory(mem)
    assert _tones(radio) == ("D023N", "D023I")
    assert radio._image.channels[0].to_bytes()[10:12] == bytes([106, 0])


CROSS_CASES = [
    (drv.ToneSetting.ctcss(67.0), drv.ToneSetting.off(), "->Tone"),
    (drv.ToneSetting.dcs(23, "N"), drv.ToneSetting.off(), "->DTCS"),
    (drv.ToneSetting.ctcss(67.0), drv.ToneSetting.dcs(23, "N"), "DTCS->Tone"),
    (drv.ToneSetting.dcs(23, "N"), drv.ToneSetting.ctcss(67.0), "Tone->DTCS"),
    (drv.ToneSetting.ctcss(71.9), drv.ToneSetting.ctcss(67.0), "Tone->Tone"),
    (drv.ToneSetting.off(), drv.ToneSetting.dcs(23, "N"), "DTCS->"),
    (drv.ToneSetting.dcs(25, "N"), drv.ToneSetting.dcs(23, "N"), "DTCS->DTCS"),
]
"""``(rx tone, tx tone, CHIRP cross mode)`` combinations the radio can store."""


@pytest.mark.parametrize("rx_tone, tx_tone, cross_mode", CROSS_CASES)
def test_mixed_tones_are_shown_as_cross_and_written_back(rx_tone, tx_tone, cross_mode):
    """Every rx/tx tone combination survives CHIRP via a Cross mode."""
    radio = _radio_with_channel(rx_tone, tx_tone)
    expected = _tones(radio)
    mem = radio.get_memory(1)
    assert (mem.tmode, mem.cross_mode) == ("Cross", cross_mode)
    mem.name = "EDITED"
    radio.set_memory(mem)
    assert _tones(radio) == expected


def test_features_offer_cross_modes():
    """The driver announces Cross and all its cross modes to CHIRP."""
    features = load(blank_image()).get_features()
    assert "Cross" in features.valid_tmodes
    assert set(features.valid_cross_modes) == set(chirp_common.CROSS_MODES)


def test_set_memory_does_not_change_the_callers_memory():
    """A DTCS memory with code 0 is stored without touching the caller's object."""
    radio = _radio_with_channel(drv.ToneSetting.off(), drv.ToneSetting.off())
    mem = radio.get_memory(1)
    mem.tmode = "DTCS"
    mem.dtcs = 0
    radio.set_memory(mem)
    assert mem.tmode == "DTCS"
    assert _tones(radio) == ("OFF", "OFF")


# --- channel record ------------------------------------------------------------

def test_edited_channel_keeps_high_nibbles_of_bytes_12_and_13():
    """Bits the driver does not know in bytes 12-13 survive an edit."""
    radio = _radio_with_channel(drv.ToneSetting.off(), drv.ToneSetting.off(),
                                raw_patch={12: 0xF3, 13: 0xA1})
    mem = radio.get_memory(1)
    mem.name = "EDITED"
    radio.set_memory(mem)
    data = radio._image.channels[0].to_bytes()
    assert (data[12], data[13]) == (0xF3, 0xA1)


# --- settings apply ------------------------------------------------------------

def test_settings_apply_writes_only_the_changed_setting():
    """Changing one setting leaves unset (0xFF) bytes elsewhere alone."""
    image = bytearray(blank_image())
    image[FUNC_OFFSET:FUNC_OFFSET + 0x100] = b"\xFF" * 0x100
    image[APRS_OFFSET:APRS_OFFSET + 0x80] = b"\xFF" * 0x80
    raw = bytes(image)
    radio = load(raw)
    tree = radio.get_settings()
    beep = [e for e in tree.walk() if e.get_name() == "function.beep_prompt"][0]
    beep.value = not bool(beep.value)
    radio.set_settings(tree)
    after = bytes(radio.get_mmap().get_packed())
    changed = [i for i in range(len(raw)) if raw[i] != after[i]]
    assert len(changed) == 1 and FUNC_OFFSET <= changed[0] < FUNC_OFFSET + 0x60
    assert radio._write_options()["write_aprs"] is False


# --- modulation and APRS blocks ----------------------------------------------------

def test_unset_modulation_block_is_written_back_unchanged():
    """An all-0xFF modulation block survives parse and encode byte-identical."""
    params = b"\xFF" * 256
    names = b"\xFF" * 768
    settings = drv.parse_modulation_sections(params, names)
    assert drv.encode_modulation_sections(settings, params, names) == (params, names)


def test_modulation_bandwidth_zero_is_kept():
    """SSB bandwidth 0 (0.5K in the CPS) is not turned into anything else."""
    params = bytearray(b"\xFF" * 256)
    params[69:74] = bytes([0x01, 0x01, 0x00, 0x82, 0x00])
    names = b"\xFF" * 768
    settings = drv.parse_modulation_sections(bytes(params), names)
    assert drv.encode_modulation_sections(settings, bytes(params), names)[0] == bytes(params)


def test_unusual_aprs_bytes_are_written_back_unchanged():
    """Stored APRS values outside the normal ranges survive without an edit."""
    raw = bytearray(blank_image()[APRS_OFFSET:APRS_OFFSET + 0x80])
    raw[7] = 0x58      # neither N nor S
    raw[8] = 75        # minutes above 59
    raw[11] = 0x58     # neither W nor E
    raw[13] = 200      # degrees above 180
    raw[27] = 0x85     # bit 7 set
    settings = drv.parse_aprs_section(bytes(raw))
    assert drv.encode_aprs_section(settings, bytes(raw)) == bytes(raw)


def test_gb2312_text_is_not_cut_inside_a_character():
    """A two-byte character that does not fit is left out, not halved."""
    assert drv._encode_gb2312("a中文", 4) == b"a\xd6\xd0\xff"


def test_negative_dtmf_code_group_index_is_refused():
    """get_dtmf_code_group refuses a negative index, like set_dtmf_code_group."""
    settings = load(blank_image())._image.dtmf
    with pytest.raises(IndexError):
        drv.get_dtmf_code_group(settings, -1)


# --- write plan -------------------------------------------------------------------

def test_function_segment_write_stops_before_0x9080():
    """Only the first 0x80-byte block of the function segment (0x9000) is written."""
    radio = load(blank_image())
    payload = drv._build_clone_payload(radio._image)
    segments, _ = drv._build_write_plan(payload, **radio._write_options())
    function = [s for s in segments if s.start == 0x9000]
    assert [(s.write_command, s.length) for s in function] == [(0x57, 0x80)]
