# Stroke, Color Overlay, Gradient Overlay and Pattern Overlay.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later

# position: (layers, rect, radii inside the stroke, radii outside it)
# (the edge of the disc is at 30, the stroke is 4 wide)
STROKES = {
    0.0: (['disc-stroke', 'disc'], (0, 0, 160, 160), (26.5, 29.2), (25.0, 30.8)),
    50.0: (['disc-stroke', 'disc'], (-2, -2, 164, 164), (28.5, 31.2), (27.0, 32.8)),
    100.0: (['disc', 'disc-stroke'], (-5, -5, 170, 170), (30.5, 33.2), (29.0, 34.8)),
}


@case
def stroke_positions():
    for position, (layers, want_rect, inside, outside) in STROKES.items():
        image, layer = disc_image()
        ok(run('stroke', image, layer, size=4, position=position))
        check(children(image) == layers, 'position %s: layers %s' % (position, children(image)))
        stroke = by_name(image, 'disc-stroke')
        check(rect(stroke) == want_rect, 'position %s: rect %s' % (position, rect(stroke)))
        check(stroke.get_mode() == Gimp.LayerMode.NORMAL, 'mode %s' % mode_nick(stroke))
        px = Pixels(stroke)
        lo, hi = inside
        stroked = band(px, lo, hi)
        check(min(stroked) > 0.9, 'position %s: no stroke between %s and %s: %.3f'
              % (position, lo, hi, min(stroked)))
        lo, hi = outside
        not_stroked = band(px, 0, lo) + band(px, hi, hi + 5)
        check(max(not_stroked) < 0.1, 'position %s: stroke inside %s or outside %s: %.3f'
              % (position, lo, hi, max(not_stroked)))
        for d in range(0, 360, 15):
            r, g, b, a = px(*at(inside[0], d))
            check(r > 0.99 and g < 0.01 and b < 0.01, 'not red: %s' % ((r, g, b),))


@case
def stroke_gradient_and_pattern():
    image, layer = disc_image()
    ok(run('stroke', image, layer, size=4, position=100.0))
    want = Pixels(by_name(image, 'disc-stroke'))
    Gimp.context_set_foreground(color('black'))
    Gimp.context_set_background(color('white'))
    for fill, args in (('gradient', dict(gradient=Gimp.Gradient.get_by_name('FG to BG (RGB)'),
                                         center_x=50.0, center_y=80.0, width=60.0, angle=0.0)),
                       ('pattern', dict(pattern=Gimp.Pattern.get_by_name('Pine'))),
                       ('pattern', dict(pattern=Gimp.Pattern.get_by_name('Pine'), scale=250.0,
                                        interpolation='linear')),
                       ('gradient', dict(gradient=Gimp.Gradient.get_by_name('FG to BG (RGB)'),
                                         gradient_type='shaped-spherical', center_x=80.0,
                                         center_y=80.0, width=40.0))):
        image, layer = disc_image()
        ok(run('stroke', image, layer, size=4, position=100.0, fill_type=fill, **args))
        px = Pixels(by_name(image, 'disc-stroke'))
        check(rect(px.layer) == rect(want.layer), '%s: rect %s' % (fill, rect(px.layer)))
        worst = max(abs(px.alpha(*at(r, d)) - want.alpha(*at(r, d)))
                    for r in (29, 31, 32, 34) for d in range(0, 360, 10))
        check(worst < 0.02, '%s %s: alpha differs from the colour stroke by %.3f'
              % (fill, args, worst))
        colors = [sum(px(*at(32, d))[:3]) for d in range(0, 360, 10)]
        check(std(colors) > 0.01, '%s: the stroke is one colour' % fill)


def alpha_matches_layer(px, layer, what):
    src = Pixels(layer)
    worst = max(abs(px.alpha(x, y) - src.alpha(x, y)) for x in range(40, 120, 3)
                for y in range(40, 120, 3))
    check(worst < 0.01, '%s: alpha differs from the layer by %.3f' % (what, worst))


@case
def color_overlay():
    image, layer = disc_image()
    ok(run('color-overlay', image, layer, color='#ff8000', opacity=80.0, mode='multiply'))
    check(children(image) == ['disc-color', 'disc'], 'layers %s' % children(image))
    ov = by_name(image, 'disc-color')
    check(rect(ov) == rect(layer), 'rect %s' % (rect(ov),))
    check(ov.get_mode() == Gimp.LayerMode.MULTIPLY, 'mode %s' % mode_nick(ov))
    approx(ov.get_opacity(), 80.0, 1e-6, 'opacity')
    px = Pixels(ov)
    alpha_matches_layer(px, layer, 'color overlay')
    r, g, b, a = px(CX, CY)
    check(r > 0.99 and 0.2 < g < 0.25 and b < 0.01, 'colour %s' % ((r, g, b),))


@case
def gradient_overlay():
    image, layer = disc_image()
    Gimp.context_set_foreground(color('black'))
    Gimp.context_set_background(color('white'))
    ok(run('gradient-overlay', image, layer, gradient=Gimp.Gradient.get_by_name('FG to BG (RGB)'),
           center_x=80.0, center_y=80.0, angle=0.0, width=60.0))
    check(children(image) == ['disc-gradient', 'disc'], 'layers %s' % children(image))
    px = Pixels(by_name(image, 'disc-gradient'))
    alpha_matches_layer(px, layer, 'gradient overlay')
    left, mid, right = px(CX - 25, CY)[0], px(CX, CY)[0], px(CX + 25, CY)[0]
    check(left < mid < right, 'not a gradient from left to right: %.3f %.3f %.3f'
          % (left, mid, right))


@case
def pattern_overlay():
    image, layer = disc_image()
    ok(run('pattern-overlay', image, layer, pattern=Gimp.Pattern.get_by_name('Pine')))
    check(children(image) == ['disc-pattern', 'disc'], 'layers %s' % children(image))
    ov = by_name(image, 'disc-pattern')
    check(rect(ov) == rect(layer), 'rect %s' % (rect(ov),))
    px = Pixels(ov)
    alpha_matches_layer(px, layer, 'pattern overlay')
    check(std([px(x, CY)[1] for x in range(55, 105)]) > 0.01, 'no pattern')
    # scaled
    image, layer = disc_image()
    ok(run('pattern-overlay', image, layer, pattern=Gimp.Pattern.get_by_name('Pine'),
           scale=300.0, interpolation='cubic'))
    ov = by_name(image, 'disc-pattern')
    check(rect(ov) == rect(layer), 'scaled: rect %s' % (rect(ov),))
    alpha_matches_layer(Pixels(ov), layer, 'scaled pattern overlay')
