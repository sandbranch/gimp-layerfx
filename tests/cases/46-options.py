# Every blend mode, contour, gradient type, repeat and interpolation.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later


@case
def every_blend_mode():
    image, layer = disc_image(size=80, r=20)
    for nick, label, mode in LFX.MODES:
        ok(run('color-overlay', image, layer, mode=nick))
        overlay = by_name(image, 'disc-color')
        check(overlay.get_mode() == getattr(Gimp.LayerMode, mode),
              '%s: mode %s' % (nick, mode_nick(overlay)))
    check(len(by_name(image, 'disc-with-effects').get_children()) == 2, 'layers %s'
          % structure(image))


@case
def every_contour():
    image, layer = disc_image(size=100, r=25)
    for nick, label in LFX.CONTOURS:
        for effect, arg in (('drop-shadow', 'contour'), ('inner-glow', 'contour'),
                            ('satin', 'contour'), ('bevel-emboss', 'gloss-contour'),
                            ('bevel-emboss', 'surface-contour')):
            ok(run(effect, image, layer, **{arg.replace('-', '_'): nick, 'size': 10}))
        # the contour shapes the shadow: its alpha across the edge follows
        # the curve of the ramp
        ok(run('drop-shadow', image, layer, contour=nick, size=10, offset_distance=0.0))
        px = Pixels(by_name(image, 'disc-dropshadow'))
        samples = LFX.contour_samples(nick)
        # a point in the middle of the ramp (ramp value about 0.5)
        got = px.alpha(50 + 25, 50)
        want = samples[int(round(0.5 * 255))]
        approx(got, want, 0.2, '%s: alpha in the middle of the ramp' % nick)


@case
def every_gradient_type_and_repeat():
    Gimp.context_set_foreground(color('black'))
    Gimp.context_set_background(color('white'))
    gradient = Gimp.Gradient.get_by_name('FG to BG (RGB)')
    for nick, label, gtype in LFX.GRADIENT_TYPES:
        for repeat in ('none', 'sawtooth', 'triangular'):
            image, layer = disc_image()
            ok(run('gradient-overlay', image, layer, gradient=gradient, gradient_type=nick,
                   repeat=repeat, reverse=repeat == 'triangular', center_x=80.0, center_y=80.0,
                   width=30.0, angle=30.0))
            px = Pixels(by_name(image, 'disc-gradient'))
            src = Pixels(layer)
            worst = max(abs(px.alpha(x, y) - src.alpha(x, y)) for x in range(40, 120, 5)
                        for y in range(40, 120, 5))
            check(worst < 0.01, '%s %s: alpha differs from the layer by %.3f'
                  % (nick, repeat, worst))
            values = [px(x, y)[0] for x in range(55, 105, 3) for y in range(55, 105, 3)]
            check(std(values) > 0.01, '%s %s: one colour' % (nick, repeat))


@case
def every_interpolation():
    for nick, label, interp in LFX.INTERPOLATIONS:
        image, layer = disc_image()
        ok(run('pattern-overlay', image, layer, pattern=Gimp.Pattern.get_by_name('Pine'),
               scale=173.0, interpolation=nick))
        ov = by_name(image, 'disc-pattern')
        check(rect(ov) == rect(layer), '%s: rect %s' % (nick, rect(ov)))
