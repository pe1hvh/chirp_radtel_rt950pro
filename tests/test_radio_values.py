"""Regression tests for values and screens confirmed on a real radio.

Each test pins down how the radio stores a value, as measured with the
original CPS (firmware V0.29, CPS V1.3.3) and raw dumps made with
``tools/raw_dump.py``. Only the encodings come from the radio; the
frequencies and other data in these images are invented.

    CHIRP_SRC=/path/to/chirp python3 -m pytest tests
"""

# The tests inspect the parsed image (radio._image), as test_driver.py does.
# pylint: disable=protected-access

import os
import subprocess
import sys

import pytest

from sample import blank_image, drv, load


VFO_OFFSET = 0x8000
"""Image offset of the VFO block (directly after the 0x8000-byte channel segment)."""

ZONE_OFFSET = 0x8980
"""Image offset of the zone-name block (radio address 0xC000)."""

VFO_LABELS = [
    "Rx Freq", "Rx QT/DQT", "Tx QT/DQT", "Busy Lockout", "Offset Dir",
    "Signalling", "Tx Power", "Scramble", "Bandwidth", "Encryption",
    "RxModulation", "Freq Band", "Step Freq", "Offset Freq",
]
"""Field labels of one VFO, in the order of the CPS *VFO Mode* screen."""

STEP_LABELS = [
    "2.5KHz", "5.0KHz", "6.25KHz", "8.33KHz", "10.0KHz",
    "12.5KHz", "20.0KHz", "25.0KHz", "50.0KHz", "100.0KHz",
]
"""Step Freq choices of the CPS; the radio stores the index (0-9)."""


def _vfo_entry(digits, offset, tones, flags):
    """Build one 32-byte VFO entry as the radio stores it.

    Args:
        digits: Eight frequency digits (10 Hz units).
        offset: Seven offset digits (100 Hz units).
        tones: ``(rx, tx)`` two-byte tone encodings.
        flags: Byte index to value for bytes 13 (bit 0 busy lockout), 14
            (bits 5-4 offset direction, low nibble signalling), 16 (high
            nibble scramble, low nibble power), 17 (bit 6 narrow, bits 5-4
            encryption, bit 0 AM), 18 (band) and 19 (step index).

    Returns:
        bytes: The 32-byte entry; unused bytes are 0xFF as on the radio.
    """
    entry = bytearray(b"\xFF" * 32)
    entry[0:8] = bytes(digits)
    entry[8:10] = bytes(tones[0])
    entry[10:12] = bytes(tones[1])
    for index, value in flags.items():
        entry[index] = value
    entry[20:27] = bytes(offset)
    return bytes(entry)


# Encodings as measured on the radio; frequencies invented.
VFO_A = _vfo_entry([4, 3, 3, 5, 0, 0, 0, 0], [0, 0, 7, 6, 0, 0, 0], ([0, 0], [0x75, 0x03]),
                   {13: 0x00, 14: 0x1E, 16: 0x82, 17: 0x70, 18: 0x01, 19: 0x09})
"""UHF, Tx 88.5, Plus, Signalling 15, Low, Scramble 8, Narrow, Encryption 3, 100.0KHz."""
VFO_B = _vfo_entry([1, 4, 5, 5, 0, 0, 0, 0], [0, 0, 0, 6, 0, 0, 0], ([1, 0], [1, 0]),
                   {13: 0x01, 14: 0x20, 16: 0x00, 17: 0x01, 18: 0x00, 19: 0x07})
"""VHF, D023N/D023N, busy lockout, Minus, Signalling 1, High, AM, 25.0KHz."""
VFO_C = _vfo_entry([0, 2, 9, 6, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0], ([0xD2, 0], [0xED, 0x09]),
                   {13: 0x00, 14: 0x07, 16: 0x11, 17: 0x50, 18: 0x00, 19: 0x05})
"""VHF, D754I/254.1, Signalling 8, Middle, Scramble 1, Narrow, Encryption 1, 12.5KHz."""


def _image(vfos=(VFO_A, VFO_B, VFO_C), zone0=None):
    """Return a blank image with the given VFO entries and zone-1 slot.

    Args:
        vfos: Three 32-byte VFO entries.
        zone0: 16-byte zone-1 slot, or ``None`` to keep it empty.

    Returns:
        bytes: The image.
    """
    data = bytearray(blank_image())
    data[VFO_OFFSET:VFO_OFFSET + 96] = b"".join(vfos)
    if zone0 is not None:
        data[ZONE_OFFSET:ZONE_OFFSET + 16] = zone0
    return bytes(data)


