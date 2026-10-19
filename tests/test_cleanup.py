"""Regression tests for the clean-up of 0.1.6 (split display, CHIRP stand-in).

Neutral, invented frequencies. The split, stand-in and ``_ToneInfo`` tests fail
on the driver before the fix; the simplex and +/- offset cases guard against
regressions.

    CHIRP_SRC=/path/to/chirp python3 -m pytest tests
"""

# The tests inspect the parsed image (radio._image), as test_driver.py does.
# pylint: disable=protected-access

import ast
import os
import subprocess
import sys

import pytest

from sample import ROOT, blank_image, drv, load


def _radio_with_frequencies(rx_hz, tx_hz):
    """Return a radio whose channel 1 has the given RX and TX frequency.

    Args:
        rx_hz: Receive frequency in Hz.
        tx_hz: Transmit frequency in Hz.

    Returns:
        The loaded driver.
    """
    record = drv.ChannelRecord.from_bytes(bytes(32))
    record.rx_hz = rx_hz
    record.tx_hz = tx_hz
    record.name = "TEST"
    record.tx_enabled = True
    image = bytearray(blank_image())
    image[0:32] = record.to_bytes()
    return load(bytes(image))


# --- split display -----------------------------------------------------------

@pytest.mark.parametrize(
    "rx_hz, tx_hz, duplex, offset",
    [
        (145_500_000, 145_500_000, "", 0),
        (145_600_000, 145_000_000, "-", 600_000),
        (430_000_000, 437_600_000, "+", 7_600_000),
        (145_500_000, 435_000_000, "split", 435_000_000),
    ],
)
def test_duplex_follows_the_bands(rx_hz, tx_hz, duplex, offset):
    """RX and TX in different bands of ``valid_bands`` read as split."""
    mem = _radio_with_frequencies(rx_hz, tx_hz).get_memory(1)
    assert (mem.duplex, mem.offset) == (duplex, offset)


def test_split_channel_round_trips():
    """A split channel (RX and TX in different bands) is written and read back as split."""
    radio = _radio_with_frequencies(145_500_000, 145_500_000)
    mem = radio.get_memory(1)
    mem.duplex = "split"
    mem.offset = 435_000_000
    radio.set_memory(mem)
    assert radio._image.channels[0].tx_hz == 435_000_000
    back = radio.get_memory(1)
    assert (back.duplex, back.offset) == ("split", 435_000_000)


def test_unused_tone_info_class_is_gone():
    """The unused ``_ToneInfo`` class has been removed."""
    assert not hasattr(drv, "_ToneInfo")


# --- CHIRP stand-in -------------------------------------------------------------

_WITHOUT_CHIRP = r"""
import sys

class _BlockChirp:
    def find_spec(self, name, path=None, target=None):
        if name == "chirp" or name.startswith("chirp."):
            raise ImportError("chirp blocked for this test")
        return None

sys.meta_path.insert(0, _BlockChirp())
sys.path.insert(0, sys.argv[1])
import radtel_rt950pro as drv

assert not drv.HAVE_CHIRP
radio = drv.RT950ProDriver(None)
for name in ("get_features", "get_settings"):
    try:
        getattr(radio, name)()
    except drv.errors.RadioError as exc:
        assert "CHIRP" in str(exc), exc
    else:
        raise AssertionError(name + " did not raise")
for name, arg in (("get_memory", 1), ("set_memory", drv.chirp_common.Memory())):
    try:
        getattr(radio, name)(arg)
    except drv.errors.RadioError as exc:
        assert "CHIRP" in str(exc), exc
    else:
        raise AssertionError(name + " did not raise")
print("ok")
"""


def test_without_chirp_the_driver_says_chirp_is_required():
    """Without CHIRP get_features, get_settings, get_memory and set_memory raise ``RadioError``."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "CHIRP_SRC")}
    result = subprocess.run(
        [sys.executable, "-c", _WITHOUT_CHIRP, ROOT],
        capture_output=True, text=True, env=env, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_with_chirp_the_flag_is_set():
    """With CHIRP importable the driver uses it."""
    assert drv.HAVE_CHIRP


def test_find_zone_names_usage_has_a_single_backslash():
    """The usage text printed by find_zone_names.py continues the shell line."""
    with open(os.path.join(ROOT, "tools", "find_zone_names.py"), encoding="utf-8") as fh:
        doc = ast.get_docstring(ast.parse(fh.read()))
    assert "find_zone_names.py \\\n" in doc
