# Runs inside GIMP (tests/run.sh), without a window: calls the Layer
# Effects procedures non-interactively on generated images and checks
# the layers they make and their pixels. Prints "LFX PASS <case>" or
# "LFX FAIL <case>: <why>" for each case, and "LFX failures: <n>" at the
# end.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.environ['LFX_SRC'], 'tests'))
from lfxtest import *      # noqa: E402,F401,F403
import lfxtest             # noqa: E402

lfxtest.load_cases(os.path.join(os.environ['LFX_SRC'], 'tests', 'cases'))
lfxtest.run_all(os.environ.get('LFX_ONLY', ''))