def _settings(radio):
    """Return the settings tree and a name-to-setting map.

    Args:
        radio: A loaded driver.

    Returns:
        tuple: ``(tree, {name: RadioSetting})``.
    """
    tree = radio.get_settings()
    return tree, {e.get_name(): e for e in tree.walk() if hasattr(e, "value")}


def _apply_unchanged(radio):
    """Run every settings callback once without changing a value.

    ``set_settings`` skips unchanged settings, so the callbacks are run
    directly: this checks that each callback round-trips its own value.

    Args:
        radio: A loaded driver.

    Returns:
        bytes: The image after the apply.
    """
    tree, _ = _settings(radio)
    for element in tree.walk():
        if hasattr(element, "has_apply_callback") and element.has_apply_callback():
            element.run_apply_callback()
    return bytes(radio.get_mmap().get_packed())


# --- VFO decoding -----------------------------------------------------------

def test_vfo_power_decodes_all_three_levels():
    """Power nibble 2/0/1 decodes as Low/High/Middle (was always High)."""
    vfos = drv.parse_vfo_section(VFO_A + VFO_B + VFO_C)
    assert [v.tx_power for v in vfos] == [
        drv.PowerLevel.LOW, drv.PowerLevel.HIGH, drv.PowerLevel.MEDIUM]


def test_settings_apply_without_edit_keeps_vfo_bytes():
    """Running every settings callback without an edit leaves the VFO bytes as they were."""
    raw = _image()
    after = _apply_unchanged(load(raw))
    assert after[VFO_OFFSET:VFO_OFFSET + 96] == raw[VFO_OFFSET:VFO_OFFSET + 96]


# --- VFO screen ---------------------------------------------------------------

def _vfo_items(radio, index):
    """Return the settings of one VFO in screen order.

    Args:
        radio: A loaded driver.
        index: 0 for VFO-A, 1 for VFO-B, 2 for VFO-C.

    Returns:
        list: The ``RadioSetting`` objects of that VFO's group.
    """
    tree = radio.get_settings()
    vfo_group = [g for g in tree if g.get_name() == "vfo"][0]
    sub = [g for g in vfo_group if g.get_name() == f"vfo.{index}"][0]
    return list(sub)


def test_vfo_screen_follows_cps_labels_and_order():
    """VFO groups are named VFO-A..C and show the CPS fields in CPS order."""
    radio = load(_image())
    tree = radio.get_settings()
    vfo_group = [g for g in tree if g.get_name() == "vfo"][0]
    assert [g.get_shortname() for g in vfo_group] == ["VFO-A", "VFO-B", "VFO-C"]
    assert [s.get_shortname() for s in _vfo_items(radio, 0)] == VFO_LABELS


def test_vfo_screen_shows_measured_values():
    """Each VFO field shows the value the CPS showed for the same bytes."""
    radio = load(_image())
    shown = [{s.get_shortname(): str(s.value) for s in _vfo_items(radio, i)} for i in range(3)]
    assert [v["Tx Power"] for v in shown] == ["Low", "High", "Middle"]
    assert [v["Step Freq"] for v in shown] == ["100.0KHz", "25.0KHz", "12.5KHz"]
    assert [v["Freq Band"] for v in shown] == ["UHF", "VHF", "VHF"]
    assert [v["Signalling"] for v in shown] == ["15", "1", "8"]
    assert [v["Scramble"] for v in shown] == ["Scramble 8", "OFF", "Scramble 1"]
    assert [v["Encryption"] for v in shown] == ["Encryption 3", "OFF", "Encryption 1"]
    assert [v["Offset Dir"] for v in shown] == ["Plus", "Minus", "None"]
    assert [v["Busy Lockout"] for v in shown] == ["OFF", "ON", "OFF"]
    assert [v["Bandwidth"] for v in shown] == ["Narrow", "Wide", "Narrow"]
    assert [v["RxModulation"] for v in shown] == ["FM", "AM", "FM"]
    assert [v["Rx QT/DQT"] for v in shown] == ["OFF", "D023N", "D754I"]
    assert [v["Tx QT/DQT"] for v in shown] == ["88.5", "D023N", "254.1"]


