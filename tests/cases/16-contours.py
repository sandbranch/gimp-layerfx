# The contours: the plug-in computes the smooth curves of the original
# itself (as look-up tables, in floating point); they must be the curves
# that GIMP's Curves tool makes from the same points.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later


def gimp_curve(points):
    """GIMP's own curve through points (0..255), sampled at 0..255: Curves
    on a perceptual ramp, since Curves works on perceptual values."""
    image = Gimp.Image.new_with_precision(256, 1, Gimp.ImageBaseType.GRAY,
                                          Gimp.Precision.FLOAT_NON_LINEAR)
    layer = Gimp.Layer.new(image, 'ramp', 256, 1, Gimp.ImageType.GRAY_IMAGE, 100,
                           Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, None, 0)
    buf = layer.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, 256, 1), "Y' float",
            struct.pack('256f', *[i / 255.0 for i in range(256)]))
    buf.flush()
    layer.curves_spline(Gimp.HistogramChannel.VALUE, [p / 255.0 for p in points])
    raw = layer.get_buffer().get(Gegl.Rectangle.new(0, 0, 256, 1), 1.0, "Y' float",
                                 Gegl.AbyssPolicy.NONE)
    image.delete()
    return struct.unpack('256f', raw)


@case
def contours_match_gimp_curves():
    worst = 0.0
    for index, (kind, data) in enumerate(LFX.CONTOUR_DATA):
        if kind != LFX.CONTOUR_SPLINE:
            continue
        nick = LFX.CONTOURS[index + 1][0]
        mine = LFX.contour_samples(nick)
        gimp = gimp_curve(data)
        d = max(abs(a - b) for a, b in zip(mine, gimp))
        print('LFX INFO contour %s: largest difference to GIMP Curves %.5f' % (nick, d))
        worst = max(worst, d)
    check(worst < 0.002, 'the contours differ from GIMP Curves by %.4f' % worst)


@case
def contour_table_in_graph():
    # the look-up table in a GEGL graph maps like the samples
    g = LFX.Graph()
    ramp = Gegl.Buffer.new('Y float', 0, 0, 1001, 1)
    ramp.set(Gegl.Rectangle.new(0, 0, 1001, 1), 'Y float',
             struct.pack('1001f', *[i / 1000.0 for i in range(1001)]))
    samples = LFX.contour_samples('ring-double')
    out = g.render(g.lut(g.src(ramp), samples, (0, 0, 1001, 1)), (0, 0, 1001, 1))
    got = struct.unpack('1001f', out.get(Gegl.Rectangle.new(0, 0, 1001, 1), 1.0, 'Y float',
                                          Gegl.AbyssPolicy.NONE))
    worst = 0.0
    for i, v in enumerate(got):
        x = i / 1000.0 * 255
        j = min(int(x), 254)
        want = samples[j] + (samples[j + 1] - samples[j]) * (x - j)
        worst = max(worst, abs(v - want))
    check(worst < 0.002, 'the table maps with an error of %.4f' % worst)
