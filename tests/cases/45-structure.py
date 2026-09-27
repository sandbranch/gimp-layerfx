# Layers inside groups, masks that are switched off, and settings at the
# ends of their ranges.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later


@case
def layer_inside_a_group():
    image, layer = disc_image()
    outer = Gimp.GroupLayer.new(image, 'outer')
    image.insert_layer(outer, None, 0)
    image.reorder_item(layer, outer, 0)
    ok(run('drop-shadow', image, layer))
    ok(run('inner-glow', image, layer))
    check(structure(image) == [('outer', [('disc-with-effects', ['disc-innerglow', 'disc',
                                                                   'disc-dropshadow'])]),
                               'background'], 'layers %s' % structure(image))
    ok(run('reapply-effects', image, layer))
    ok(run('stroke', image, layer, merge=True))
    check(structure(image) == [('outer', [('disc-with-effects', ['disc-innerglow', 'disc',
                                                                   'disc-dropshadow'])]),
                               'background'], 'after merging: %s' % structure(image))


@case
def mask_switched_off():
    # a mask that hides the left half, switched off: the effect is that of
    # the whole disc, and merging keeps the mask, off
    image, layer = disc_image(offset=(20, 10), layer_size=(130, 140))
    mask = layer.create_mask(Gimp.AddMaskType.WHITE)
    layer.add_mask(mask)
    put(mask, lambda x, y: (0.0 if x + 20 < CX else 1.0,))
    layer.set_apply_mask(False)
    ok(run('drop-shadow', image, layer, size=0, spread=100.0, offset_distance=0.0))
    px = Pixels(by_name(image, 'disc-dropshadow'))
    approx(px.alpha(CX - 20, CY), 1.0, 0.01, 'shadow of the hidden half')
    ok(run('stroke', image, layer, position=100.0, merge=True))
    merged = by_name(image, 'disc')
    check(merged.get_mask() is not None and not merged.get_apply_mask(),
          'the mask is not kept switched off')
    m = Pixels(merged.get_mask(), 'Y float')
    approx(m(CX - 20, CY)[0], 0.0, 0.01, 'mask in the left half')
    approx(m(CX + 20, CY)[0], 1.0, 0.01, 'mask in the right half')
    # where the layer grew (the stroke outside its old bounds, at the
    # top: the old layer started at y = 10) the mask shows it
    ox, oy, ow, oh = rect(merged)
    check(oy < 10, 'the layer did not grow: %s' % (rect(merged),))
    approx(m(CX + 10, oy)[0], 1.0, 0.01, 'mask where the layer grew')
    # a mask switched on is applied when merging an effect that reaches out
    image, layer = disc_image()
    mask = layer.create_mask(Gimp.AddMaskType.WHITE)
    layer.add_mask(mask)
    put(mask, lambda x, y: (0.0 if x < CX else 1.0,))
    ok(run('drop-shadow', image, layer, merge=True))
    merged = by_name(image, 'disc')
    check(merged.get_mask() is None, 'the mask in use was kept')
    check(Pixels(merged).alpha(CX - 20, CY) < 0.01, 'the mask was not applied')


@case
def settings_at_their_ends():
    # every effect with its sizes at 0 (or 1) and at the top of the range,
    # angles at -180 and 180, opacity 0: no errors, layers of sane sizes
    for effect, low, high in (
            ('drop-shadow', dict(size=0, spread=0.0, offset_distance=0.0, offset_angle=-180.0),
             dict(size=250, spread=100.0, offset_distance=300.0, offset_angle=180.0, noise=100.0)),
            ('inner-shadow', dict(size=0, choke=0.0, offset_distance=0.0),
             dict(size=250, choke=100.0, offset_distance=300.0, noise=100.0)),
            ('outer-glow', dict(size=0, spread=0.0), dict(size=250, spread=100.0, noise=100.0)),
            ('inner-glow', dict(size=0, choke=0.0), dict(size=250, choke=100.0, noise=100.0)),
            ('bevel-emboss', dict(size=0, depth=1, soften=0, altitude=0.0),
             dict(size=250, depth=65, soften=16, altitude=90.0, style='pillow-emboss')),
            ('satin', dict(size=0, offset_distance=0.0), dict(size=250, offset_distance=300.0)),
            ('stroke', dict(size=1, position=0.0), dict(size=250, position=100.0)),
            ('color-overlay', dict(opacity=0.0), dict(opacity=100.0)),
            ('pattern-overlay', dict(scale=1.0), dict(scale=1000.0))):
        for args in (low, high):
            image, layer = disc_image(size=120, r=20)
            if effect == 'pattern-overlay':
                args = dict(args, pattern=Gimp.Pattern.get_by_name('Pine'))
            ok(run(effect, image, layer, **args))
            for child in by_name(image, 'disc-with-effects').get_children():
                w, h = child.get_width(), child.get_height()
                check(0 < w < 1000 and 0 < h < 1000, '%s %s: %s is %d x %d'
                      % (effect, args, child.get_name(), w, h))
