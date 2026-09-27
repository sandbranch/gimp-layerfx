# The ramps of the effects against the original's way of making them:
# the selection grown (or shrunk) by one pixel less for each step and
# filled with the next shade (draw_blurshape () of layerfx.2.8.py),
# here with GIMP 3's own Grow and Shrink. The plug-in computes the same
# ramps from a distance transform, in one go.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later


def reference_blurshape(image, drawable, size, initgrowth, sel, invert):
    """draw_blurshape () of the original, with the GIMP 3 API."""
    k = initgrowth
    for i in range(size):
        image.select_item(Gimp.ChannelOps.REPLACE, sel)
        if k > 0:
            Gimp.Selection.grow(image, k)
        elif k < 0:
            Gimp.Selection.shrink(image, -k)
        if invert:
            shade = float(size - (i + 1)) / float(size)
        else:
            shade = float(i + 1) / float(size)
        c = Gegl.Color.new('black')
        c.set_rgba(shade, shade, shade, 1.0)
        Gimp.context_set_foreground(c)
        if not Gimp.Selection.is_empty(image):
            drawable.edit_fill(Gimp.FillType.FOREGROUND)
        k -= 1
    Gimp.Selection.none(image)


RAMP_SHAPES = [
    ('disc', lambda: disc(80, 80, 30, aa=True)),
    ('hard-disc', lambda: disc(80, 80, 30, aa=False)),
    ('box', lambda: box(50, 60, 110, 100)),
]
# (size, growth, inverted) as the effects use them
RAMP_SETTINGS = [
    ('drop-shadow-5', 5, 3, False),
    ('drop-shadow-10', 10, 5, False),
    ('outer-glow-10', 10, 10, False),
    ('inner-glow-10', 10, -1, True),
    ('inner-bevel-8', 8, 0, False),
    ('big-30', 30, 15, False),
]


def compare_ramp(shape_name, shape, size, growth, invert):
    image = Gimp.Image.new_with_precision(160, 160, Gimp.ImageBaseType.GRAY, FLOAT)
    layer = shape_layer(image, shape, color=(1.0, 1.0, 1.0))
    ref = Gimp.Layer.new(image, 'ref', 160, 160, Gimp.ImageType.GRAY_IMAGE, 100,
                         Gimp.LayerMode.NORMAL)
    image.insert_layer(ref, None, 0)
    put(ref, lambda x, y: ((1.0 if invert else 0.0),) * 3 + (1.0,))
    image.select_item(Gimp.ChannelOps.REPLACE, layer)
    sel = Gimp.Selection.save(image)
    Gimp.Selection.none(image)
    reference_blurshape(image, ref, size, growth, sel, invert)
    want = read(ref, 'Y float')
    s = LFX.Shape(layer)
    g = LFX.Graph()
    sigma = g.src(s.sigma((0, 0, 160, 160), 2 * size + 4))
    got_buf = g.render(LFX.ramp(g, sigma, size, growth, invert), (0, 0, 160, 160))
    raw = got_buf.get(Gegl.Rectangle.new(0, 0, 160, 160), 1.0, 'Y float', Gegl.AbyssPolicy.NONE)
    got = struct.unpack('%df' % (160 * 160), raw)
    diffs = [abs(got[y * 160 + x] - want[y][x][0]) for y in range(160) for x in range(160)]
    # only where either is not flat
    active = [d for i, d in enumerate(diffs)
              if 0.0 < got[i] < 1.0 or 0.0 < want[i // 160][i % 160][0] < 1.0]
    image.delete()
    mean = sum(active) / len(active)
    return mean * size, max(active) * size, len(active)


@case
def ramp_matches_original():
    worst_mean = worst_max = 0.0
    for shape_name, make in RAMP_SHAPES:
        for name, size, growth, invert in RAMP_SETTINGS:
            mean, mx, n = compare_ramp(shape_name, make(), size, growth, invert)
            print('LFX INFO ramp %s %s: mean %.3f max %.3f steps over %d pixels'
                  % (shape_name, name, mean, mx, n))
            worst_mean = max(worst_mean, mean)
            worst_max = max(worst_max, mx)
    # in steps of the ramp (1 / size): the original's ramp is a staircase
    # of whole steps, the plug-in's a straight line through its corners
    check(worst_mean <= 0.35, 'mean difference %.3f steps' % worst_mean)
    check(worst_max <= 1.5, 'largest difference %.3f steps' % worst_max)
