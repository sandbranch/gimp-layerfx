# Bevel and Emboss, and Satin.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later

BEVEL_RINGS = {'outer-bevel': (31, 35), 'inner-bevel': (25, 29), 'emboss': (28, 32),
               'pillow-emboss': (28, 32)}


@case
def bevel_layers():
    image, layer = disc_image()
    ok(run('bevel-emboss', image, layer))
    check(structure(image) == [('disc-with-effects', ['disc-highlight', 'disc-shadow', 'disc']),
                               'background'], 'layers %s' % structure(image))
    hl, sh = by_name(image, 'disc-highlight'), by_name(image, 'disc-shadow')
    check(hl.get_mode() == Gimp.LayerMode.SCREEN, 'highlight mode %s' % mode_nick(hl))
    check(sh.get_mode() == Gimp.LayerMode.MULTIPLY, 'shadow mode %s' % mode_nick(sh))
    approx(hl.get_opacity(), 75.0, 1e-6, 'highlight opacity')
    approx(sh.get_opacity(), 75.0, 1e-6, 'shadow opacity')
    check(rect(hl) == rect(sh) == (-6, -6, 172, 172), 'rects %s %s' % (rect(hl), rect(sh)))
    check(info(hl)['role'] == 'highlight' and info(sh)['role'] == 'shadow', 'roles')


@case
def bevel_light_sides():
    for style, (r0, r1) in BEVEL_RINGS.items():
        for direction in ('up', 'down'):
            image, layer = disc_image()
            ok(run('bevel-emboss', image, layer, style=style, direction=direction, size=5,
                   depth=5))
            hl = Pixels(by_name(image, 'disc-highlight'))
            sh = Pixels(by_name(image, 'disc-shadow'))
            # light from 120 degrees (upper left)
            h_lit, h_dark = arc_mean(hl, r0, r1, 100, 140), arc_mean(hl, r0, r1, 280, 320)
            s_lit, s_dark = arc_mean(sh, r0, r1, 100, 140), arc_mean(sh, r0, r1, 280, 320)
            if direction == 'down':
                h_lit, h_dark, s_lit, s_dark = h_dark, h_lit, s_dark, s_lit
            what = '%s %s: highlight %.3f / %.3f, shadow %.3f / %.3f' % (
                style, direction, h_lit, h_dark, s_lit, s_dark)
            check(h_lit > h_dark + 0.1 and s_dark > s_lit + 0.1, what)
            # flat in the middle and far outside
            check(hl.alpha(CX, CY) < 0.02 and sh.alpha(CX, CY) < 0.02, what + ' (middle)')


@case
def bevel_options():
    # soften, contours and a texture all make a bevel
    image, layer = disc_image()
    ok(run('bevel-emboss', image, layer, soften=4, gloss_contour='ring',
           surface_contour='half-round', use_texture=True, scale=50.0, tex_depth=300.0,
           invert=True, pattern=Gimp.Pattern.get_by_name('Pine')))
    hl = Pixels(by_name(image, 'disc-highlight'))
    check(max(hl.alpha(*at(33, d)) for d in range(0, 360, 5)) > 0.05, 'no highlight')


@case
def satin_layers():
    image, layer = disc_image()
    ok(run('satin', image, layer))
    check(structure(image) == [('disc-with-effects', ['disc-satin', 'disc']), 'background'],
          'layers %s' % structure(image))
    satin = by_name(image, 'disc-satin')
    check(rect(satin) == rect(layer), 'rect %s' % (rect(satin),))
    check(satin.get_mode() == Gimp.LayerMode.MULTIPLY, 'mode %s' % mode_nick(satin))


@case
def satin_present():
    image, layer = disc_image()
    ok(run('satin', image, layer))
    px = Pixels(by_name(image, 'disc-satin'))
    inside = [px.alpha(*at(r, d)) for r in range(0, 29, 3) for d in range(0, 360, 30)]
    check(max(inside) > 0.3, 'no satin: %.3f' % max(inside))
    check(std(inside) > 0.02, 'the satin is flat: %.3f' % std(inside))
    for d in range(0, 360, 30):
        check(px.alpha(*at(31.5, d)) < 0.01, 'satin outside at %d degrees' % d)
    # without inverting, the satin is dark where the offset copies differ
    image, layer = disc_image()
    ok(run('satin', image, layer, invert=False, contour='linear'))
    px = Pixels(by_name(image, 'disc-satin'))
    check(px.alpha(CX, CY) < 0.05, 'satin in the middle without invert: %.3f' % px.alpha(CX, CY))
