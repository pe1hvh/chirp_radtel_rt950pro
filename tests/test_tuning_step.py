"""Regression tests for channel frequencies that fit no tuning step (0.1.8).

The radio stores a channel frequency as packed BCD in 10 Hz units and has no
per-channel tuning step. Up to 0.1.7 the driver offered CHIRP a list of
tuning steps (2.5-25 kHz), so CHIRP's ``validate_memory`` refused every
frequency that none of them reaches, e.g. UK CB channel 1 at 27.60125 MHz
(10 kHz raster with a 1.25 kHz offset). A paste, edit or import of such a
channel failed with "Unable to find a supported tuning step"; a paste of a
whole table left gaps. Reading these channels from the radio worked, because
that path does not validate.

The frequencies are public channel plans (UK CB 27/81 FM) and neutral
sample values; no user data.

    CHIRP_SRC=/path/to/chirp python3 -m pytest tests
"""

import builtins

import pytest

from sample import blank_image, chirp_common, drv, load

# CHIRP's validation messages use the gettext function ``_``, which the CHIRP
# application installs as a builtin at start-up; outside it, pass text through.
if not hasattr(builtins, "_"):
    builtins._ = lambda text: text

UK_CB_FIRST = 27_601_250
"""UK CB 27/81 FM channel 1 in Hz."""
UK_CB_LAST = 27_991_250
"""UK CB 27/81 FM channel 40 in Hz."""


def _memory(number, freq, duplex="", offset=0):
    """Return a simple FM memory.

    Args:
        number: CHIRP memory number.
        freq: Receive frequency in Hz.
        duplex: CHIRP duplex value (``""``, ``"+"``, ``"-"`` or ``"split"``).
        offset: Offset in Hz, or the TX frequency in Hz for ``split``.

    Returns:
        chirp_common.Memory: The memory, not empty, mode FM.
    """
    mem = chirp_common.Memory()
    mem.number = number
    mem.empty = False
    mem.freq = freq
    mem.duplex = duplex
    mem.offset = offset
    mem.name = "TEST"
    mem.mode = "FM"
    return mem


def _errors(radio, mem):
    """Return the texts of the ``ValidationError`` messages for ``mem``.

    Args:
        radio: The radio (or zone sub-device) that validates.
        mem: The memory to validate.

    Returns:
        list[str]: The error texts; warnings are left out.
    """
    return [str(msg) for msg in radio.validate_memory(mem)
            if isinstance(msg, chirp_common.ValidationError)]


def test_features_have_no_step_requirement():
    """The radio and its zones tell CHIRP that no tuning step is needed."""
    radio = load(blank_image())
    assert radio.get_features().has_nostep_tuning is True
    zone = radio.get_sub_devices()[0]
    assert zone.get_features().has_nostep_tuning is True


@pytest.mark.parametrize("freq", [UK_CB_FIRST, UK_CB_LAST, 145_500_000, 433_012_340])
def test_10_hz_frequencies_validate(freq):
    """These 10 Hz aligned frequencies in a valid band pass validation.

    Args:
        freq: Frequency in Hz under test.
    """
    radio = load(blank_image())
    zone = radio.get_sub_devices()[1]
    assert not _errors(radio, _memory(1, freq))
    assert not _errors(zone, _memory(1, freq))


def test_uk_cb_paste_round_trip():
    """All 40 UK CB channels can be stored in a zone and read back.

    This is what a paste does: validate, then ``set_memory``.
    """
    radio = load(blank_image())
    zone = radio.get_sub_devices()[2]
    for channel in range(40):
        mem = _memory(channel + 1, UK_CB_FIRST + channel * 10_000)
        assert not _errors(zone, mem)
        zone.set_memory(mem)
    reloaded = load(drv._build_clone_payload(radio._image))  # pylint: disable=protected-access
    zone = reloaded.get_sub_devices()[2]
    for channel in range(40):
        assert zone.get_memory(channel + 1).freq == UK_CB_FIRST + channel * 10_000


@pytest.mark.parametrize("freq, duplex, offset", [
    (145_500_005, "", 0),
    (145_500_000, "-", 600_005),
    (145_500_000, "split", 435_000_001),
])
def test_off_grid_frequency_is_refused(freq, duplex, offset):
    """An RX or TX frequency the radio cannot store gives a validation error.

    Without the step check, CHIRP would otherwise accept it and the write
    would fail later in the frequency encoder.

    Args:
        freq: Receive frequency in Hz.
        duplex: CHIRP duplex value.
        offset: Offset in Hz, or the TX frequency for ``split``.
    """
    radio = load(blank_image())
    messages = _errors(radio, _memory(1, freq, duplex, offset))
    assert any("10 Hz" in text for text in messages)
