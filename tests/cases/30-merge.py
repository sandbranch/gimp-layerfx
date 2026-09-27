# The Merge with layer option.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later

ALL_EFFECTS = ['drop-shadow', 'inner-shadow', 'outer-glow', 'inner-glow', 'bevel-emboss', 'satin',
               'stroke', 'color-overlay', 'gradient-overlay', 'pattern-overlay']


@case
def merge_drop_shadow():
    image, layer = disc_image()
    ok(run('drop-shadow', image, layer, size=0, spread=100.0, offset_distance=10.0,
           offset_angle=90.0, merge=True))
    check(structure(image) == ['disc', 'background'], 'layers %s' % structure(image))
    merged = by_name(image, 'disc')
    check(rect(merged) == (0, 0, 160, 170), 'rect %s' % (rect(merged),))
    check(merged.get_mode() == Gimp.LayerMode.NORMAL, 'mode %s' % mode_nick(merged))
    check(merged.get_parasite(LFX.PARASITE_EFFECT) is None, 'a merged effect has a parasite')
    px = Pixels(merged)
    approx(px.alpha(CX, CY + 38), 0.75, 0.01, 'alpha of the shadow')
    r, g, b, a = px(CX, CY)
    check(abs(b - 0.8) < 0.01 and a > 0.99, 'the disc changed: %s' % ((r, g, b, a),))
    check(image.get_selected_layers() == [merged], 'selected %s' % image.get_selected_layers())


@case
def merge_inside_keeps_alpha_and_mask():
    image = new_image()
    layer = shape_layer(image, lambda x, y: 1.0)
    mask = layer.create_mask(Gimp.AddMaskType.WHITE)
    layer.add_mask(mask)
    put(mask, lambda x, y: (disc(CX, CY, 30)(x, y),))
    image2, ref = disc_image()
    ok(run('color-overlay', image, layer, color='#00ff00', merge=True))
    merged = by_name(image, 'disc')
    check(merged.get_mask() is not None, 'the layer mask is gone')
    check(rect(merged) == (0, 0, 160, 160), 'rect %s' % (rect(merged),))
    px = Pixels(merged)
    approx(px.alpha(5, 5), 1.0, 1e-4, 'alpha outside the mask')
    r, g, b, a = px(CX, CY)
    check(g > 0.99 and r < 0.01, 'not the overlay colour: %s' % ((r, g, b),))
    m = Pixels(merged.get_mask(), 'Y float')
    for p in ((CX, CY), (5, 5), (CX + 29, CY), (CX + 31, CY)):
        approx(m(*p)[0], disc(CX, CY, 30)(*p), 0.005, 'mask at %s' % (p,))
    # a semi-transparent layer keeps its alpha exactly
    image = new_image()
    layer = shape_layer(image, lambda x, y: 0.5 * disc(CX, CY, 30)(x, y))
    before = Pixels(layer)
    ok(run('inner-glow', image, layer, merge=True))
    after = Pixels(by_name(image, 'disc'))
    worst = max(abs(after.alpha(x, y) - before.alpha(x, y)) for x in range(40, 120, 2)
                for y in range(40, 120, 2))
    check(worst < 1e-3, 'the alpha changed by %.4f' % worst)


@case
def merge_every_effect():
    for effect in ALL_EFFECTS:
        for masked in (False, True):
            image, layer = disc_image()
            if masked:
                mask = layer.create_mask(Gimp.AddMaskType.WHITE)
                layer.add_mask(mask)
                put(mask, lambda x, y: (0.0 if x < 60 else 1.0,))
            before = visible(image)
            ok(run(effect, image, layer, merge=True))
            check(structure(image) == ['disc', 'background'],
                  '%s: layers %s' % (effect, structure(image)))
            after = visible(image)
            changed = sum(1 for x in range(0, 160, 4) for y in range(0, 160, 4)
                          if abs(after(x, y)[1] - before(x, y)[1]) > 0.02)
            check(changed > 5, '%s: the merged effect changed %d pixels' % (effect, changed))


@case
def merge_into_layer_with_effects():
    image, layer = disc_image()
    ok(run('stroke', image, layer, position=100.0))
    ok(run('color-overlay', image, layer, color='#00ff00', merge=True))
    check(children(image) == ['disc', 'disc-stroke'], 'layers %s' % children(image))
    merged = by_name(image, 'disc')
    check(LFX.group_source(by_name(image, 'disc-with-effects')) == merged,
          'the group does not know the merged layer')
    ok(run('reapply-effects', image, merged))
    check(children(image) == ['disc', 'disc-stroke'], 'after reapply: %s' % children(image))
