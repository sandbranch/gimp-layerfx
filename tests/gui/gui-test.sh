#!/bin/sh
# Tests the dialog and undo on a Broadway display, with a headless
# Chrome: the Drop Shadow dialog with Preview on and OK (the effect is
# made once), with Preview on and Cancel (the preview is removed), on a
# layer that has a drop shadow already (the dialog shows its settings),
# and Edit > Undo (Ctrl+Z) after an effect (the image is as before, after
# one undo). Screenshots are left in tests/output/gui/. Run tests/run.sh
# first (it installs the plug-in into the test profile).
#
#   tests/gui/gui-test.sh
#   LFX_GUI_ONLY="OK UNDO" tests/gui/gui-test.sh    some of the sessions
#
# On Broadway the keys of a session sometimes reach no window of GIMP at
# all (in about a third of the sessions here, with or without a dialog
# before). The undo session is then repeated, up to 6 times; a wrong
# result after an undo fails at once.
#
# Needs a headless Chrome (google-chrome or chromium), node 22 and
# ../gimp-devtools (or GIMP_PLUGIN_DEVTOOLS) for gui/cdp.mjs.
# Prints PASS or FAIL for each check and exits non-zero if one fails.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
here=$(cd "$(dirname "$0")" && pwd)
status=0
pass () { echo "LFX GUI PASS $1"; }
fail () { echo "LFX GUI FAIL $1"; status=1; }
LFX_GUI_EFFECT=drop-shadow
export LFX_GUI_EFFECT LFX_GUI_MODE