def test_vfo_choice_lists_match_cps():
    """The choice lists are the lists of the CPS."""
    radio = load(_image())
    items = {s.get_shortname(): s for s in _vfo_items(radio, 0)}
    assert items["Step Freq"].value.get_options() == STEP_LABELS
    assert items["Tx Power"].value.get_options() == ["High", "Middle", "Low"]
    assert items["Scramble"].value.get_options() == ["OFF"] + [f"Scramble {i}" for i in range(1, 9)]
    assert items["Signalling"].value.get_options() == [str(i) for i in range(1, 16)]
    assert items["Offset Dir"].value.get_options() == ["None", "Plus", "Minus"]
    assert items["Encryption"].value.get_options() == ["OFF"] + [
        f"Encryption {i}" for i in range(1, 4)]
    assert items["Bandwidth"].value.get_options() == ["Wide", "Narrow"]
    assert items["RxModulation"].value.get_options() == ["FM", "AM"]
    assert items["Busy Lockout"].value.get_options() == ["OFF", "ON"]
    tones = items["Rx QT/DQT"].value.get_options()
    assert len(tones) == 1 + 50 + 210
    assert tones[:3] == ["OFF", "67.0", "69.3"]
    assert "254.1" in tones and "D023N" in tones and tones[-1] == "D754I"


def test_vfo_freq_band_is_read_only():
    """Freq Band is read-only and has no apply callback."""
    radio = load(_image())
    band = {s.get_shortname(): s for s in _vfo_items(radio, 0)}["Freq Band"]
    assert not band.value.get_mutable()
    assert not band.has_apply_callback()


def test_vfo_edit_writes_cps_encoding():
    """Edited VFO fields are stored with the encoding the CPS uses."""
    radio = load(_image())
    tree, by_name = _settings(radio)
    by_name["vfo.1.step"].value = "100.0KHz"
    by_name["vfo.1.power"].value = "Low"
    by_name["vfo.1.signalling_group"].value = "15"
    by_name["vfo.1.tx_tone"].value = "D754I"
    radio.set_settings(tree)
    entry = bytes(radio.get_mmap().get_packed())[VFO_OFFSET + 32:VFO_OFFSET + 64]
    expected = bytearray(VFO_B)
    expected[19] = 9
    expected[16] = (VFO_B[16] & 0xF0) | 2
    expected[14] = (VFO_B[14] & 0xF0) | 14
    expected[10:12] = bytes([0xD2, 0x00])
    assert entry == bytes(expected)


def test_vfo_value_outside_list_is_left_alone():
    """A stored value the CPS does not offer is shown as unknown and kept."""
    # Offset direction 3, step index 12, power nibble 0xF, CTCSS 101.3 and DCS
    # index 240 are not offered by the CPS.
    odd = bytearray(VFO_B)
    odd[14] = 0x30
    odd[19] = 0x0C
    odd[16] = 0x0F
    odd[8:10] = bytes([0xF5, 0x03])
    odd[10:12] = bytes([0xF0, 0x00])
    raw = _image(vfos=(VFO_A, bytes(odd), VFO_C))
    radio = load(raw)
    items = {s.get_shortname(): s for s in _vfo_items(radio, 1)}
    assert str(items["Offset Dir"].value) == "Unknown (3)"
    assert str(items["Step Freq"].value) == "Unknown (12)"
    assert str(items["Rx QT/DQT"].value) == "Unknown (101.3)"
    after = _apply_unchanged(radio)
    assert after[VFO_OFFSET:VFO_OFFSET + 96] == raw[VFO_OFFSET:VFO_OFFSET + 96]


# --- channels -----------------------------------------------------------------

def test_channel_encryption_3_is_kept():
    """Channel encryption 3 and scramble 8 from the extras are stored."""
    radio = load(blank_image())
    zone = radio.get_sub_devices()[0]
    mem = zone.get_memory(1).dupe()
    mem.empty = False
    mem.freq = 145_500_000
    mem.name = "ENC3"
    mem.extra = {"scrambler": 8, "encryption": 3}
    zone.set_memory(mem)
    channel = radio._image.channels[0]
    assert (channel.scrambler, channel.encryption) == (8, 3)


# --- function block and APRS ranges ---------------------------------------------

@pytest.mark.parametrize("key, highest", [
    ("key_side1_short", 7), ("key_side1_long", 7),
    ("key_side2_short", 6), ("key_side2_long", 6),
])
def test_side_key_ranges_match_cps(key, highest):
    """PF1 accepts 0-7 and PF2 0-6, as the CPS lists."""
    settings = load(blank_image())._image.function
    drv.set_function_value(settings, key, highest)
    with pytest.raises(drv.SettingsError):
        drv.set_function_value(settings, key, highest + 1)


@pytest.mark.parametrize("key, highest", [
    ("timed_beacon_time", 9), ("radio_symbol", 4),
])
def test_aprs_ranges_match_cps(key, highest):
    """Timed Beacon Time accepts 0-9 and Radio Symbol 0-4, as the CPS lists."""
    settings = load(blank_image())._image.aprs
    drv.set_aprs_value(settings, key, highest)
    with pytest.raises(drv.SettingsError):
        drv.set_aprs_value(settings, key, highest + 1)


