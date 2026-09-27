# Runs inside GIMP with fonts (tests/run.sh): effects on a text layer,
# and Reapply Effects after the text has changed.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

sys.path.insert(0, os.path.join(os.environ['LFX_SRC'], 'tests'))
from lfxtest import *      # noqa: E402,F401,F403
import lfxtest             # noqa: E402


@case
def text_layer():
    image = new_image(400, 160)
    font = Gimp.context_get_font()
    check(font is not None, 'no font')
    text = Gimp.TextLayer.new(image, 'Hi', font, 72.0, Gimp.Unit.pixel())
    image.insert_layer(text, None, 0)
    text.set_offsets(20, 20)
    for effect in ('drop-shadow', 'stroke', 'bevel-emboss', 'inner-glow', 'gradient-overlay'):
        ok(run(effect, image, text))
    check(text.is_text_layer(), 'the text layer is no longer a text layer')
    group = text.get_parent()
    check(group is not None and group.get_name() == 'Hi-with-effects',
          'group %s' % (group.get_name() if group else None))
    names = [c.get_name() for c in group.get_children()]
    check(names == ['Hi-highlight', 'Hi-shadow', 'Hi-stroke', 'Hi-innerglow', 'Hi-gradient', 'Hi',
                    'Hi-dropshadow'], 'layers %s' % names)
    width = text.get_width()
    stroke = Pixels(image.get_layer_by_name('Hi-stroke'))
    check(max(stroke.alpha(x, y) for x in range(20, 20 + width) for y in range(20, 120)) > 0.9,
          'no stroke around the text')
    # the text changes (and GIMP renames the layer after it); the effects
    # follow it
    text.set_text('Hello')
    check(text.get_width() > width, 'the text layer did not grow')
    check(text.get_name() == 'Hello', 'the text layer is called %r' % text.get_name())
    ok(run('reapply-effects', image, text))
    renamed = [n.replace('Hi', 'Hello') for n in names]
    check([c.get_name() for c in group.get_children()] == renamed,
          'layers after reapply %s' % [c.get_name() for c in group.get_children()])
    check(group.get_name() == 'Hello-with-effects', 'group %r' % group.get_name())
    x, y, w, h = rect(text)
    check(rect(image.get_layer_by_name('Hello-innerglow')) == (x, y, w, h), 'the glow is not '
          'the size of the new text')
    shadow = rect(image.get_layer_by_name('Hello-dropshadow'))
    check(shadow[2] == w + 8, 'shadow width %d for text width %d' % (shadow[2], w))
    check(text.is_text_layer(), 'the text layer is no longer a text layer after reapply')


lfxtest.run_all(os.environ.get('LFX_ONLY', ''))