# shellcheck source=SCRIPTDIR/common.sh
. "$here/common.sh"
rm -f "$out"/*.png

# the image window opens centred on the top left corner of the page: for
# the screenshots of the preview it is moved into view, right of the
# dialog (only on the page: Broadway does not know, so it is moved back
# before anything is clicked)
show_image="eval:(() => { for (const c of document.querySelectorAll('canvas'))
  if ((Number(c.style.zIndex) || 0) === 0) { const r = c.getBoundingClientRect();
    c.style.transform = 'translate(' + (560 - r.left) + 'px,' + (-r.top) + 'px)' }
  return 1 })()"
unmove="eval:(() => { for (const c of document.querySelectorAll('canvas'))
  c.style.transform = ''; return 1 })()"

# positions in the dialog, from its top left corner (the Broadway canvas,
# with the shadow around the window)
PREVIEW=49,423
OK=372,508
CANCEL=278,508

# a dialog session: Preview on, then OK or Cancel; or OK on a layer that
# has the effect (EXISTING)
dialog_session () {
    ending=$1
    LFX_GUI_MODE=dialog
    LFX_GUI_EXISTING=0
    [ "$ending" = EXISTING ] && LFX_GUI_EXISTING=1
    export LFX_GUI_EXISTING
    start_gimp
    find_dialog
    if [ -z "$at" ]; then
        fail "$ending: the dialog did not open (log: $out/gimp-dialog.log)"
        stop_all
        return
    fi
    pass "$ending: the dialog opened"
    [ "$ending" = OK ] && $cdp "$view" shot:"$out/01-dialog.png" >/dev/null
    if [ "$ending" != EXISTING ]; then
        xy=$PREVIEW
        $cdp "$view" click:"$(p "${xy%,*}" "${xy#*,}")" wait:4000 "$show_image" wait:500 \
          shot:"$out/02-preview-$ending.png" "$unmove" >/dev/null
    fi
    if [ "$ending" = CANCEL ]; then xy=$CANCEL; else xy=$OK; fi
    $cdp "$view" click:"$(p "${xy%,*}" "${xy#*,}")" >/dev/null
    if ! wait_for "$out/result.txt" 60; then
        fail "$ending: no result (log: $out/gimp-dialog.log)"
        stop_all
        return
    fi
    touch "$out/undone"
    case $ending in
    OK)
        grep -q '^status success$' "$out/result.txt" && pass "OK: status success" ||
          fail "OK: $(head -1 "$out/result.txt")"
        grep -q '^layers disc-with-effects\[disc,disc-dropshadow\] background$' \
          "$out/result.txt" && pass "OK: one drop shadow, the preview is gone" ||
          fail "OK: $(sed -n 2p "$out/result.txt")";;
    CANCEL)
        grep -q '^status cancel$' "$out/result.txt" && pass "Cancel: status cancel" ||
          fail "Cancel: $(head -1 "$out/result.txt")"
        grep -q '^layers disc background$' "$out/result.txt" &&
          pass "Cancel: the preview was removed" ||
          fail "Cancel: $(sed -n 2p "$out/result.txt")";;
    EXISTING)
        grep -q '^opacity disc=100.0 disc-dropshadow=44.0$' "$out/result.txt" &&
          pass "the dialog opened with the effect's own settings" ||
          fail "the dialog did not show the effect's settings: $(tail -1 "$out/result.txt")";;
    esac
    stop_all
}

# the undo session: Drop Shadow applied (without a dialog), then Ctrl+Z.
# Sets $undo_result to "none" if no key reached GIMP.
undo_session () {
    undo_result=
    LFX_GUI_MODE=undo
    LFX_GUI_EXISTING=0
    export LFX_GUI_EXISTING
    start_gimp
    if ! wait_for "$out/result.txt" 90; then
        fail "undo: the effect was not applied (log: $out/gimp-undo.log)"
        stop_all
        return
    fi
    grep -q '^layers disc-with-effects\[disc,disc-dropshadow\] background$' "$out/result.txt" ||
      fail "undo: the drop shadow was not made: $(sed -n 2p "$out/result.txt")"
    # The keys go to the window clicked last. The image window opens
    # centred on the page's top left corner, and of it only the lower
    # right corner of the Layers dock can be clicked: the empty part of
    # the list of layers, below the last one (the window has its default
    # size: start.sh removes the sessionrc). Escape first, for a popup
    # that may hold the keyboard. gui-script.py also presents the window.
    i=0
    until CDP_TIMEOUT=10000 $cdp wait:1000 key:Escape wait:300 click:40,82 wait:500 \
            >/dev/null 2>&1 || [ $i -ge 5 ]; do
        i=$((i + 1))
    done
    CDP_TIMEOUT=10000 $cdp "$show_image" shot:"$out/03-applied.png" "$unmove" >/dev/null 2>&1
    # Ctrl+Z until the layers change (up to 5 times), which gui-script.py
    # reports at once: an undo too many would be seen
    tries=0
    while [ ! -f "$out/undo.txt" ] && [ $tries -lt 5 ]; do
        node "$here/key.mjs" z
        tries=$((tries + 1))
        wait_for "$out/undo.txt" 4
    done
    CDP_TIMEOUT=10000 $cdp "$show_image" shot:"$out/04-undone.png" "$unmove" >/dev/null 2>&1
    touch "$out/undone"
    if ! wait_for "$out/undo.txt" 30; then
        fail "undo: no result (log: $out/gimp-undo.log)"
    elif grep -q '^layers disc-with-effects\[disc,disc-dropshadow\] background$' \
           "$out/undo.txt"; then
        undo_result=none
    else
        grep -q '^layers disc background$' "$out/undo.txt" &&
          pass "undo: one Ctrl+Z removes the whole effect" ||
          fail "undo: after Ctrl+Z: $(head -1 "$out/undo.txt")"
        grep -q '^pixels same$' "$out/undo.txt" && pass "undo: the layer is as before" ||
          fail "undo: the layer changed"
    fi
    stop_all
}

for session in ${LFX_GUI_ONLY:-OK CANCEL EXISTING UNDO}; do
    if [ "$session" = UNDO ]; then
        n=1
        undo_session
        while [ "$undo_result" = none ] && [ $n -lt 6 ]; do
            echo "LFX GUI (no key reached GIMP in undo session $n; once more)"
            n=$((n + 1))
            undo_session
        done
        [ "$undo_result" = none ] && fail "undo: no key reached GIMP in $n sessions"
    else
        dialog_session "$session"
    fi
done

[ $status = 0 ] && echo "LFX GUI all passed" || echo "LFX GUI FAILED (screenshots in $out)"
exit $status
