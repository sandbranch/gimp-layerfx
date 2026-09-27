#!/bin/sh
# Tests Layer Effects: installs the plug-in into a throwaway GIMP profile
# in tests/output (GIMP3_DIRECTORY) and runs tests/gimp-test.py inside
# GIMP without a window; then, if a headless Chrome and node are there,
# the dialog and undo tests on a Broadway display (tests/gui/gui-test.sh).
# GIMP runs isolated from your own folders (tests/isolate.sh, with
# gimp-devtools/gimp-run.sh): HOME and the XDG folders inside its
# Flatpak point into tests/output/gimp-home, so your GIMP profile,
# plug-ins and ~/.var/app/org.gimp.GIMP are not used or changed. Before
# and after, it lists your folders of GIMP and the other apps
# (gimp-devtools/snapshot.sh) and fails if anything there changed.
#
#   tests/run.sh                 all tests
#   LFX_ONLY=stroke tests/run.sh   only the GIMP cases whose names match
#   LFX_GUI=0 tests/run.sh       without the Broadway tests
#   GIMP_FLATPAK=0 tests/run.sh  with a native GIMP 3 (gimp-console-3.2
#                                or gimp-console on the PATH)
#
# Prints PASS or FAIL for each case and exits non-zero if any case fails
# or if the plug-in printed a traceback, warnings or criticals.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
here=$(cd "$(dirname "$0")" && pwd)
src=$(dirname "$here")
out=$here/output
profile=$out/profile
log=$out/test.log
status=0

GIMP_RUN_HOME=$out/gimp-home
export GIMP_RUN_HOME
# shellcheck source=SCRIPTDIR/isolate.sh
. "$here/isolate.sh"
mkdir -p "$out"
snapshot_take "$out/snapshot-before.txt"

rm -rf "$profile"
mkdir -p "$profile/plug-ins/layerfx"
cp "$src/layerfx/layerfx.py" "$profile/plug-ins/layerfx/layerfx.py"
chmod 755 "$profile/plug-ins/layerfx/layerfx.py"

if [ -z "$GIMP_FLATPAK" ]; then
    if command -v flatpak >/dev/null 2>&1 && flatpak info org.gimp.GIMP >/dev/null 2>&1; then
        GIMP_FLATPAK=1
    else
        GIMP_FLATPAK=0
    fi
fi

# GIMP loads no fonts (--no-fonts): GIMP 3.2 can hang while loading
# them. The text layer test runs in a second GIMP with fonts, with a
# time limit.
run_gimp () {
    fonts=$1
    script=$2
    if [ "$GIMP_FLATPAK" = 1 ]; then
        console=gimp-console-3.2
    else
        console=$(command -v gimp-console-3.2 || command -v gimp-console)
        [ -n "$console" ] || { echo "LFX FAIL: no gimp-console on the PATH"; return 1; }
    fi
    gimp_run --timeout=1800 --filesystem="$src" \
      --env=GIMP3_DIRECTORY="$profile" --env=LFX_ONLY="$LFX_ONLY" \
      --env=LFX_SRC="$src" --env=LFX_OUT="$out" -- \
      "$console" --no-interface ${fonts:+"$fonts"} --batch-interpreter python-fu-eval \
      -b "exec(open('$script').read())" --quit
}

echo "== GIMP"
run_gimp --no-fonts "$here/gimp-test.py" >"$log" 2>&1
grep -E "^LFX|Traceback|^  File|Error" "$log"
grep -q "^LFX failures: 0$" "$log" || status=1
# messages of the plug-in (its process is named after it), and GIMP
# closing undo groups that the plug-in left open. A GEGL operation of
# another project that may be installed (LinuxBeaver's colorremoval)
# warns about its default colour in every process that loads it.
if grep -E "layerfx.py.*(WARNING|CRITICAL)|inconsistent state|Traceback" "$log" |
     grep -v 'Parsing of color string "0.0, 1.0, 0.0"'; then
    echo "LFX FAIL: warnings or tracebacks from the plug-in, see $log"
    status=1
fi

echo "== GIMP with fonts (text layers)"
if [ -z "$LFX_ONLY" ] || echo text | grep -q "$LFX_ONLY"; then
    run_gimp "" "$here/gimp-text-test.py" >"$out/text.log" 2>&1
    code=$?
    if [ $code = 124 ]; then
        echo "LFX SKIP text layers: GIMP hung while loading fonts (log: $out/text.log)"
    else
        grep -E "^LFX|Traceback|^  File" "$out/text.log"
        grep -q "^LFX failures: 0$" "$out/text.log" || status=1
    fi
fi

if [ "$LFX_GUI" != 0 ] && [ -z "$LFX_ONLY" ]; then
    echo "== GUI (Broadway)"
    "$here/gui/gui-test.sh" || status=1
fi

echo "== your folders of GIMP and the other apps"
snapshot_check "$out/snapshot-before.txt" "LFX " || status=1

[ $status = 0 ] && echo "LFX all passed" || echo "LFX FAILED (log: $log)"
exit $status
