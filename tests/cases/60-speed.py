# How long the effects take on a larger layer (printed; a generous limit
# catches only a gross slowdown).
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later


def big_shape(x, y):
    # a wide rounded bar and a ring, like large lettering
    if 100 <= x < 1100 and 150 <= y < 450:
        return 1.0
    return disc(600, 620, 150, aa=False)(x, y) * (1.0 - disc(600, 620, 90, aa=False)(x, y))


@case
def speed_on_a_large_layer():
    image = new_image(1200, 800, precision=U8)
    layer = shape_layer(image, big_shape)
    worst = 0.0
    for effect, args in (('drop-shadow', dict(size=30, offset_distance=20.0)),
                         ('outer-glow', dict(size=40, contour='ring')),
                         ('inner-glow', dict(size=20, noise=30.0)),
                         ('bevel-emboss', dict(size=20, soften=3)),
                         ('satin', {}), ('stroke', dict(size=8)),
                         ('color-overlay', {}), ('pattern-overlay',
                                                 dict(pattern=Gimp.Pattern.get_by_name('Pine')))):
        t = time.time()
        ok(run(effect, image, layer, **args))
        dt = time.time() - t
        worst = max(worst, dt)
        print('LFX INFO %s on 1200 x 800: %.1f s' % (effect, dt))
    t = time.time()
    ok(run('reapply-effects', image, layer))
    print('LFX INFO reapply-effects (8 effects) on 1200 x 800: %.1f s' % (time.time() - t))
    check(worst < 60.0, 'an effect took %.0f s' % worst)
