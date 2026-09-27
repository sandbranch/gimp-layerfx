# Drop Shadow on an opaque disc on a transparent layer.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later


@case
def drop_shadow_layers():
    image, layer = disc_image()
    ok(run('drop-shadow', image, layer))
    check(structure(image) == [('disc-with-effects', ['disc', 'disc-dropshadow']), 'background'],
          'layers %s' % structure(image))
    group = by_name(image, 'disc-with-effects')
    check(group.get_mode() == Gimp.LayerMode.PASS_THROUGH, 'group mode %s' % mode_nick(group))
    shadow = by_name(image, 'disc-dropshadow')
    check(shadow.get_mode() == Gimp.LayerMode.MULTIPLY, 'mode %s' % mode_nick(shadow))
    approx(shadow.get_opacity(), 75.0, 1e-6, 'opacity')
    # size 5: grown by round(ceil(5 / 2) * 1.2) = 4 on each side, moved
    # by the offset of 5 pixels at 120 degrees: (3, 4)
    check(rect(shadow) == (3 - 4, 4 - 4, 168, 168), 'rect %s' % (rect(shadow),))
    check(info(shadow)['effect'] == 'drop-shadow', 'parasite %s' % info(shadow))
    check(image.get_selected_layers() == [layer], 'selected %s' % image.get_selected_layers())


@case
def drop_shadow_offset():
    image, layer = disc_image(r=30)
    ok(run('drop-shadow', image, layer, size=0, offset_distance=20.0, offset_angle=90.0,
           opacity=100.0))
    px = Pixels(by_name(image, 'disc-dropshadow'))
    # light from above (90 degrees): the shadow is the disc 20 pixels down
    approx(px.alpha(CX, CY + 30 + 20 - 2), 1.0, 0.01, 'alpha at the moved bottom edge')
    approx(px.alpha(CX, CY - 30 + 20 - 2), 0.0, 0.01, 'alpha above the moved top edge')
    approx(px.alpha(CX, CY + 30 + 20 + 2), 0.0, 0.01, 'alpha below the moved disc')
    approx(px.alpha(CX - 28, CY + 20), 1.0, 0.01, 'alpha at the moved left edge')
    # and from the left (180 degrees): to the right
    image, layer = disc_image(r=30)
    ok(run('drop-shadow', image, layer, size=0, offset_distance=12.0, offset_angle=180.0))
    px = Pixels(by_name(image, 'disc-dropshadow'))
    approx(px.alpha(CX + 30 + 10, CY), 1.0, 0.01, 'alpha right of the disc')
    approx(px.alpha(CX - 30 + 10, CY), 0.0, 0.01, 'alpha at the left edge')


@case
def drop_shadow_ramp():
    image, layer = disc_image(r=30)
    ok(run('drop-shadow', image, layer, size=10, offset_distance=0.0))
    px = Pixels(by_name(image, 'disc-dropshadow'))
    values = [px.alpha(CX + r, CY) for r in range(20, 40)]
    approx(values[0], 1.0, 0.01, 'alpha well inside')
    approx(px.alpha(CX + 30, CY), 0.5, 0.15, 'alpha at the edge')
    approx(values[-1], 0.0, 0.01, 'alpha well outside')
    check(all(a >= b - 1e-4 for a, b in zip(values, values[1:])), 'not falling: %s' % values)
    # all around the same
    for d in range(0, 360, 30):
        approx(px.alpha(*at(30, d)), 0.5, 0.15, 'alpha at the edge at %d degrees' % d)


@case
def drop_shadow_spread():
    image, layer = disc_image(r=30, aa=False)
    ok(run('drop-shadow', image, layer, size=10, spread=100.0, offset_distance=0.0))
    px = Pixels(by_name(image, 'disc-dropshadow'))
    # spread 100: no ramp, the shape grown by ceil(10 / 2) = 5 pixels
    approx(px.alpha(CX + 34, CY), 1.0, 0.01, 'alpha 4 pixels out')
    approx(px.alpha(CX + 36, CY), 0.0, 0.01, 'alpha 6 pixels out')


@case
def drop_shadow_blends_with_the_image_below():
    image, layer = disc_image(r=30)
    before = visible(image)
    ok(run('drop-shadow', image, layer, size=4, offset_distance=10.0, offset_angle=90.0))
    after = visible(image)
    x, y = CX, CY + 34
    check(after(x, y)[0] < before(x, y)[0] - 0.1,
          'the shadow does not darken the background: %.3f, was %.3f' % (after(x, y)[0],
                                                                          before(x, y)[0]))
    # the disc itself is unchanged
    for p in ((CX, CY), (CX - 20, CY - 5)):
        approx(after(*p)[2], before(*p)[2], 0.005, 'the disc at %s' % (p,))


@case
def drop_shadow_knockout():
    # a disc at half opacity: its shadow is at half opacity too, and shows
    # through it unless the layer knocks it out
    for knockout, want in ((False, 0.5), (True, 0.0)):
        image = new_image()
        layer = shape_layer(image, lambda x, y: 0.5 * disc(CX, CY, 30)(x, y))
        ok(run('drop-shadow', image, layer, size=0, offset_distance=0.0, spread=100.0,
               opacity=100.0, knockout=knockout))
        px = Pixels(by_name(image, 'disc-dropshadow'))
        a = px.alpha(CX, CY)
        check(abs(a - want) < 0.02 if want else a < 0.01,
              'knockout %s: alpha under the layer %.3f' % (knockout, a))
        # the shadow outside is there in both cases (size 0, spread 100:
        # the disc as it is)
        approx(px.alpha(CX + 28, CY + 3), 0.0 if knockout else 0.5, 0.02,
               'knockout %s: alpha inside the edge' % knockout)
        approx(px.alpha(CX + 32, CY), 0.0, 0.01, 'alpha outside')


@case
def drop_shadow_contour():
    image, layer = disc_image(r=30)
    ok(run('drop-shadow', image, layer, size=10, offset_distance=0.0, contour='cone'))
    px = Pixels(by_name(image, 'disc-dropshadow'))
    # the cone contour: 0 where the ramp is 0 or 1, 1 in the middle
    check(px.alpha(CX + 30, CY) > 0.8, 'alpha at the edge %.3f' % px.alpha(CX + 30, CY))
    check(px.alpha(CX + 20, CY) < 0.05, 'alpha inside %.3f' % px.alpha(CX + 20, CY))
    check(px.alpha(CX + 37, CY) < 0.01, 'alpha outside %.3f' % px.alpha(CX + 37, CY))


@case
def drop_shadow_noise():
    image, layer = disc_image(r=30)
    ok(run('drop-shadow', image, layer, size=10, offset_distance=0.0, noise=60.0))
    px = Pixels(by_name(image, 'disc-dropshadow'))
    values = [px.alpha(*at(30, d / 4.0)) for d in range(0, 1440, 7)]
    check(std(values) > 0.05, 'no noise at the edge: std %.3f' % std(values))
    approx(px.alpha(CX + 40, CY), 0.0, 0.01, 'alpha outside')
