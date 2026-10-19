"""Tests for ``tools/ident_dump.py`` with a simulated radio (invented answers)."""

import sys
import types
from pathlib import Path

import pytest

from sample import drv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import ident_dump  # noqa: E402

F_ANSWER = bytes(range(0x30, 0x40))  # invented 16 bytes: "0123456789:;<=>?"
M_ANSWER = b"RT-950\x00V9.87"  # invented 12 bytes


class _SimRadio:
    """Answers the handshake like the radio; records what was written."""

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout", 3)
        self.write_timeout = kwargs.get("write_timeout", 3)
        self.written = []
        self._out = bytearray()
        self.closed = False

    def write(self, data):
        self.written.append(bytes(data))
        if data == drv.HANDSHAKE_STRING or data[:4] == b"SEND":
            self._out += drv.ACK
        elif data == b"F":
            self._out += F_ANSWER
        elif data == b"M":
            self._out += M_ANSWER
        return len(data)

    def read(self, size):
        chunk = bytes(self._out[:size])
        del self._out[:size]
        return chunk

    def reset_input_buffer(self):
        self._out.clear()

    def close(self):
        self.closed = True


@pytest.fixture
def sim(monkeypatch):
    radios = []

    def factory(*args, **kwargs):
        radios.append(_SimRadio(*args, **kwargs))
        return radios[-1]

    monkeypatch.setattr(drv, "serial", types.SimpleNamespace(Serial=factory))
    return radios


def test_identify_records_all_answers_and_ends_session(sim):
    exchanges = ident_dump.identify("/dev/null")
    rx = [data for direction, data in exchanges if direction == "RX"]
    assert rx == [drv.ACK, F_ANSWER, M_ANSWER, drv.ACK]
    radio = sim[0]
    assert radio.written[:3] == [drv.HANDSHAKE_STRING, b"F", b"M"]
    assert radio.written[3][:4] == b"SEND" and len(radio.written[3]) == 25
    assert radio.written[-1] == drv.END_COMMAND
    assert len(radio.written) == 5  # no read or write commands
    assert radio.closed


def test_find_version_reports_answer_and_offset():
    exchanges = [("TX", b"M"), ("RX", M_ANSWER)]
    hits = ident_dump.find_version(exchanges, "9.87")
    assert "answer 1 offset 8: ASCII (39 2E 38 37)" in hits


def test_find_version_bcd_and_binary():
    exchanges = [("RX", b"\x00\x00\x29\xff"), ("RX", b"\x1d\x00")]
    hits = ident_dump.find_version(exchanges, "ver0.29")
    assert "answer 1 offset 1: BCD major minor (00 29)" in hits
    assert "answer 2 offset 0: binary minor major (1D 00)" in hits


def test_version_patterns_rejects_bad_input():
    with pytest.raises(ValueError):
        ident_dump.version_patterns("abc")


def test_main_prints_answers(sim, capsys):
    assert ident_dump.main(["/dev/null", "--expect", "9.87"]) == 0
    out = capsys.readouterr().out
    assert "RX answer 3 (12 bytes): 52 54 2D 39 35 30 00 56 39 2E 38 37  |RT-950.V9.87|" in out
    assert "TX SEND key frame (25 bytes)" in out
    assert "TX E (end) (1 bytes)" in out
    assert "answer 3 offset 8: ASCII" in out


def test_empty_expect_is_refused(sim):
    with pytest.raises(SystemExit) as exc:
        ident_dump.main(["/dev/null", "--expect", ""])
    assert exc.value.code == 2


def test_version_patterns_rejects_non_ascii_digits():
    with pytest.raises(ValueError):
        ident_dump.version_patterns("٣.٢")
