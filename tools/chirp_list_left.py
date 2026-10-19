#!/usr/bin/env python3
"""Optional: show CHIRP's zone list on the LEFT instead of the right.

CHIRP shows a radio with more than two sub-devices (the RT-950 Pro has 10
zones) in a wx.Treebook that is hard-coded to wx.NB_RIGHT in
chirp/wxui/main.py. This script changes that one line to wx.NB_LEFT.

This MODIFIES YOUR CHIRP INSTALLATION. It affects every radio with a zone
list, makes a .orig backup, and is undone by a CHIRP update.

Usage:
    python3 tools/chirp_list_left.py            # apply
    python3 tools/chirp_list_left.py --restore  # restore the original
"""
import glob
import os
import shutil
import sys

OLD = "wx.Treebook(self, style=wx.NB_RIGHT)"
"""The line in CHIRP's ``main.py`` that puts the zone list on the right."""
NEW = "wx.Treebook(self, style=wx.NB_LEFT)"
"""Its replacement: the zone list on the left."""


def find_main():
    """Locate CHIRP's ``wxui/main.py`` in the pipx installation.

    Returns:
        str: Path of the first match of
        ``~/.local/share/pipx/venvs/chirp/lib/python3*/site-packages/chirp/wxui/main.py``.

    Raises:
        SystemExit: If no such file exists.
    """
    pattern = os.path.expanduser(
        "~/.local/share/pipx/venvs/chirp/lib/python3*/site-packages/chirp/wxui/main.py")
    hits = glob.glob(pattern)
    if not hits:
        sys.exit("CHIRP main.py not found under " + pattern)
    return hits[0]


def main() -> None:
    """Apply the patch, or restore the backup with ``--restore``.

    Applying makes ``main.py.orig`` once, then replaces ``OLD`` with ``NEW``;
    nothing is changed if the patch is already applied.

    Raises:
        SystemExit: If CHIRP is not found, ``--restore`` finds no backup, or
            ``OLD`` does not occur exactly once (other CHIRP version).
    """
    path = find_main()
    backup = path + ".orig"
    if "--restore" in sys.argv:
        if not os.path.exists(backup):
            sys.exit("No backup found: " + backup)
        shutil.copy2(backup, path)
        print("Original restored:", path)
        return
    text = open(path, encoding="utf-8").read()
    if NEW in text:
        print("Already applied:", path)
        return
    if text.count(OLD) != 1:
        sys.exit("Expected line not found exactly once; CHIRP version differs. Nothing changed.")
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    open(path, "w", encoding="utf-8").write(text.replace(OLD, NEW))
    print("Applied:", path)
    print("Backup: ", backup)


if __name__ == "__main__":
    main()
