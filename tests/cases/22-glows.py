# Outer Glow and Inner Glow.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later


@case
def outer_glow_layers():
    image, layer = disc_image()
    ok(run('outer-glow', image, layer))
    check(structure(image) == [('disc-with-effects', ['disc', 'disc-outerglow']), 'background'],
          'layers %s' % structure(image))
    glow = by_name(image, 'disc-outerglow')
    # grown by round(5 * 1.2) = 6
    check(rect(glow) == (-6, -6, 172, 172), 'rect %s' % (rect(glow),))
    check(glow.get_mode() == Gimp.LayerMode.SCREEN, 'mode %s' % mode_nick(glow))
    approx(glow.get_opacity(), 75.0, 1e-6, 'opacity')


@case
def outer_glow_outside_only():
    image, layer = disc_image()
    before = visible(image)
    ok(run('outer-glow', image, layer, size=8))
    px = Pixels(by_name(image, 'disc-outerglow'))
    after = visible(image)
    for d in range(0, 360, 20):
        x, y = at(32, d)
        check(px.alpha(x, y) > 0.3, 'no glow at %d degrees: %.3f' % (d, px.alpha(x, y)))
        check(after(x, y)[0] > before(x, y)[0] + 0.05, 'the glow does not lighten the image')
        check(px.alpha(*at(40, d)) < 0.01, 'glow too far out at %d degrees' % d)
        # the disc is unchanged
        x, y = at(20, d)
        approx(after(x, y)[2], before(x, y)[2], 0.005, 'the disc at %d degrees' % d)


@case
def outer_glow_knockout():
    image = new_image()
    layer = shape_layer(image, lambda x, y: 0.5 * disc(CX, CY, 30)(x, y))
    ok(run('outer-glow', image, layer, knockout=True))
    px = Pixels(by_name(image, 'disc-outerglow'))
    check(px.alpha(CX, CY) < 0.01, 'alpha under the layer %.3f' % px.alpha(CX, CY))
    check(0.1 < px.alpha(CX + 32, CY) < 0.5, 'alpha outside %.3f' % px.alpha(CX + 32, CY))
    image = new_image()
    layer = shape_layer(image, lambda x, y: 0.5 * disc(CX, CY, 30)(x, y))
    ok(run('outer-glow', image, layer))
    px = Pixels(by_name(image, 'disc-outerglow'))
    approx(px.alpha(CX, CY), 0.5, 0.02, 'without knockout: alpha under the layer')


@case
def outer_glow_gradient():
    image, layer = disc_image()
    black = Gimp.Gradient.get_by_name('FG to BG (RGB)')
    Gimp.context_set_foreground(color('black'))
    Gimp.context_set_background(color('white'))
    ok(run('outer-glow', image, layer, size=10, fill_type='gradient', gradient=black))
    px = Pixels(by_name(image, 'disc-outerglow'))
    # the gradient runs from the edge (its start, black) outwards
    near, far = px(CX + 31, CY), px(CX + 38, CY)
    check(near[0] < far[0] - 0.2, 'colour near %.3f, far %.3f' % (near[0], far[0]))
    approx(near[3], 1.0, 0.01, 'alpha near')
    approx(px.alpha(CX + 42, CY), 0.0, 0.01, 'alpha beyond the glow')


@case
def inner_glow_layers():
    image, layer = disc_image()
    ok(run('inner-glow', image, layer))
    check(structure(image) == [('disc-with-effects', ['disc-innerglow', 'disc']), 'background'],
          'layers %s' % structure(image))
    glow = by_name(image, 'disc-innerglow')
    check(rect(glow) == rect(layer), 'rect %s' % (rect(glow),))
    check(glow.get_mode() == Gimp.LayerMode.SCREEN, 'mode %s' % mode_nick(glow))


@case
def inner_glow_inside_only():
    image, layer = disc_image()
    ok(run('inner-glow', image, layer, size=8))
    px = Pixels(by_name(image, 'disc-innerglow'))
    for d in range(0, 360, 20):
        check(px.alpha(*at(28.5, d)) > 0.5, 'no glow at %d degrees: %.3f'
              % (d, px.alpha(*at(28.5, d))))
        check(px.alpha(*at(31.5, d)) < 0.01, 'glow outside at %d degrees' % d)
    check(px.alpha(CX, CY) < 0.01, 'glow in the middle %.3f' % px.alpha(CX, CY))
    # from the centre instead
    image, layer = disc_image()
    ok(run('inner-glow', image, layer, size=20, source='center'))
    px = Pixels(by_name(image, 'disc-innerglow'))
    check(px.alpha(CX, CY) > 0.95, 'no glow in the middle %.3f' % px.alpha(CX, CY))
    check(px.alpha(CX + 29, CY) < 0.1, 'glow at the edge %.3f' % px.alpha(CX + 29, CY))


@case
def inner_glow_gradient():
    image, layer = disc_image()
    Gimp.context_set_foreground(color('black'))
    Gimp.context_set_background(color('white'))
    ok(run('inner-glow', image, layer, size=10, fill_type='gradient',
           gradient=Gimp.Gradient.get_by_name('FG to BG (RGB)')))
    px = Pixels(by_name(image, 'disc-innerglow'))
    edge, deeper = px(CX + 29, CY), px(CX + 23, CY)
    check(edge[0] < deeper[0] - 0.2, 'colour at the edge %.3f, deeper %.3f' % (edge[0], deeper[0]))
    approx(px.alpha(CX + 32, CY), 0.0, 0.01, 'alpha outside')
    approx(px.alpha(CX, CY), 0.0, 0.01, 'alpha in the middle')
