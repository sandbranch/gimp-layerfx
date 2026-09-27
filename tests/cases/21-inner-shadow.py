# Inner Shadow.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later


@case
def inner_shadow_layers():
    image, layer = disc_image()
    ok(run('inner-shadow', image, layer))
    check(structure(image) == [('disc-with-effects', ['disc-innershadow', 'disc']), 'background'],
          'layers %s' % structure(image))
    shadow = by_name(image, 'disc-innershadow')
    check(rect(shadow) == rect(layer), 'rect %s' % (rect(shadow),))
    check(shadow.get_mode() == Gimp.LayerMode.MULTIPLY, 'mode %s' % mode_nick(shadow))
    approx(shadow.get_opacity(), 75.0, 1e-6, 'opacity')


@case
def inner_shadow_inside_only():
    image, layer = disc_image()
    ok(run('inner-shadow', image, layer, size=6, offset_distance=6.0))
    px = Pixels(by_name(image, 'disc-innershadow'))
    for d in range(0, 360, 15):
        check(px.alpha(*at(31.5, d)) < 0.01, 'alpha outside at %d degrees' % d)
    check(px.alpha(CX, CY) < 0.01, 'alpha in the middle %.3f' % px.alpha(CX, CY))
    # light from 120 degrees: the shadow falls on the inside of the upper
    # left edge
    upper_left = arc_mean(px, 26, 29, 110, 160)
    lower_right = arc_mean(px, 26, 29, 290, 340)
    check(upper_left > 0.5 and lower_right < 0.2,
          'upper left %.3f, lower right %.3f' % (upper_left, lower_right))


@case
def inner_shadow_center():
    image, layer = disc_image()
    ok(run('inner-shadow', image, layer, size=20, offset_distance=0.0, source='center'))
    px = Pixels(by_name(image, 'disc-innershadow'))
    # as in the original, the ramp starts ceil(size / 2) outside the edge
    # and is full ceil(size / 2) inside it
    check(px.alpha(CX, CY) > 0.95, 'alpha in the middle %.3f' % px.alpha(CX, CY))
    approx(px.alpha(CX + 29, CY), 0.55, 0.1, 'alpha at the edge')
    check(px.alpha(CX + 31, CY) < 0.01, 'alpha outside %.3f' % px.alpha(CX + 31, CY))
