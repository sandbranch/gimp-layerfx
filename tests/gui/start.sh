#!/bin/sh
# Starts the Flatpak GIMP on a Broadway display, on the port
# LFX_BROADWAY_PORT (8087 by default; the page is http://127.0.0.1:port/)
# with tests/gui/gui-script.py (see there for LFX_GUI_MODE and
# LFX_GUI_EFFECT), in the throwaway profile of tests/run.sh, which
# installs the plug-in there. broadwayd stops when GIMP quits, also when
# GIMP fails. GIMP loads no fonts (--no-fonts): on Broadway it often hung
# at start while loading them.
#
#   LFX_GUI_MODE=dialog LFX_GUI_EFFECT=bevel-emboss tests/gui/start.sh
#
# GIMP starts when tests/output/gui/page-open exists: GIMP places its
# window for the size of the Broadway screen, which is that of the page
# once a browser shows it (common.sh does so first).
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
here=$(cd "$(dirname "$0")" && pwd)
tests=$(dirname "$here")
src=$(dirname "$tests")
out=$tests/output/gui
profile=$tests/output/profile
port=${LFX_BROADWAY_PORT:-8087}
display=$((port - 8080))
mkdir -p "$out"
# no Welcome dialog: GIMP shows it when the profile is of an older
# version, or when asked to
if ! grep -q config-version "$profile/gimprc" 2>/dev/null; then
    version=$(LC_ALL=C flatpak info org.gimp.GIMP | sed -n 's/^ *Version: *//p')
    printf '(config-version "%s")\n' "$version" >> "$profile/gimprc"
fi
grep -q show-welcome-dialog "$profile/gimprc" 2>/dev/null ||
  echo '(show-welcome-dialog no)' >> "$profile/gimprc"
# the windows where GIMP puts them by default (gui-test.sh clicks there),
# not where they were when GIMP last quit
rm -f "$profile/sessionrc"
exec flatpak run --no-documents-portal --filesystem="$src" \
  --env=GDK_BACKEND=broadway --env=BROADWAY_DISPLAY=:$display \
  --env=GIMP3_DIRECTORY="$tests/output/profile" --env=LFX_OUT="$out" \
  --env=LFX_GUI_MODE="${LFX_GUI_MODE:-dialog}" \
  --env=LFX_GUI_EFFECT="${LFX_GUI_EFFECT:-drop-shadow}" \
  --env=LFX_GUI_EXISTING="${LFX_GUI_EXISTING:-0}" \
  --command=sh org.gimp.GIMP -c \
  "broadwayd --port $port :$display & bw=\$!; trap 'kill \$bw' EXIT; \
   i=0; while [ ! -f '$out/page-open' ] && [ \$i -lt 300 ]; do sleep 0.2; i=\$((i+1)); done; \
   gimp-3.2 --no-splash --no-fonts \
   --batch-interpreter python-fu-eval -b \"exec(open('$here/gui-script.py').read())\""
