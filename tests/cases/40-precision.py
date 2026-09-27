# Every precision, RGB and grey, layers with offsets and with layer
# masks: the effects are the same, in image coordinates.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later

EFFECT_LAYERS = {
    'drop-shadow': ['disc-dropshadow'], 'inner-shadow': ['disc-innershadow'],
    'outer-glow': ['disc-outerglow'], 'inner-glow': ['disc-innerglow'],
    'bevel-emboss': ['disc-highlight', 'disc-shadow'], 'satin': ['disc-satin'],
    'stroke': ['disc-stroke'], 'color-overlay': ['disc-color'],
    'gradient-overlay': ['disc-gradient'], 'pattern-overlay': ['disc-pattern'],
}
PRECISIONS = [p for p in (
    'U8_LINEAR', 'U8_NON_LINEAR', 'U16_LINEAR', 'U16_NON_LINEAR', 'U32_LINEAR',
    'U32_NON_LINEAR', 'HALF_LINEAR', 'HALF_NON_LINEAR', 'FLOAT_LINEAR', 'FLOAT_NON_LINEAR',
    'DOUBLE_LINEAR', 'DOUBLE_NON_LINEAR')]
SAMPLES = [(x, y) for x in range(36, 125, 4) for y in range(36, 125, 4)]


def effect_alphas(make):
    """The alpha of every effect layer at the sample points, for images
    made by make ()."""
    out = {}
    for effect, names in EFFECT_LAYERS.items():
        image, layer = make()
        ok(run(effect, image, layer, pattern=Gimp.Pattern.get_by_name('Pine'))
           if effect == 'pattern-overlay' else run(effect, image, layer))
        for name in names:
            px = Pixels(by_name(image, name))
            out[name] = [px.alpha(x, y) for x, y in SAMPLES]
        image.delete()
    return out


def compare_alphas(got, want, tol, what):
    for name in want:
        worst = max(abs(a - b) for a, b in zip(got[name], want[name]))
        check(worst <= tol, '%s: %s differs by %.4f' % (what, name, worst))


REFERENCE = {}


def reference():
    if not REFERENCE:
        REFERENCE.update(effect_alphas(lambda: disc_image(precision=FLOAT)))
    return REFERENCE


@case
def every_precision_rgb_and_grey():
    want = reference()
    for p in PRECISIONS:
        precision = getattr(Gimp.Precision, p)
        for base in (Gimp.ImageBaseType.RGB, Gimp.ImageBaseType.GRAY):
            got = effect_alphas(lambda: disc_image(precision=precision, base=base))
            tol = 3 / 255.0 if p.startswith('U8') else 0.004
            compare_alphas(got, want, tol, '%s %s' % (p, base.value_nick))


@case
def layer_with_offset():
    want = reference()
    for offset, size in (((30, 30), (100, 100)), ((-20, -10), (150, 170)), ((47, 11), (90, 130))):
        got = effect_alphas(lambda: disc_image(precision=FLOAT, offset=offset, layer_size=size))
        compare_alphas(got, want, 0.004, 'offset %s size %s' % (offset, size))
    # the effect layers are placed relative to the layer
    image, layer = disc_image(offset=(30, 30), layer_size=(100, 100))
    ok(run('drop-shadow', image, layer))
    check(rect(by_name(image, 'disc-dropshadow')) == (30 + 3 - 4, 30 + 4 - 4, 108, 108),
          'drop shadow rect %s' % (rect(by_name(image, 'disc-dropshadow')),))
    ok(run('inner-glow', image, layer))
    check(rect(by_name(image, 'disc-innerglow')) == (30, 30, 100, 100), 'inner glow rect')


@case
def layer_with_mask():
    want = reference()

    def masked():
        image = new_image(precision=FLOAT)
        layer = shape_layer(image, lambda x, y: 1.0)
        mask = layer.create_mask(Gimp.AddMaskType.WHITE)
        layer.add_mask(mask)
        put(mask, lambda x, y: (disc(CX, CY, 30)(x, y),))
        return image, layer
    got = effect_alphas(masked)
    compare_alphas(got, want, 0.004, 'masked layer')
    # the mask stays on the layer
    image, layer = masked()
    ok(run('drop-shadow', image, layer))
    check(layer.get_mask() is not None, 'the mask is gone')
