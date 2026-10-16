"""Tests for the RT-950 Pro driver, run against the CHIRP source tree.

    CHIRP_SRC=/path/to/chirp python3 -m pytest tests

CHIRP_SRC is the directory that contains the ``chirp`` package (a checkout of
https://github.com/kk7ds/chirp). Not needed when CHIRP is importable already.
"""

import time

import pytest

from sample import CHANNELS, ZONE_NAMES, blank_image, drv, load, sample_radio
from chirp import chirp_common


@pytest.fixture
def radio():
    return sample_radio()


def _plan(radio):
    payload = drv._build_clone_payload(radio._image)
    segments, data = drv._build_write_plan(payload, **radio._write_options())
    return [(s.write_command, s.start, s.length) for s in segments], data


# --- layout -----------------------------------------------------------------

def test_layout_constants():
    assert drv.CHANNEL_COUNT == 990
    assert drv.CHANNEL_DATA_BYTES == 0x7BC0
    assert drv.ZONE_NAME_ADDRESS == 0xC000
    aprs = [s for s in drv.DEFAULT_SEGMENTS if s.read_command == 0x54][0]
    assert aprs.write_command == 0x58


def test_zone_mapping(radio):
    zones = radio.get_sub_devices()
    assert len(zones) == 10
    for zone, number, name, mhz, *_ in CHANNELS:
        mem = zones[zone - 1].get_memory(number)
        assert mem.number == number
        assert mem.name == name
        assert mem.freq == int(round(mhz * 1e6))
        # same channel through the flat parent numbering
        assert radio.get_memory((zone - 1) * 99 + number).name == name
    assert zones[0].get_features().memory_bounds == (1, 99)


def test_zone_names_and_labels(radio):
    zones = radio.get_sub_devices()
    assert zones[0].VARIANT == "1 VHF-LOCAL"
    assert zones[1].VARIANT == "2 UHF-LOCAL"
    assert zones[2].VARIANT == "Zone 3"
    assert radio._image.zone_names[:2] == ZONE_NAMES


def test_untouched_roundtrip_is_byte_identical(radio):
    raw = bytes(radio.get_mmap().get_packed())
    assert drv._build_clone_payload(load(raw)._image) == raw


def test_aprs_message_nul_padding():
    radio = load(blank_image())
    values = [str(e.value) for e in radio.get_settings().walk()
              if e.get_name().endswith("custom_messages")]
    assert values == ["Hello world!"]


# --- editing ----------------------------------------------------------------

def test_set_memory_does_not_modify_frozen_input(radio):
    zone2 = radio.get_sub_devices()[1]
    mem = zone2.get_memory(10).dupe()
    mem.empty = False
    mem.freq = 432_100_000
    mem.name = "NEW"
    frozen = chirp_common.FrozenMemory(mem)
    zone2.set_memory(frozen)          # must not warn/raise on frozen object
    assert zone2.get_memory(10).name == "NEW"
    assert radio.get_memory(99 + 10).name == "NEW"


def test_zone_name_via_settings(radio, tmp_path):
    settings = radio.get_settings()
    for element in settings.walk():
        if element.get_name() == "zone_name_2":
            element.value = "PORTABLE"
    radio.set_settings(settings)
    path = tmp_path / "t.img"
    radio.save_mmap(str(path))
    reloaded = drv.RT950ProDriver(str(path))
    assert reloaded.get_sub_devices()[1].VARIANT == "2 PORTABLE"
    assert reloaded.get_sub_devices()[0].VARIANT == "1 VHF-LOCAL"


def test_edits_reach_saved_image(radio, tmp_path):
    zone1 = radio.get_sub_devices()[0]
    mem = zone1.get_memory(5).dupe()
    mem.empty = False
    mem.freq = 145_375_000
    mem.name = "SAVED"
    zone1.set_memory(mem)
    path = tmp_path / "t.img"
    radio.save_mmap(str(path))
    assert drv.RT950ProDriver(str(path)).get_memory(5).name == "SAVED"


# --- write plan (what goes to the radio) -------------------------------------

def test_plan_unchanged_skips_aprs_and_high_channels(radio):
    plan, _ = _plan(radio)
    assert (0x57, 0x0000, 0x7800) in plan
    assert (0x57, 0xC000, 0x100) in plan
    assert all(cmd != 0x58 for cmd, _, _ in plan)


def test_plan_writes_high_channels_only_when_changed(radio):
    zone10 = radio.get_sub_devices()[9]
    mem = zone10.get_memory(99).dupe()
    mem.empty = False
    mem.freq = 145_500_000
    mem.name = "CH990"
    zone10.set_memory(mem)
    plan, _ = _plan(radio)
    assert (0x57, 0x0000, 0x7C00) in plan


def test_plan_writes_aprs_last_with_0x58_when_changed(radio):
    drv.set_aprs_value(radio._image.aprs, "custom_messages", "TEST")
    plan, _ = _plan(radio)
    assert plan[-1] == (0x58, 0x0000, 0x80)


def test_old_images_never_write_zone_names():
    raw = bytes(sample_radio().get_mmap().get_packed())
    radio = load(raw, fresh_read=False)          # no layout metadata
    plan, _ = _plan(radio)
    assert all(start != 0xC000 for _, start, _ in plan)


def test_legacy_960_image_never_writes_past_0x7800():
    raw = bytes(sample_radio().get_mmap().get_packed())
    legacy = raw[:0x7800] + raw[0x8000:-drv.ZONE_NAME_SEGMENT_BYTES]
    assert len(legacy) == 33152
    radio = load(legacy, fresh_read=False)
    zone10 = radio.get_sub_devices()[9]
    mem = zone10.get_memory(99).dupe()
    mem.empty = False
    mem.freq = 145_500_000
    zone10.set_memory(mem)
    plan, _ = _plan(radio)
    assert (0x57, 0x0000, 0x7800) in plan


# --- transport ----------------------------------------------------------------

class _FakePort:
    timeout = 3
    write_timeout = 3

    def close(self):
        pass


class _FakeTransport(drv.CloneSerialTransport):
    def __init__(self, fail_at=None):
        super().__init__(_FakePort(), logger=drv.LOG)
        self.sent = []
        self.fail_at = fail_at

    def handshake(self):
        self._xor_key = bytearray(b"    ")
        return "RT-950"

    def _write(self, data):
        self._last = data
        if len(data) > 1:
            self.sent.append((data[0], (data[1] << 8) | data[2]))

    def _read_exact(self, size):
        if self.fail_at == (self._last[0], (self._last[1] << 8) | self._last[2]):
            raise drv.CloneTransportError("Serial read timed out")
        return drv.ACK


def test_write_error_names_command_and_address(radio, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    drv.set_aprs_value(radio._image.aprs, "custom_messages", "TEST")
    segments, data = drv._build_write_plan(
        drv._build_clone_payload(radio._image), **radio._write_options())
    transport = _FakeTransport(fail_at=(0x58, 0x0000))
    with pytest.raises(drv.CloneTransportError, match="cmd 0x58 address 0x0000"):
        transport.write_clone(data, segments=segments)
    assert transport.sent[-1] == (0x58, 0x0000)
