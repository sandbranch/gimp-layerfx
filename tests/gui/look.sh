#!/bin/sh
# Opens the dialog of an effect on a Broadway display, does the given
# steps in it and leaves screenshots of the dialog and of the whole page
# in tests/output/gui/<effect>-dialog.png and <effect>-page.png; then
# stops GIMP. For looking at the layouts. Run tests/run.sh first.
#
#   tests/gui/look.sh <effect> [step...]
#   tests/gui/look.sh stroke click:30,40 wait:1000
#
# The steps are those of gimp-plugin-devtools/gui/cdp.mjs, with click,
# down, move and up at positions from the dialog's top left corner.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
here=$(cd "$(dirname "$0")" && pwd)
[ -n "$1" ] || { sed -n '2,13s/^# \{0,1\}//p' "$0"; exit 1; }
LFX_GUI_EFFECT=$1
LFX_GUI_MODE=dialog
export LFX_GUI_EFFECT LFX_GUI_MODE
shift

# shellcheck source=SCRIPTDIR/common.sh
. "$here/common.sh"
start_gimp
find_dialog
if [ -z "$at" ]; then
    echo "LFX GUI FAIL the dialog did not open (log: $out/gimp-dialog.log)"
    exit 1
fi
steps=
for step in "$@"; do
    case $step in
        click:*|down:*|move:*|up:*)
            xy=${step#*:}
            step=${step%%:*}:$(p "${xy%,*}" "${xy#*,}");;
    esac
    steps="$steps $step"
done
# shellcheck disable=SC2086
$cdp "$view" $steps wait:500 shot:"$out/$LFX_GUI_EFFECT-page.png" >/dev/null || exit 1
python3 - "$out/$LFX_GUI_EFFECT-page.png" "$out/$LFX_GUI_EFFECT-dialog.png" "$x0" "$y0" "$dw" "$dh" <<'PY'
import sys
from PIL import Image
page, dialog, x, y, w, h = sys.argv[1:]
x, y, w, h = int(x), int(y), int(w), int(h)
Image.open(page).crop((x, y, x + w, y + h)).save(dialog)
PY
echo "$out/$LFX_GUI_EFFECT-dialog.png"
