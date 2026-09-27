# The preview of the dialogs, without the dialog: Preview.update () and
# stop () with a stand-in for the dialog's config.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later


class FakeConfig:
    def __init__(self, effect, **values):
        self.values = {}
        for a in LFX.EFFECTS[effect].args:
            if a.kind == 'color':
                self.values[a.name] = Gegl.Color.new(a.extra[0])
            elif a.kind == 'gradient':
                self.values[a.name] = Gimp.context_get_gradient()
            elif a.kind == 'pattern':
                self.values[a.name] = Gimp.context_get_pattern()
            else:
                self.values[a.name] = a.default()
        self.values['preview'] = True
        self.values.update({k.replace('_', '-'): v for k, v in values.items()})

    def get_property(self, name):
        return self.values[name]


def tree(image):
    """The layers, with visibility, opacity and parasites."""
    def walk(items):
        out = []
        for it in items:
            p = it.get_parasite(LFX.PARASITE_EFFECT) or it.get_parasite(LFX.PARASITE_GROUP)
            entry = (it.get_name(), it.get_visible(), round(it.get_opacity(), 3),
                     bytes(p.get_data()) if p else None)
            out.append((entry, walk(it.get_children())) if it.is_group() else entry)
        return out
    return walk(image.get_layers())


@case
def preview_and_stop():
    for merge in (False, True):
        image, layer = disc_image()
        ok(run('drop-shadow', image, layer))
        ok(run('inner-glow', image, layer))
        before = tree(image)
        effect = LFX.EFFECTS['drop-shadow']
        preview = LFX.Preview(image, layer, effect, FakeConfig('drop-shadow', opacity=40.0,
                                                               merge=merge))
        preview.update()
        check(not image.undo_is_enabled(), 'merge %s: the undo history is not frozen' % merge)
        names = [c.get_name() for c in by_name(image, 'disc-with-effects').get_children()]
        if merge:
            # a merged copy of the layer is shown, the layer is hidden
            check(not layer.get_visible(), 'the layer is not hidden for the merge preview')
            check(len(names) == 4, 'layers during the merge preview: %s' % names)
        else:
            shadows = [c for c in by_name(image, 'disc-with-effects').get_children()
                       if c.get_name().startswith('disc-dropshadow')]
            check(len(shadows) == 2, 'no preview shadow: %s' % names)
            check([s.get_visible() for s in shadows].count(True) == 1,
                  'the old shadow is not hidden')
            check(any(abs(s.get_opacity() - 40.0) < 1e-6 for s in shadows),
                  'the preview is not at the new opacity')
        preview.update()        # again, as when a setting changes
        preview.stop()
        check(image.undo_is_enabled(), 'merge %s: the undo history is still frozen' % merge)
        check(tree(image) == before, 'merge %s: the image is not as before:\n%s\n%s'
              % (merge, tree(image), before))
