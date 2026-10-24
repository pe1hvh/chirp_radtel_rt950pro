"""Tests for the setting *Channel Divide* (Zone CH Mode / All CH Mode).

The encoding was measured on a real radio (firmware V0.29, CPS V1.3.3):
two raw dumps made with ``tools/raw_dump.py``, one after the CPS wrote
*Zone CH Mode* and one after it wrote *All CH Mode*, differ in exactly one
byte: radio address 0x9026 (image offset 0x8126) is 0 for Zone CH Mode and
1 for All CH Mode. The channel data is the same in both modes; only the
view changes. The channels in these tests are the neutral sample set.

    CHIRP_SRC=/path/to/chirp python3 -m pytest tests
"""

# The tests inspect the parsed image (radio._image), as test_driver.py does.
# pylint: disable=protected-access

import pytest

from sample import CHANNELS, blank_image, drv, load, sample_radio


DIVIDE_OFFSET = 0x8126
"""Image offset of the Channel Divide byte (radio address 0x9026: function
block at image offset 0x8100, second part at +32, byte 6)."""


def _with_divide(raw, value):
    """Return ``raw`` with the Channel Divide byte set to ``value``.

    Args:
        raw: A complete clone image.
        value: Byte value for radio address 0x9026.

    Returns:
        bytes: The changed image.
    """
    data = bytearray(raw)
    data[DIVIDE_OFFSET] = value
    return bytes(data)


def _sample_raw():
    """Return the clone image of the neutral sample set (Zone CH Mode, 0).

    Returns:
        bytes: The image as the driver would write it.
    """
    return bytes(sample_radio().get_mmap().get_packed())


def _setting(radio):
    """Return the settings tree and the Channel Divide setting.

    Args:
        radio: A loaded driver.

    Returns:
        tuple: ``(tree, RadioSetting)``.
    """
    tree = radio.get_settings()
    by_name = {e.get_name(): e for e in tree.walk() if hasattr(e, "value")}
    return tree, by_name["function.divide_channel"]


def test_measured_values():
    """Zone CH Mode is stored as 0 and All CH Mode as 1."""
    assert drv.CHANNEL_DIVIDE_ZONE == 0
    assert drv.CHANNEL_DIVIDE_ALL == 1
    assert DIVIDE_OFFSET - 0x8100 == 0x26


def test_setting_follows_cps_label_and_list():
    """The setting has the CPS label, the CPS choices in CPS order, and is volatile."""
    _, setting = _setting(load(blank_image()))
    assert setting.get_shortname() == "Channel Divide"
    assert list(setting.value.get_options()) == ["Zone CH Mode", "All CH Mode"]
    assert setting.volatile


@pytest.mark.parametrize("value, label", [(0, "Zone CH Mode"), (1, "All CH Mode")])
def test_stored_value_is_shown(value, label):
    """The stored byte is shown as the matching CPS choice."""
    _, setting = _setting(load(_with_divide(blank_image(), value)))
    assert str(setting.value) == label


def test_zone_mode_shows_ten_zone_tabs():
    """Zone CH Mode: ten sub-devices of 99 memories, as before."""
    radio = load(_with_divide(_sample_raw(), 0))
    rf = radio.get_features()
    assert rf.has_sub_devices
    assert rf.has_dynamic_subdevices
    zones = radio.get_sub_devices()
    assert len(zones) == 10
    assert zones[0].get_features().memory_bounds == (1, 99)
    assert not zones[0].get_features().has_dynamic_subdevices


def test_all_mode_shows_one_list_of_990():
    """All CH Mode: no sub-devices; the radio itself is one list 1-990."""
    radio = load(_with_divide(_sample_raw(), 1))
    rf = radio.get_features()
    assert not rf.has_sub_devices
    assert rf.has_dynamic_subdevices
    assert rf.memory_bounds == (1, 990)
    assert radio.get_sub_devices() == []


def test_all_mode_numbering_keeps_empty_channels():
    """All CH Mode: channel n is slot n; zones follow each other, gaps stay empty."""
    radio = load(_with_divide(_sample_raw(), 1))
    for zone, number, name, *_ in CHANNELS:
        mem = radio.get_memory((zone - 1) * 99 + number)
        assert mem.name == name
        assert not mem.empty
    # Zone 1 holds channels 1-4 and 99: 5-98 stay empty (not moved up).
    assert radio.get_memory(5).empty
    assert radio.get_memory(98).empty
    # Zone 2 channel 1 is channel 100 in the single list.
    assert radio.get_memory(100).name == "U-SIMPLEX"


def test_unset_value_shows_zones_and_is_kept():
    """0xFF (not set) shows the zone view and is not rewritten without an edit."""
    radio = load(_with_divide(_sample_raw(), 0xFF))
    assert radio.get_features().has_sub_devices
    assert len(radio.get_sub_devices()) == 10
    tree, _ = _setting(radio)
    radio.set_settings(tree)
    assert bytes(radio.get_mmap().get_packed())[DIVIDE_OFFSET] == 0xFF


@pytest.mark.parametrize("start, label, value, zones", [
    (0, "All CH Mode", 1, 0),
    (1, "Zone CH Mode", 0, 10),
])
def test_changing_the_setting_switches_view_and_one_byte(start, label, value, zones):
    """Changing Channel Divide writes only byte 0x9026 and switches the view at once."""
    before = _with_divide(_sample_raw(), start)
    radio = load(before)
    tree, setting = _setting(radio)
    setting.value = label
    radio.set_settings(tree)
    after = bytes(radio.get_mmap().get_packed())
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert changed == [DIVIDE_OFFSET]
    assert after[DIVIDE_OFFSET] == value
    # No reload needed: the features and sub-devices follow the image.
    assert radio.get_features().has_sub_devices == (zones == 10)
    assert len(radio.get_sub_devices()) == zones
    # The channels are the same in both views.
    for zone, number, name, *_ in CHANNELS:
        assert radio.get_memory((zone - 1) * 99 + number).name == name


def test_all_mode_edit_writes_the_same_slot():
    """A memory set in the single list lands in the same slot as via its zone."""
    radio = load(_with_divide(_sample_raw(), 1))
    mem = radio.get_memory(100).dupe()
    mem.name = "EDITED"
    radio.set_memory(mem)
    zone_view = load(_with_divide(bytes(radio.get_mmap().get_packed()), 0))
    assert zone_view.get_sub_devices()[1].get_memory(1).name == "EDITED"
