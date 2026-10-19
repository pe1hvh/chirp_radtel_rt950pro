"""Tests for ``tools/check_docstrings.py`` and for the repository itself."""

import glob
import os
import sys

from sample import ROOT

sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_docstrings  # noqa: E402

_UNDOCUMENTED = '''"""Module."""


def public(x):
    return x


def _private(x):
    def nested(y):
        return y
    return nested(x)


try:
    import missing_module
except ImportError:
    class StandIn:
        """Documented class."""

        def method(self):
            return None
'''


def test_reports_public_private_nested_and_stand_in_objects():
    """Public, private, nested and ``except``-block objects are all reported."""
    assert check_docstrings.missing_docstrings(_UNDOCUMENTED, "x.py") == [
        "x.py:4: function public",
        "x.py:8: function _private",
        "x.py:9: function nested",
        "x.py:20: function method",
    ]


def test_reports_missing_module_docstring():
    """A module without a docstring is reported at line 1."""
    assert check_docstrings.missing_docstrings("x = 1\n", "m.py") == ["m.py:1: module"]


def test_main_exit_status(tmp_path, capsys):
    """Exit status 1 with a report line, 0 when everything is documented."""
    bad = tmp_path / "bad.py"
    bad.write_text("def f():\n    pass\n", encoding="utf-8")
    good = tmp_path / "good.py"
    good.write_text('"""M."""\n\n\ndef f():\n    """F."""\n', encoding="utf-8")
    assert check_docstrings.main([str(bad)]) == 1
    assert "function f" in capsys.readouterr().out
    assert check_docstrings.main([str(good)]) == 0


def test_repository_is_fully_documented():
    """The driver, the tools and the documentation build pass the check."""
    files = [os.path.join(ROOT, "radtel_rt950pro.py"), os.path.join(ROOT, "docs", "build.py")]
    files += sorted(glob.glob(os.path.join(ROOT, "tools", "*.py")))
    assert check_docstrings.main(files) == 0


def test_unreadable_file_is_reported_not_raised(tmp_path, capsys):
    """A file that is not UTF-8 gives exit status 1 and a report line."""
    bad = tmp_path / "latin1.py"
    bad.write_bytes(b'"""M\xe9."""\n')
    assert check_docstrings.main([str(bad)]) == 1
    assert "cannot check" in capsys.readouterr().out
