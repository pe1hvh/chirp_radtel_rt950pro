#!/usr/bin/env python3
"""Write a CHIRP .img with the neutral two-zone sample set (no radio needed).

    CHIRP_SRC=/path/to/chirp python3 tools/make_sample_image.py sample.img

Open the result in CHIRP (with the driver loaded) to look at the zone tabs.
Do NOT upload it to a radio: the settings blocks are zero-filled.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
from sample import sample_radio  # noqa: E402

if len(sys.argv) != 2:
    sys.exit(__doc__)
sample_radio().save_mmap(sys.argv[1])
print("Written:", sys.argv[1])