# --- zone names -------------------------------------------------------------------

def test_zone_name_of_twelve_characters_loads_and_saves():
    """A 12-character zone name loads in the settings and is written in full."""
    raw = _image(zone0=b"ABCDEFGHIJKL" + b"\xFF" * 4)
    radio = load(raw)
    tree, by_name = _settings(radio)
    assert str(by_name["zone_name_1"].value) == "ABCDEFGHIJKL"
    by_name["zone_name_2"].value = "MNOPQRSTUVWX"
    radio.set_settings(tree)
    after = bytes(radio.get_mmap().get_packed())
    assert after[ZONE_OFFSET:ZONE_OFFSET + 16] == raw[ZONE_OFFSET:ZONE_OFFSET + 16]
    assert after[ZONE_OFFSET + 16:ZONE_OFFSET + 28] == b"MNOPQRSTUVWX"


def test_zone_name_longer_than_twelve_is_shown_and_kept():
    """A 14-character name written another way loads and survives an apply."""
    raw = _image(zone0=b"ABCDEFGHIJKLMN" + b"\xFF" * 2)
    radio = load(raw)
    _, by_name = _settings(radio)
    assert str(by_name["zone_name_1"].value) == "ABCDEFGHIJKLMN"
    after = _apply_unchanged(radio)
    assert after[ZONE_OFFSET:ZONE_OFFSET + 16] == raw[ZONE_OFFSET:ZONE_OFFSET + 16]


def test_vfo_group_builds_with_the_stand_in_classes():
    """Without CHIRP installed the driver's stand-in classes build the VFO group."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import radtel_rt950pro as d; "
            "d._build_vfo_group(d.parse_vfo_section(bytes(96)))")
    result = subprocess.run([sys.executable, "-I", "-c", code, root],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


# --- band and modulation screen (measured in test round 2b) ------------------------

@pytest.mark.parametrize("freq, band", [
    ("145.50000", "VHF"), ("299.99999", "VHF"), ("300.00000", "UHF"), ("433.50000", "UHF"),
])
def test_vfo_band_follows_rx_freq(freq, band):
    """Changing Rx Freq sets Freq Band as the CPS does: UHF from 300 MHz."""
    radio = load(_image())
    tree, by_name = _settings(radio)
    by_name["vfo.2.freq"].value = freq
    radio.set_settings(tree)
    _, after = _settings(radio)
    assert str(after["vfo.2.freq_band"].value) == band


MOD_OFFSET = 0x8400
"""Image offset of the modulation parameter block (radio address 0xB000)."""


def test_modulation_screen_uses_cps_lists():
    """Work Mode, Modulation Mode, steps and Rx Gain are CPS lists."""
    image = bytearray(_image())
    for index, value in ((33, 0), (67, 1), (151, 0), (150, 5), (68, 0), (152, 36)):
        image[MOD_OFFSET + index] = value
    radio = load(bytes(image))
    _, by_name = _settings(radio)
    shown = {key: str(by_name[f"modulation.{key}"].value)
             for key in ("work_mode", "modulation_mode", "am_step", "ssb_step",
                         "am_rx_gain", "ssb_rx_gain")}
    assert shown == {"work_mode": "VFO Mode", "modulation_mode": "AM", "am_step": "1K",
                     "ssb_step": "1000K", "am_rx_gain": "AGC", "ssb_rx_gain": "-35dB"}
    assert by_name["modulation.modulation_mode"].value.get_options() == [
        "FM", "AM", "LSB", "USB", "CW"]
    gains = by_name["modulation.am_rx_gain"].value.get_options()
    assert gains[:3] == ["AGC", "0dB", "-1dB"] and len(gains) == 37


def test_modulation_edit_and_unset_value():
    """An edited list value is stored; an unset (0xFF) field shows 'Not set' and stays."""
    image = bytearray(_image())
    image[MOD_OFFSET + 67] = 1
    image[MOD_OFFSET + 150] = 0xFF
    raw = bytes(image)
    radio = load(raw)
    tree, by_name = _settings(radio)
    assert str(by_name["modulation.ssb_step"].value) == "Not set"
    by_name["modulation.modulation_mode"].value = "USB"
    radio.set_settings(tree)
    after = bytes(radio.get_mmap().get_packed())
    assert after[MOD_OFFSET + 67] == 3
    assert after[MOD_OFFSET + 150] == 0xFF


def test_modulation_current_channel_range_matches_decoding():
    """The current-channel fields offer 0-14, the values the decoder can return."""
    radio = load(_image())
    _, by_name = _settings(radio)
    value = by_name["modulation.fm_current_channel"].value
    assert (value.get_min(), value.get_max()) == (0, 14)
