#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# GIMP Layer Effects
# Copyright (c) 2008 Jonathan Stipe
# JonStipe@prodigy.net
#
# Copyright 2026 David, port to GIMP 3
#
# ---------------------------------------------------------------------
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""GIMP Layer Effects for GIMP 3.

A port of layerfx.2.8.py (Jonathan Stipe, 2008 to 2012) to GIMP 3 and
Python 3. Each effect is built as its own layer (or two, for Bevel and
Emboss) with its own blend mode and opacity, in a pass-through layer
group with the layer it belongs to, so that every effect blends with the
image below. The settings of each effect are stored on its layer as a
parasite, so that Reapply Effects can rebuild them after the layer has
changed.

The original built its masks with GIMP's selection tools, growing or
shrinking the selection one pixel at a time for each step of a ramp.
This port computes the same ramps from a Euclidean distance transform
of the layer's alpha (gegl:distance-transform) in GEGL graphs inside
the plug-in, in floating point, and writes only the finished effect
layers to the image. Contours are look-up tables made from the
original curves. gegl:bump-map, gegl:noise-hsv and gegl:gaussian-blur
replace plug-in-bump-map, plug-in-hsv-noise and plug-in-gauss-rle.
"""

import array
import itertools
import json
import math
import random
import struct
import sys
import traceback

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('Gegl', '0.4')
from gi.repository import Gimp, Gegl, GObject, GLib

PLUG_IN_BINARY = 'layerfx'
PREFIX = 'python-layerfx-'
PARASITE_EFFECT = 'layerfx-effect'
PARASITE_GROUP = 'layerfx-group'
PARASITE_VERSION = 1
PARASITE_FLAGS = Gimp.PARASITE_PERSISTENT | Gimp.PARASITE_UNDOABLE

AUTHOR = 'Jonathan Stipe'
COPYRIGHT = 'Jonathan Stipe; GIMP 3 port 2026 David'
DATE = '2008, 2012, 2026'
IMAGE_MENU = '<Image>/Layer/La_yer Effects'
LAYERS_MENU = '<Layers>/_Layer Effects'


class LayerFXError(Exception):
    """An error for the user: shown as a message, never as a traceback."""


def rnd(x):
    """Rounds half away from zero, as Python 2's round() did."""
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


# ------------------------------------------------------------ the tables

# The blend modes of the original, in its order; GIMP 3's (non-legacy)
# modes of the same names.
MODES = [
    ('normal', 'Normal', 'NORMAL'),
    ('dissolve', 'Dissolve', 'DISSOLVE'),
    ('multiply', 'Multiply', 'MULTIPLY'),
    ('divide', 'Divide', 'DIVIDE'),
    ('screen', 'Screen', 'SCREEN'),
    ('overlay', 'Overlay', 'OVERLAY'),
    ('dodge', 'Dodge', 'DODGE'),
    ('burn', 'Burn', 'BURN'),
    ('hard-light', 'Hard Light', 'HARDLIGHT'),
    ('soft-light', 'Soft Light', 'SOFTLIGHT'),
    ('grain-extract', 'Grain Extract', 'GRAIN_EXTRACT'),
    ('grain-merge', 'Grain Merge', 'GRAIN_MERGE'),
    ('difference', 'Difference', 'DIFFERENCE'),
    ('addition', 'Addition', 'ADDITION'),
    ('subtract', 'Subtract', 'SUBTRACT'),
    ('darken-only', 'Darken Only', 'DARKEN_ONLY'),
    ('lighten-only', 'Lighten Only', 'LIGHTEN_ONLY'),
    ('hue', 'Hue', 'HSV_HUE'),
    ('saturation', 'Saturation', 'HSV_SATURATION'),
    ('color', 'Color', 'HSL_COLOR'),
    ('value', 'Value', 'HSV_VALUE'),
]

CONTOURS = [
    ('linear', 'Linear'),
    ('cone', 'Cone'),
    ('cone-inverted', 'Cone (Inverted)'),
    ('cove-deep', 'Cove (Deep)'),
    ('cove-shallow', 'Cove (Shallow)'),
    ('gaussian', 'Gaussian'),
    ('half-round', 'Half Round'),
    ('ring', 'Ring'),
    ('ring-double', 'Ring (Double)'),
    ('rolling-slope-descending', 'Rolling Slope (Descending)'),
    ('rounded-steps', 'Rounded Steps'),
    ('sawtooth-1', 'Sawtooth 1'),
]

# The curves of the contours, from the original: control points (x, y,
# x, y, ...) of a smooth curve, or 256 explicit values.
CONTOUR_SPLINE, CONTOUR_EXPLICIT = 0, 1
CONTOUR_DATA = [
    (CONTOUR_SPLINE, (0, 0, 127, 255, 255, 0)),
    (CONTOUR_SPLINE, (0, 255, 127, 0, 255, 255)),
    (CONTOUR_SPLINE, (0, 64, 94, 74, 150, 115, 179, 179, 191, 255)),
    (CONTOUR_SPLINE, (0, 0, 5, 125, 6, 125, 48, 148, 79, 179, 107, 217, 130, 255)),
    (CONTOUR_SPLINE, (0, 0, 33, 8, 64, 38, 97, 102, 128, 166, 158, 209, 191, 235, 222, 247, 255, 255)),
    (CONTOUR_SPLINE, (0, 0, 28, 71, 87, 166, 194, 240, 255, 255)),
    (CONTOUR_SPLINE, (0, 0, 33, 110, 64, 237, 97, 240, 128, 138, 158, 33, 191, 5, 222, 99, 255, 255)),
    (CONTOUR_SPLINE, (0, 0, 33, 74, 64, 219, 97, 186, 128, 0, 158, 176, 191, 201, 222, 3, 255, 255)),
    (CONTOUR_SPLINE, (3, 255, 54, 99, 97, 107, 179, 153, 252, 0)),
    (CONTOUR_EXPLICIT, (
        0, 5, 9, 13, 16, 19, 22, 25, 27, 29, 30, 32, 33, 34, 35, 36, 38, 39, 40, 41, 43, 44, 46, 47,
        48, 49, 50, 51, 52, 53, 54, 55, 55, 56, 56, 57, 57, 58, 58, 59, 59, 59, 60, 60, 60, 61, 61,
        61, 61, 62, 62, 62, 62, 62, 63, 63, 63, 63, 63, 63, 64, 64, 64, 64, 64, 71, 75, 78, 81, 84,
        86, 89, 91, 93, 95, 96, 98, 99, 101, 102, 103, 104, 105, 107, 107, 108, 110, 111, 112, 113,
        114, 115, 116, 117, 118, 119, 119, 120, 121, 121, 122, 123, 123, 123, 124, 124, 124, 125,
        125, 125, 125, 125, 125, 125, 126, 126, 126, 126, 126, 126, 126, 125, 125, 125, 125, 125,
        125, 125, 125, 130, 134, 137, 141, 145, 148, 151, 153, 156, 158, 160, 162, 163, 165, 166,
        167, 168, 170, 171, 171, 172, 173, 174, 175, 176, 177, 178, 178, 179, 180, 181, 181, 182,
        183, 183, 184, 184, 185, 185, 186, 186, 187, 187, 188, 188, 189, 189, 189, 189, 190, 190,
        190, 190, 191, 191, 191, 191, 191, 191, 191, 191, 191, 191, 193, 194, 196, 197, 198, 200,
        201, 203, 204, 205, 207, 208, 209, 211, 212, 213, 214, 215, 217, 218, 219, 220, 220, 221,
        222, 222, 223, 223, 224, 224, 224, 224, 224, 223, 223, 222, 222, 221, 221, 220, 219, 218,
        217, 216, 215, 214, 213, 212, 211, 210, 209, 208, 206, 205, 204, 203, 202, 200, 199, 198,
        197, 196, 194, 194)),
    (CONTOUR_EXPLICIT, (
        0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46,
        48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82, 84, 86, 88, 90, 92,
        94, 96, 98, 100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122, 124, 126, 127, 125,
        123, 121, 119, 117, 115, 113, 111, 109, 107, 105, 103, 101, 99, 97, 95, 93, 91, 89, 87, 85,
        83, 81, 79, 77, 75, 73, 71, 69, 67, 65, 63, 61, 59, 57, 55, 53, 51, 49, 47, 45, 43, 41, 39,
        37, 35, 33, 31, 29, 27, 25, 23, 21, 19, 17, 15, 13, 11, 9, 7, 5, 3, 1, 1, 3, 5, 7, 9, 11,
        13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45, 47, 49, 51, 53, 55, 57,
        59, 61, 63, 65, 67, 69, 71, 73, 75, 77, 79, 81, 83, 85, 87, 89, 91, 93, 95, 97, 99, 101,
        103, 105, 107, 109, 111, 113, 115, 117, 119, 121, 123, 125, 127, 128, 126, 124, 122, 120,
        118, 116, 114, 112, 110, 108, 106, 104, 102, 100, 98, 96, 94, 92, 90, 88, 86, 84, 82, 80,
        78, 76, 74, 72, 70, 68, 66, 64, 62, 60, 58, 56, 54, 52, 50, 48, 46, 44, 42, 40, 38, 36, 34,
        32, 30, 28, 26, 24, 22, 20, 18, 16, 14, 12, 10, 8, 6, 4, 2)),
]

GRADIENT_TYPES = [
    ('linear', 'Linear', 'LINEAR'),
    ('bilinear', 'Bi-linear', 'BILINEAR'),
    ('radial', 'Radial', 'RADIAL'),
    ('square', 'Square', 'SQUARE'),
    ('conical-symmetric', 'Conical (symmetric)', 'CONICAL_SYMMETRIC'),
    ('conical-asymmetric', 'Conical (asymmetric)', 'CONICAL_ASYMMETRIC'),
    ('shaped-angular', 'Shaped (angular)', 'SHAPEBURST_ANGULAR'),
    ('shaped-spherical', 'Shaped (spherical)', 'SHAPEBURST_SPHERICAL'),
    ('shaped-dimpled', 'Shaped (dimpled)', 'SHAPEBURST_DIMPLED'),
    ('spiral-clockwise', 'Spiral (clockwise)', 'SPIRAL_CLOCKWISE'),
    ('spiral-anticlockwise', 'Spiral (counter-clockwise)', 'SPIRAL_ANTICLOCKWISE'),
]

REPEATS = [
    ('none', 'None', 'NONE'),
    ('sawtooth', 'Sawtooth Wave', 'SAWTOOTH'),
    ('triangular', 'Triangular Wave', 'TRIANGULAR'),
]

# The original offered None, Linear, Cubic and Sinc (Lanczos3); GIMP 3
# replaced Lanczos with NoHalo (GIMP 2.10 did so already).
INTERPOLATIONS = [
    ('none', 'None', 'NONE'),
    ('linear', 'Linear', 'LINEAR'),
    ('cubic', 'Cubic', 'CUBIC'),
    ('nohalo', 'NoHalo', 'NOHALO'),
]

SOURCES = [('center', 'Cent_er'), ('edge', 'Ed_ge')]
DIRECTIONS = [('up', 'Up'), ('down', 'Down')]
STYLES = [
    ('outer-bevel', 'Outer Bevel'),
    ('inner-bevel', 'Inner Bevel'),
    ('emboss', 'Emboss'),
    ('pillow-emboss', 'Pillow Emboss'),
]
GLOW_FILLS = [('color', 'Color'), ('gradient', 'Gradient')]
STROKE_FILLS = [('color', 'Color'), ('gradient', 'Gradient'), ('pattern', 'Pattern')]


def nick_index(table, nick):
    for i, entry in enumerate(table):
        if entry[0] == nick:
            return i
    raise LayerFXError('Unknown value "%s"' % nick)


def layer_mode(nick):
    return getattr(Gimp.LayerMode, MODES[nick_index(MODES, nick)][2])


def enum_value(table, enum, nick):
    return getattr(enum, table[nick_index(table, nick)][2])


# ------------------------------------------------------------ the curves

def spline_samples(points, n_samples=256):
    """The samples of GIMP's smooth curve through the control points (in
    0..255), as GIMP 2.8's gimp_curve_calculate () computed them: cubic
    Bezier segments whose inner control points follow the neighbours."""
    pts = [(points[i] / 255.0, points[i + 1] / 255.0) for i in range(0, len(points), 2)]
    samples = [0.0] * n_samples
    last = n_samples - 1
    for i in range(rnd(pts[0][0] * last)):
        samples[i] = pts[0][1]
    for i in range(rnd(pts[-1][0] * last), n_samples):
        samples[i] = pts[-1][1]
    for i in range(len(pts) - 1):
        p1 = pts[max(i - 1, 0)]
        p2 = pts[i]
        p3 = pts[i + 1]
        p4 = pts[min(i + 2, len(pts) - 1)]
        x0, y0 = p2
        x3, y3 = p3
        dx, dy = x3 - x0, y3 - y0
        if dx <= 0:
            continue
        if i == 0 and i + 2 > len(pts) - 1:
            y1 = y0 + dy / 3.0
            y2 = y0 + dy * 2.0 / 3.0
        elif i == 0:
            slope = (p4[1] - y0) / (p4[0] - x0)
            y2 = y3 - slope * dx / 3.0
            y1 = y0 + (y2 - y0) / 2.0
        elif i + 2 > len(pts) - 1:
            slope = (y3 - p1[1]) / (x3 - p1[0])
            y1 = y0 + slope * dx / 3.0
            y2 = y3 + (y1 - y3) / 2.0
        else:
            slope = (y3 - p1[1]) / (x3 - p1[0])
            y1 = y0 + slope * dx / 3.0
            slope = (p4[1] - y0) / (p4[0] - x0)
            y2 = y3 - slope * dx / 3.0
        for j in range(rnd(dx * last) + 1):
            t = j / dx / last
            y = (y0 * (1 - t) ** 3 + 3 * y1 * (1 - t) ** 2 * t +
                 3 * y2 * (1 - t) * t * t + y3 * t ** 3)
            index = j + rnd(x0 * last)
            if index < n_samples:
                samples[index] = min(max(y, 0.0), 1.0)
    for x, y in pts:
        samples[rnd(x * last)] = y
    return samples


_contour_cache = {}


def contour_samples(nick):
    """256 samples of a contour curve (index 0, Linear, is the identity)."""
    index = nick_index(CONTOURS, nick)
    if index not in _contour_cache:
        if index == 0:
            samples = [i / 255.0 for i in range(256)]
        else:
            kind, data = CONTOUR_DATA[index - 1]
            if kind == CONTOUR_SPLINE:
                samples = spline_samples(data)
            else:
                samples = [v / 255.0 for v in data]
        _contour_cache[index] = samples
    return _contour_cache[index]


def brightness_contrast_samples(contrast):
    """GIMP 2's brightness-contrast curve for a contrast in -1..1 (the
    brightness is 0 here), as 256 samples."""
    out = []
    for i in range(256):
        value = i / 255.0
        nvalue = 1.0 - value if value > 0.5 else value
        nvalue = max(nvalue, 0.0)
        if contrast < 0:
            nvalue = 0.5 * math.pow(nvalue * 2.0, 1.0 + contrast)
        else:
            power = 127.0 if contrast == 1.0 else 1.0 / (1.0 - contrast)
            nvalue = 0.5 * math.pow(2.0 * nvalue, power)
        out.append(1.0 - nvalue if value > 0.5 else nvalue)
    return out


# ------------------------------------------------------------ GEGL graphs

_enum_cache = {}


def gegl_enum(op, prop, nick):
    """The value of an enum property of a GEGL operation, by its nick."""
    key = (op, prop, nick)
    if key not in _enum_cache:
        spec = [p for p in Gegl.Operation.list_properties(op) if p.name == prop][0]
        for member in spec.enum_class.__enum_values__.values():
            if member.value_nick == nick:
                _enum_cache[key] = member
                break
        else:
            raise KeyError('%s %s %s' % key)
    return _enum_cache[key]


def rect_grow(rect, n):
    x, y, w, h = rect
    return (x - n, y - n, w + 2 * n, h + 2 * n)


def cast_buffer(buf, rect, from_format, to_format):
    """A copy of the pixels of buf over rect, read in from_format and
    stored unchanged as to_format (like gegl:cast-format)."""
    r = Gegl.Rectangle.new(*rect)
    out = Gegl.Buffer.new(to_format, *rect)
    out.set(r, to_format, buf.get(r, 1.0, from_format, Gegl.AbyssPolicy.NONE))
    return out


def moved_buffer(buf, rect, from_format, to_format, to_rect=None):
    """The pixels of buf over rect in a new buffer at to_rect (of the same
    size; at (0, 0) by default), read in from_format and stored unchanged
    as to_format."""
    x, y, w, h = rect
    to_rect = to_rect or (0, 0, w, h)
    out = Gegl.Buffer.new(to_format, *to_rect)
    out.set(Gegl.Rectangle.new(*to_rect), to_format,
            buf.get(Gegl.Rectangle.new(*rect), 1.0, from_format, Gegl.AbyssPolicy.NONE))
    return out


class Graph:
    """A GEGL graph inside the plug-in. Single-channel images ("masks")
    are carried as RGBA float with R = G = B = the value and alpha 1;
    their values are plain numbers, as the 8-bit mask values of the
    original were."""

    def __init__(self):
        self.root = Gegl.Node()

    def op(self, name, input=None, aux=None, **props):
        node = self.root.create_child(name)
        for key, value in props.items():
            key = key.replace('_', '-')
            if isinstance(value, str) and key != 'string':
                value = gegl_enum(name, key, value)
            node.set_property(key, value)
        if input is not None:
            input.connect_to('output', node, 'input')
        if aux is not None:
            aux.connect_to('output', node, 'aux')
        return node

    def src(self, buf, dx=0, dy=0):
        node = self.op('gegl:buffer-source', buffer=buf)
        if dx or dy:
            node = self.op('gegl:translate', node, x=float(dx), y=float(dy),
                           sampler='nearest')
        return node

    def translate(self, node, dx, dy):
        if not dx and not dy:
            return node
        return self.op('gegl:translate', node, x=float(dx), y=float(dy), sampler='nearest')

    def crop(self, node, rect):
        x, y, w, h = rect
        return self.op('gegl:crop', node, x=float(x), y=float(y),
                       width=float(w), height=float(h))

    def color(self, color, rect):
        return self.crop(self.op('gegl:color', value=color), rect)

    def const(self, value, rect):
        color = Gegl.Color.new('black')
        color.set_rgba(value, value, value, 1.0)
        return self.color(color, rect)

    def region(self, node, rect):
        """node over the whole of rect, 0 where it has no pixels."""
        return self.op('gegl:add', self.const(0.0, rect), node)

    def lin(self, node, scale, offset=0.0):
        """scale * node + offset"""
        if scale != 1.0:
            node = self.op('gegl:multiply', node, value=float(scale))
        if offset != 0.0:
            node = self.op('gegl:add', node, value=float(offset))
        return node

    def clamp(self, node):
        return self.op('gegl:rgb-clip', node, clip_low=True, low_limit=0.0,
                       clip_high=True, high_limit=1.0)

    def mul(self, a, b):
        if isinstance(b, (int, float)):
            return self.lin(a, b)
        return self.op('gegl:multiply', a, b)

    def add(self, a, b):
        return self.op('gegl:add', a, b)

    def sub(self, a, b):
        return self.op('gegl:subtract', a, b)

    def inv(self, node):
        """1 - node"""
        return self.lin(node, -1.0, 1.0)

    def mix(self, a, b, t):
        """a + t * (b - a)"""
        return self.add(a, self.mul(self.sub(b, a), t))

    def lut(self, node, samples, rect):
        """Maps the values of node (0..1) over rect through the curve given
        by its samples (interpolated linearly), in floating point."""
        n = len(samples) - 1
        table = []
        for i in range(LUT_SIZE):
            x = i * n / (LUT_SIZE - 1)
            j = min(int(x), n - 1)
            f = x - j
            table.append(samples[j] * (1 - f) + samples[j + 1] * f)
        return self.src(lut_buffer(self.render(self.clamp(node), rect), rect, table, 1))

    def render(self, node, rect, fmt='Y float'):
        out = Gegl.Buffer.new(fmt, *rect)
        sink = self.op('gegl:write-buffer', self.crop(node, rect), buffer=out)
        sink.process()
        return out


LUT_SIZE = 4096
LUT_STRIP = 64


def lut_buffer(buf, rect, table, channels):
    """A new buffer: the values of buf (a "Y float" buffer with values in
    0..1) over rect looked up in table, which has LUT_SIZE entries of
    channels values each ("Y float" or "RGBA float"). GEGL's samplers
    cannot be used for this: they read from smaller mipmap levels where
    the coordinates change quickly."""
    x, y, w, h = rect
    fmt = 'Y float' if channels == 1 else 'RGBA float'
    out = Gegl.Buffer.new(fmt, *rect)
    top = LUT_SIZE - 1
    for y0 in range(y, y + h, LUT_STRIP):
        strip = Gegl.Rectangle.new(x, y0, w, min(LUT_STRIP, y + h - y0))
        values = array.array('f', buf.get(strip, 1.0, 'Y float', Gegl.AbyssPolicy.NONE))
        if channels == 1:
            mapped = array.array('f', [table[int(v * top + 0.5)] for v in values])
        else:
            mapped = array.array('f', itertools.chain.from_iterable(
                [table[int(v * top + 0.5)] for v in values]))
        out.set(strip, fmt, mapped.tobytes())
    return out


def write_layer(graph, layer, node):
    """Writes node (in image coordinates) into layer."""
    ok, lx, ly = layer.get_offsets()
    w, h = layer.get_width(), layer.get_height()
    local = graph.crop(graph.translate(node, -lx, -ly), (0, 0, w, h))
    shadow = layer.get_shadow_buffer()
    sink = graph.op('gegl:write-buffer', local, buffer=shadow)
    sink.process()
    shadow.flush()
    layer.merge_shadow(True)
    layer.update(0, 0, w, h)


def layer_rect(layer):
    ok, x, y = layer.get_offsets()
    return (x, y, layer.get_width(), layer.get_height())


# ------------------------------------------------------------ the shape

# The signed distance (sigma) of a pixel to the edge of the shape is in
# steps of GIMP's Grow and Shrink: a pixel is in the selection grown by k
# pixels (shrunk, for k < 0) where sigma <= k. It is the distance to the
# shape outside it, minus the distance to the outside inside it, plus the
# alpha; measured against GIMP 3.2's Grow and Shrink on discs and
# rectangles (tests/cases/15-ramp.py). Averaging over thresholds makes
# the distances of antialiased edges exact to a fraction of a pixel.
SIGMA_AVERAGING = 4


class Shape:
    """The shape of a layer: its alpha times its layer mask, in image
    coordinates, and its signed distance transform.

    The distances are those of the alpha divided by its maximum nearby
    (norm): an opaque layer is unchanged, a layer at 50 % has the edges of
    an opaque one. Its alpha level near a pixel (the density) scales the
    effects that reach out of the layer, as the partly selected fills of
    the original did."""

    def __init__(self, layer):
        self.layer = layer
        self.rect = layer_rect(layer)
        x, y, w, h = self.rect
        g = Graph()
        alpha = g.op('gegl:component-extract', g.src(layer.get_buffer()),
                     component='alpha', linear=True)
        mask = layer.get_mask()
        if mask is not None and layer.get_apply_mask():
            alpha = g.mul(alpha, g.src(mask.get_buffer()))
        self.alpha = g.render(g.translate(alpha, x, y), self.rect)
        g = Graph()
        a = g.region(g.src(self.alpha), rect_grow(self.rect, 3))
        top = g.op('gegl:median-blur', a, radius=2, percentile=100.0, neighborhood='circle',
                   abyss_policy='none', high_precision=True)
        self.norm = g.render(g.clamp(g.op('gegl:divide', a, top)), self.rect)
        whole = Gegl.Rectangle.new(*self.rect)
        self.opaque = (self.alpha.get(whole, 1.0, 'Y float', Gegl.AbyssPolicy.NONE) ==
                       self.norm.get(whole, 1.0, 'Y float', Gegl.AbyssPolicy.NONE))

    def alpha_node(self, g, dx=0, dy=0):
        return g.translate(g.src(self.alpha), dx, dy)

    def knockout_node(self, g, rect):
        """1 where the layer does not cover, 0 where it does (also where
        it is only partly opaque), soft at its edges."""
        return g.inv(g.region(g.src(self.norm), rect))

    def sigma(self, rect, margin, dx=0, dy=0):
        """The signed distance over rect, of the shape moved by (dx, dy);
        exact up to margin pixels from the edge, saturated beyond."""
        g = Graph()
        big = rect_grow(rect, int(margin) + 2)
        a = g.region(g.translate(g.src(self.norm), dx, dy), big)
        d_in = g.op('gegl:distance-transform', a, metric='euclidean',
                    edge_handling='below', threshold_lo=0.0001, threshold_hi=1.0,
                    averaging=SIGMA_AVERAGING, normalize=False)
        d_out = g.op('gegl:distance-transform', g.inv(a), metric='euclidean',
                     edge_handling='above', threshold_lo=0.0001, threshold_hi=1.0,
                     averaging=SIGMA_AVERAGING, normalize=False)
        return g.render(g.add(g.sub(d_out, d_in), a), rect)

    def density(self, g, rect, reach, dx=0, dy=0):
        """The alpha level of the shape (moved by (dx, dy)) near each pixel
        of rect, up to about reach pixels away; None for an opaque layer."""
        if self.opaque:
            return None
        std = max(1.0, reach / 2.0)
        big = rect_grow(rect, int(3 * std) + 2)
        h = Graph()
        a = h.region(h.translate(h.src(self.alpha), dx, dy), big)
        n = h.region(h.translate(h.src(self.norm), dx, dy), big)
        blur_a = h.op('gegl:gaussian-blur', a, std_dev_x=std, std_dev_y=std, abyss_policy='none')
        blur_n = h.op('gegl:gaussian-blur', n, std_dev_x=std, std_dev_y=std, abyss_policy='none')
        return g.src(h.render(h.clamp(h.op('gegl:divide', blur_a, blur_n)), rect))


def with_density(g, b, mask, rect, reach, dx=0, dy=0):
    d = b.shape.density(g, rect, reach, dx, dy)
    return mask if d is None else g.mul(mask, d)


def ramp(g, sigma, steps, growth, invert=False):
    """The ramp of the original's draw_blurshape (): the selection grown
    by growth, growth - 1, ... pixels (steps times), each filled with
    the next of steps shades from 1/steps to 1 (or from 1 - 1/steps down
    to 0, inverted, over white), as a smooth ramp."""
    r = g.clamp(g.lin(sigma, -1.0 / steps, (growth + 1.0) / steps))
    return g.inv(r) if invert else r


def coverage(g, sigma, growth):
    """The selection grown by growth pixels (shrunk for growth < 0)."""
    return g.clamp(g.lin(sigma, -1.0, growth + 1.0))


def noise_buffer(rect, seed):
    """Value noise as the original made it with plug-in-hsv-noise on
    black: half the pixels 0, the others uniform in 0..1."""
    g = Graph()
    black = g.const(0.0, rect)
    noise = g.op('gegl:noise-hsv', black, holdness=1, hue_distance=0.0,
                 saturation_distance=0.0, value_distance=1.0, seed=seed)
    # gegl:noise-hsv works on perceptual values; the original's noise
    # was uniform in the 8-bit values
    buf = g.render(noise, rect, "Y' float")
    return cast_buffer(buf, rect, "Y' float", 'Y float')


def noise_mask(g, mask, rect, amount, seed):
    """The original's apply_noise () for a colour effect: the noise in
    GIMP 2's Overlay mode over the mask, at amount percent."""
    n = g.src(noise_buffer(rect, seed))
    # GIMP 2 overlay: I * (I + 2 * N * (1 - I))
    over = g.mul(mask, g.add(mask, g.mul(g.mul(n, g.inv(mask)), 2.0)))
    return g.clamp(g.mix(mask, over, g.const(amount / 100.0, rect)))


def noise_factor(g, rect, amount, seed):
    """The original's apply_noise () for a gradient effect: a layer mask
    of the noise at amount percent over white."""
    n = g.src(noise_buffer(rect, seed))
    return g.inv(g.mul(g.inv(n), amount / 100.0))


def gradient_lut(g, node, rect, gradient, reverse=False):
    """Maps the values of node through the colours of gradient (with
    their alpha), as plug-in-gradmap did."""
    samples = gradient.get_uniform_samples(LUT_SIZE, reverse)
    table = []
    for color in samples:
        rgba = color.get_rgba()
        table.append((rgba.red, rgba.green, rgba.blue, rgba.alpha))
    return g.src(lut_buffer(g.render(g.clamp(node), rect), rect, table, 4))


# ------------------------------------------------------------ the layers

def image_layer_type(image):
    if image.get_base_type() == Gimp.ImageBaseType.GRAY:
        return Gimp.ImageType.GRAYA_IMAGE
    return Gimp.ImageType.RGBA_IMAGE


def is_effect_layer(item):
    return item is not None and item.get_parasite(PARASITE_EFFECT) is not None


def effect_info(item):
    parasite = item.get_parasite(PARASITE_EFFECT)
    if parasite is None:
        return None
    try:
        info = json.loads(bytes(parasite.get_data()).decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(info, dict) or info.get('effect') not in EFFECTS:
        return None
    return info


def group_info(item):
    if item is None or not item.is_group():
        return None
    parasite = item.get_parasite(PARASITE_GROUP)
    if parasite is None:
        return None
    try:
        return json.loads(bytes(parasite.get_data()).decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return {}


def attach_json(item, name, data):
    item.attach_parasite(Gimp.Parasite.new(name, PARASITE_FLAGS,
                                           list(json.dumps(data, sort_keys=True).encode('utf-8'))))


def effects_group(layer):
    """The layer group of the effects of layer, or None."""
    parent = layer.get_parent()
    if group_info(parent) is not None:
        return parent
    return None


def group_source(group):
    """The layer that the effects of group belong to."""
    info = group_info(group) or {}
    others = [c for c in group.get_children() if not is_effect_layer(c)]
    for child in others:
        if child.get_tattoo() == info.get('source'):
            return child
    if len(others) >= 1:
        return others[0]
    return None


def resolve_layer(image, drawables):
    """The layer to work on, for the drawables the procedure was called
    with: a layer mask stands for its layer, an effect layer or the
    group of the effects for the layer they belong to."""
    if drawables is None or len(drawables) != 1:
        raise LayerFXError('Select one layer.')
    drawable = drawables[0]
    if isinstance(drawable, Gimp.LayerMask):
        drawable = Gimp.Layer.from_mask(drawable)
    if not isinstance(drawable, Gimp.Layer):
        raise LayerFXError('Layer Effects work on layers, not on channels or selections.')
    if drawable.get_image() != image:
        raise LayerFXError('The layer is not part of the image.')
    if is_effect_layer(drawable):
        group = effects_group(drawable)
        source = group_source(group) if group is not None else None
        if source is None:
            raise LayerFXError('"%s" is a layer made by Layer Effects; select the layer it '
                               'belongs to.' % drawable.get_name())
        return source
    if group_info(drawable) is not None:
        source = group_source(drawable)
        if source is None:
            raise LayerFXError('The group "%s" has no layer for its effects.' % drawable.get_name())
        return source
    if drawable.is_group():
        raise LayerFXError('Layer Effects cannot be applied to a layer group; select a layer '
                           'inside it.')
    return drawable


def check_layer(image, layer, effect):
    base = image.get_base_type()
    if base not in (Gimp.ImageBaseType.RGB, Gimp.ImageBaseType.GRAY):
        raise LayerFXError('Layer Effects work on RGB and grayscale images, not on indexed '
                           'images (Image > Mode).')
    if effect.needs_alpha and not layer.has_alpha():
        raise LayerFXError('%s needs a layer with an alpha channel (Layer > Transparency > '
                           'Add Alpha Channel).' % effect.title)


class Build:
    """What an effect needs while it builds its layers."""

    def __init__(self, image, source, place):
        self.image = image
        self.source = source
        self.place = place          # a Placer
        self.shape = Shape(source)
        self.name = source.get_name()
        self.layer_type = image_layer_type(image)
        self.layers = []            # (layer, role)
        self.seed = random.randrange(1, 2 ** 31)

    def new_layer(self, suffix, rect, opacity, mode):
        x, y, w, h = rect
        layer = Gimp.Layer.new(self.image, '%s-%s' % (self.name, suffix), max(1, w), max(1, h),
                               self.layer_type, opacity, mode)
        return layer, (x, y)


def effect_side(effect_name, settings):
    if effect_name in ('drop-shadow', 'outer-glow'):
        return 'below'
    if effect_name == 'stroke' and settings.get('position', 50.0) >= 100.0:
        return 'below'
    return 'above'


RANKS = {
    ('bevel-emboss', 'highlight'): 10,
    ('bevel-emboss', 'shadow'): 11,
    ('stroke', 'above'): 20,
    ('inner-shadow', 'main'): 30,
    ('inner-glow', 'main'): 40,
    ('satin', 'main'): 50,
    ('color-overlay', 'main'): 60,
    ('gradient-overlay', 'main'): 70,
    ('pattern-overlay', 'main'): 80,
    ('stroke', 'below'): 110,
    ('outer-glow', 'main'): 120,
    ('drop-shadow', 'main'): 130,
}
SOURCE_RANK = 100


def rank_of(item, source):
    if item == source:
        return SOURCE_RANK
    info = effect_info(item)
    if info is None:
        return None
    effect = info['effect']
    role = info.get('role', 'main')
    if effect == 'stroke':
        role = effect_side('stroke', info.get('settings', {}))
    return RANKS.get((effect, role))


# ------------------------------------------------------------ the effects

def gradient_measurements(drawoffsetx, drawoffsety, gradienttype, centerx, centery, angle, width):
    """The start and end of a gradient, as the original computed them."""
    ang = (angle * -1) * (math.pi / 180.0)
    if gradienttype == 0:
        offset = ((width / 2.0) * math.cos(ang), (width / 2.0) * math.sin(ang))
        start = (centerx - offset[0] - drawoffsetx, centery - offset[1] - drawoffsety)
        end = (centerx + offset[0] - drawoffsetx, centery + offset[1] - drawoffsety)
    elif 1 <= gradienttype <= 8:
        offset = ((width / 2.0) * math.cos(ang), (width / 2.0) * math.sin(ang))
        start = (centerx - drawoffsetx, centery - drawoffsety)
        end = (centerx + offset[0] - drawoffsetx, centery + offset[1] - drawoffsety)
    else:
        offset = (width * math.cos(ang), width * math.sin(ang))
        start = (centerx - drawoffsetx, centery - drawoffsety)
        end = (centerx + offset[0] - drawoffsetx, centery + offset[1] - drawoffsety)
    return start, end


def shadow_offset(angle, distance):
    ang = ((angle + 180) * -1) * (math.pi / 180.0)
    return rnd(distance * math.cos(ang)), rnd(distance * math.sin(ang))


def select_mask(image, graph, node):
    """Makes node (in image coordinates) the selection."""
    w, h = image.get_width(), image.get_height()
    channel = Gimp.Channel.new(image, 'layerfx-selection', w, h, 100.0, Gegl.Color.new('black'))
    image.insert_channel(channel, None, 0)
    write_layer(graph, channel, graph.region(node, (0, 0, w, h)))
    image.select_item(Gimp.ChannelOps.REPLACE, channel)
    image.remove_channel(channel)


def gradient_fill(b, layer, s, selection, graph):
    """Fills layer with the gradient of the settings s, as the
    original's gimp_edit_blend () did. The shaped gradients follow the
    shape of selection (a node): its pixels that are not 0, so that the
    layer is filled at full opacity there, to be masked by selection."""
    image = b.image
    gtype = nick_index(GRADIENT_TYPES, s['gradient-type'])
    Gimp.context_push()
    try:
        Gimp.context_set_gradient(s['gradient'])
        Gimp.context_set_gradient_repeat_mode(enum_value(REPEATS, Gimp.RepeatMode, s['repeat']))
        Gimp.context_set_gradient_reverse(bool(s['reverse']))
        ok, lx, ly = layer.get_offsets()
        start, end = gradient_measurements(lx, ly, gtype, s['center-x'], s['center-y'],
                                           s['angle'], s['width'])
        if 6 <= gtype <= 8:
            select_mask(image, graph, graph.clamp(graph.lin(selection, 1e6)))
        layer.edit_gradient_fill(enum_value(GRADIENT_TYPES, Gimp.GradientType, s['gradient-type']),
                                 1.0, False, 1, 0.0, False, start[0], start[1], end[0], end[1])
        Gimp.Selection.none(image)
    finally:
        Gimp.context_pop()


def pattern_fill(layer, pattern, scale, interpolation):
    """Fills layer with pattern, scaled as the original did it: filled at
    100 / scale of the size and scaled up."""
    Gimp.context_push()
    try:
        Gimp.context_set_pattern(pattern)
        if scale == 100.0:
            layer.fill(Gimp.FillType.PATTERN)
            return layer
        x, y, w, h = layer_rect(layer)
        layer.resize(max(1, rnd(w / (scale / 100.0))), max(1, rnd(h / (scale / 100.0))), 0, 0)
        layer.fill(Gimp.FillType.PATTERN)
        Gimp.context_set_interpolation(enum_value(INTERPOLATIONS, Gimp.InterpolationType,
                                                  interpolation))
        Gimp.context_set_transform_direction(Gimp.TransformDirection.FORWARD)
        Gimp.context_set_transform_resize(Gimp.TransformResize.ADJUST)
        scaled = layer.transform_scale(x, y, x + w, y + h)
        if layer_rect(scaled) != (x, y, w, h):
            scaled.resize(w, h, scaled.get_offsets()[1] - x, scaled.get_offsets()[2] - y)
            scaled.set_offsets(x, y)
        return scaled
    finally:
        Gimp.context_pop()


def finish_color(b, g, layer, rect, color, mask):
    """The layer: color, with mask as its alpha."""
    write_layer(g, layer, g.op('gegl:opacity', g.color(color, rect), g.clamp(mask)))


def finish_filled(b, g, layer, mask):
    """The layer as filled, with its alpha times mask."""
    ok, lx, ly = layer.get_offsets()
    node = g.op('gegl:opacity', g.src(layer.get_buffer(), lx, ly), g.clamp(mask))
    write_layer(g, layer, node)


def add_layer(b, layer, xy, rank, side, role='main'):
    b.place(layer, rank, side)
    layer.set_offsets(*xy)
    b.layers.append((layer, role))
    return layer


def build_drop_shadow(b, s):
    size = s['size']
    growamt = int(math.ceil(size / 2.0))
    steps = rnd(size - (s['spread'] / 100.0) * size)
    lyrgrowamt = rnd(growamt * 1.2)
    dx, dy = shadow_offset(s['offset-angle'], s['offset-distance'])
    sx, sy, sw, sh = b.shape.rect
    rect = (sx + dx - lyrgrowamt, sy + dy - lyrgrowamt, sw + 2 * lyrgrowamt, sh + 2 * lyrgrowamt)
    layer, xy = b.new_layer('dropshadow', rect, s['opacity'], layer_mode(s['mode']))
    add_layer(b, layer, xy, RANKS[('drop-shadow', 'main')], 'below')
    g = Graph()
    sigma = g.src(b.shape.sigma(rect, 2 * size + 4, dx, dy))
    if steps > 0:
        m = ramp(g, sigma, steps, growamt)
    else:
        m = coverage(g, sigma, growamt)
    if s['contour'] != 'linear':
        m = g.mul(g.lut(m, contour_samples(s['contour']), rect), coverage(g, sigma, growamt))
    m = with_density(g, b, m, rect, growamt + 1, dx, dy)
    if s['noise'] > 0:
        m = noise_mask(g, m, rect, s['noise'], b.seed)
    if s['knockout']:
        m = g.mul(m, b.shape.knockout_node(g, rect))
    finish_color(b, g, layer, rect, s['color'], m)


def build_inner_shadow(b, s, merge):
    size = s['size']
    growamt = int(math.ceil(size / 2.0))
    chokeamt = (s['choke'] / 100.0) * size
    steps = rnd(size - chokeamt)
    dx, dy = shadow_offset(s['offset-angle'], s['offset-distance'])
    rect = b.shape.rect
    layer, xy = b.new_layer('innershadow', rect, s['opacity'], layer_mode(s['mode']))
    add_layer(b, layer, xy, RANKS[('inner-shadow', 'main')], 'above')
    g = Graph()
    sigma = g.src(b.shape.sigma(rect, 2 * size + 4, dx, dy))
    edge = s['source'] == 'edge'
    if steps > 0:
        m = ramp(g, sigma, steps, growamt - chokeamt, invert=edge)
    else:
        m = coverage(g, sigma, -growamt)
        if edge:
            m = g.inv(m)
    if s['contour'] != 'linear':
        m = g.lut(m, contour_samples(s['contour']), rect)
    if not merge:
        m = g.mul(m, g.region(b.shape.alpha_node(g), rect))
    if s['noise'] > 0:
        m = noise_mask(g, m, rect, s['noise'], b.seed)
    finish_color(b, g, layer, rect, s['color'], m)


def build_outer_glow(b, s):
    size = s['size']
    growamt = (s['spread'] / 100.0) * size
    steps = rnd(size - growamt)
    lyrgrowamt = rnd(size * 1.2)
    rect = rect_grow(b.shape.rect, lyrgrowamt)
    layer, xy = b.new_layer('outerglow', rect, s['opacity'], layer_mode(s['mode']))
    add_layer(b, layer, xy, RANKS[('outer-glow', 'main')], 'below')
    g = Graph()
    sigma = g.src(b.shape.sigma(rect, 2 * size + 4))
    if steps > 0:
        r = ramp(g, sigma, steps, size)
    else:
        r = coverage(g, sigma, growamt)
    if s['contour'] != 'linear':
        r = g.mul(g.lut(r, contour_samples(s['contour']), rect), coverage(g, sigma, size))
    knockout = b.shape.knockout_node(g, rect) if s['knockout'] else None
    if s['fill-type'] == 'color':
        m = with_density(g, b, r, rect, size + 1)
        if s['noise'] > 0:
            m = noise_mask(g, m, rect, s['noise'], b.seed)
        if knockout is not None:
            m = g.mul(m, knockout)
        finish_color(b, g, layer, rect, s['color'], m)
    else:
        colors = gradient_lut(g, g.inv(r), rect, s['gradient'])
        m = with_density(g, b, coverage(g, sigma, size), rect, size + 1)
        if s['noise'] > 0:
            m = g.mul(m, noise_factor(g, rect, s['noise'], b.seed))
        if knockout is not None:
            m = g.mul(m, knockout)
        write_layer(g, layer, g.op('gegl:opacity', g.crop(colors, rect), g.clamp(m)))


def build_inner_glow(b, s, merge):
    size = s['size']
    chokeamt = (s['choke'] / 100.0) * size
    steps = rnd(size - chokeamt)
    rect = b.shape.rect
    layer, xy = b.new_layer('innerglow', rect, s['opacity'], layer_mode(s['mode']))
    add_layer(b, layer, xy, RANKS[('inner-glow', 'main')], 'above')
    g = Graph()
    sigma = g.src(b.shape.sigma(rect, 2 * size + 4))
    edge = s['source'] == 'edge'
    if steps > 0:
        if edge:
            r = ramp(g, sigma, steps, -chokeamt - 1, invert=True)
        else:
            r = ramp(g, sigma, steps, -chokeamt)
    else:
        r = coverage(g, sigma, -chokeamt)
        if edge:
            r = g.inv(r)
    if s['contour'] != 'linear':
        r = g.lut(r, contour_samples(s['contour']), rect)
    alpha = g.region(b.shape.alpha_node(g), rect)
    if s['fill-type'] == 'color':
        m = r
        if edge and not merge:
            m = g.mul(m, alpha)
        if s['noise'] > 0:
            m = noise_mask(g, m, rect, s['noise'], b.seed)
        finish_color(b, g, layer, rect, s['color'], m)
    else:
        colors = gradient_lut(g, g.inv(r), rect, s['gradient'])
        m = g.inv(coverage(g, sigma, -size))
        if not merge:
            m = g.mul(m, alpha)
        if s['noise'] > 0:
            m = g.mul(m, noise_factor(g, rect, s['noise'], b.seed))
        write_layer(g, layer, g.op('gegl:opacity', g.crop(colors, rect), g.clamp(m)))


def texture_node(b, g, rect, s):
    """The bevel's texture: the pattern, desaturated, scaled, with the
    contrast of its depth, as a mask to multiply the bump map with."""
    image = b.image
    scale = s['scale']
    x, y, w, h = rect
    tmp = Gimp.Layer.new(image, 'layerfx-texture', w, h, b.layer_type, 100.0,
                         Gimp.LayerMode.NORMAL)
    image.insert_layer(tmp, None, 0)
    tmp.set_offsets(x, y)
    tmp = pattern_fill(tmp, s['pattern'], scale, 'nohalo')
    tx, ty, tw, th = layer_rect(tmp)
    # desaturated to its luminance, as 8-bit values were
    lum = cast_buffer(tmp.get_buffer(), (0, 0, tw, th), "Y' float", 'Y float')
    image.remove_layer(tmp)
    t = g.src(lum, tx, ty)
    depth = s['tex-depth']
    if depth < 0:
        t = g.inv(t)
    d = abs(depth)
    if d <= 100.0:
        contrast = rnd((1 - (d / 100.0)) * -127)
    else:
        contrast = rnd(((d - 100.0) / 900.0) * 127)
    if contrast != 0:
        t = g.lut(g.region(t, rect), brightness_contrast_samples(contrast / 127.0), rect)
    return g.region(t, rect)


def build_bevel_emboss(b, s, merge):
    size = s['size']
    style = s['style']
    lyrgrowamt = rnd(size * 1.2)
    sx, sy, sw, sh = b.shape.rect
    if style == 'outer-bevel':
        rect = rect_grow(b.shape.rect, lyrgrowamt)
    elif style == 'inner-bevel':
        rect = b.shape.rect
    else:
        rect = (sx - lyrgrowamt // 2, sy - lyrgrowamt // 2, sw + lyrgrowamt, sh + lyrgrowamt)
    shadow, xy = b.new_layer('shadow', rect, s['shadow-opacity'], layer_mode(s['shadow-mode']))
    add_layer(b, shadow, xy, RANKS[('bevel-emboss', 'shadow')], 'above', 'shadow')
    highlight, xy = b.new_layer('highlight', rect, s['highlight-opacity'],
                                layer_mode(s['highlight-mode']))
    add_layer(b, highlight, xy, RANKS[('bevel-emboss', 'highlight')], 'above', 'highlight')
    g = Graph()
    sigma = g.src(b.shape.sigma(rect, 2 * size + 4))
    halfsizef = size // 2
    halfsizec = size - halfsizef
    if size == 0:
        bump = g.const(1.0 if style == 'pillow-emboss' else 0.0, rect)
    elif style == 'outer-bevel':
        bump = ramp(g, sigma, size, size)
    elif style == 'inner-bevel':
        bump = ramp(g, sigma, size, 0)
    elif style == 'emboss':
        bump = ramp(g, sigma, size, int(math.ceil(size / 2.0)))
    else:
        bump = ramp(g, sigma, halfsizec, halfsizec, invert=True)
        if halfsizef > 0:
            bump = g.mix(bump, ramp(g, sigma, halfsizef, 0), coverage(g, sigma, 0))
    if s['use-texture']:
        bump = g.mul(bump, texture_node(b, g, rect, s))
    if s['surface-contour'] != 'linear':
        bump = g.lut(bump, contour_samples(s['surface-contour']), rect)
    # gegl:bump-map, like plug-in-bump-map, works on perceptual values:
    # the bump map and the grey are given to it as such, unchanged. It
    # also shades wrongly unless its buffers start at (0, 0).
    at_origin = (0, 0, rect[2], rect[3])
    bump_buf = moved_buffer(g.render(bump, rect), rect, 'Y float', "Y' float")
    grey = cast_buffer(g.render(g.const(127 / 255.0, at_origin), at_origin), at_origin,
                       'Y float', "Y' float")
    angle = s['angle'] + 360.0 if s['angle'] < 0 else s['angle']
    bumped = g.op('gegl:bump-map', g.src(grey), g.src(bump_buf), type='linear',
                  compensate=True, invert=s['direction'] == 'down', tiled=False,
                  azimuth=angle, elevation=s['altitude'], depth=s['depth'],
                  offset_x=0, offset_y=0, waterlevel=0.0, ambient=0.0)
    h_buf = moved_buffer(g.render(bumped, at_origin, "Y' float"), at_origin, "Y' float",
                         'Y float', rect)
    h = g.clamp(g.src(h_buf))
    if s['gloss-contour'] != 'linear':
        h = g.lut(h, contour_samples(s['gloss-contour']), rect)
    if s['soften'] > 0:
        # plug-in-gauss-rle's radius as a standard deviation
        std = (s['soften'] + 1.0) / math.sqrt(2.0 * math.log(255.0))
        h = g.op('gegl:gaussian-blur', h, std_dev_x=std, std_dev_y=std, abyss_policy='clamp')
    if s['use-texture'] and s['invert']:
        h = g.inv(h)
    # levels 127..255 to 0..255, and 0..127 to 255..0
    hmask = g.lin(h, 255.0 / 128.0, -127.0 / 128.0)
    smask = g.lin(h, -255.0 / 127.0, 1.0)
    if style == 'outer-bevel':
        smask = g.mul(g.clamp(smask), coverage(g, sigma, size))
    elif style == 'inner-bevel':
        smask = g.mul(g.clamp(smask), g.region(b.shape.alpha_node(g), rect))
    else:
        smask = g.mul(g.clamp(smask), coverage(g, sigma, halfsizec))
    if style != 'inner-bevel':
        hmask = with_density(g, b, g.clamp(hmask), rect, size + 1)
        smask = with_density(g, b, smask, rect, size + 1)
    finish_color(b, g, highlight, rect, s['highlight-color'], hmask)
    finish_color(b, g, shadow, rect, s['shadow-color'], smask)


def build_satin(b, s, merge):
    size = s['size']
    growamt = int(math.ceil(size / 2.0))
    dx, dy = shadow_offset(s['offset-angle'], s['offset-distance'])
    rect = b.shape.rect
    layer, xy = b.new_layer('satin', rect, s['opacity'], layer_mode(s['mode']))
    add_layer(b, layer, xy, RANKS[('satin', 'main')], 'above')
    g = Graph()
    if size > 0:
        # the ramp is 0 beyond growamt + 1 pixels from the shape
        around = rect_grow(rect, growamt + 2)
        sigma_around = g.src(b.shape.sigma(around, 2 * size + 4))
        r = g.render(ramp(g, sigma_around, size, growamt), around)
        one = g.region(g.src(r, dx, dy), rect)
        two = g.region(g.src(r, -dx, -dy), rect)
        d = g.op('gegl:absolute', g.sub(one, two))
    else:
        d = g.const(0.0, rect)
    if s['contour'] != 'linear':
        sigma = g.src(b.shape.sigma(rect, 2 * size + 4))
        d = g.mul(g.lut(d, contour_samples(s['contour']), rect), coverage(g, sigma, size))
    if s['invert']:
        d = g.inv(d)
    if not merge:
        d = g.mul(g.clamp(d), g.region(b.shape.alpha_node(g), rect))
    finish_color(b, g, layer, rect, s['color'], d)


def build_stroke(b, s, merge):
    size = s['size']
    position = s['position']
    if position <= 0.0:
        rect = b.shape.rect
        side = 'above'
    elif position >= 100.0:
        rect = rect_grow(b.shape.rect, rnd(size * 1.2))
        side = 'below'
    else:
        outerwidth = rnd((position / 100.0) * size)
        innerwidth = size - outerwidth
        rect = rect_grow(b.shape.rect, rnd(outerwidth * 1.2))
        side = 'above'
    layer, xy = b.new_layer('stroke', rect, s['opacity'], layer_mode(s['mode']))
    add_layer(b, layer, xy, RANKS[('stroke', side)], side)
    g = Graph()
    sigma = g.src(b.shape.sigma(rect, 2 * size + 4))
    alpha = g.region(b.shape.alpha_node(g), rect)
    if position <= 0.0:
        outer = alpha
        if merge:
            # the original made the outer edge hard when merging, so
            # that the stroke covers the edge of the layer
            outer = g.clamp(g.lin(alpha, 1e6))
        m = g.mul(outer, g.inv(coverage(g, sigma, -size)))
    elif position >= 100.0:
        inner = g.clamp(g.lin(alpha, 256.0, -255.0))
        m = g.mul(coverage(g, sigma, size), g.inv(inner))
    else:
        m = g.mul(coverage(g, sigma, outerwidth), g.inv(coverage(g, sigma, -innerwidth)))
    if position > 0.0:
        m = with_density(g, b, m, rect, size + 1)
    fill = s['fill-type']
    if fill == 'color':
        finish_color(b, g, layer, rect, s['color'], m)
        return
    if fill == 'gradient':
        gradient_fill(b, layer, s, selection=m, graph=g)
    else:
        layer = pattern_fill(layer, s['pattern'], s['scale'], s['interpolation'])
        b.layers[-1] = (layer, 'main')
    finish_filled(b, g, layer, m)


def build_color_overlay(b, s, merge):
    rect = b.shape.rect
    layer, xy = b.new_layer('color', rect, s['opacity'], layer_mode(s['mode']))
    add_layer(b, layer, xy, RANKS[('color-overlay', 'main')], 'above')
    g = Graph()
    m = g.const(1.0, rect) if merge else g.region(b.shape.alpha_node(g), rect)
    finish_color(b, g, layer, rect, s['color'], m)


def build_gradient_overlay(b, s, merge):
    rect = b.shape.rect
    layer, xy = b.new_layer('gradient', rect, s['opacity'], layer_mode(s['mode']))
    add_layer(b, layer, xy, RANKS[('gradient-overlay', 'main')], 'above')
    g = Graph()
    alpha = g.region(b.shape.alpha_node(g), rect)
    gradient_fill(b, layer, s, alpha, g)
    if not merge:
        finish_filled(b, g, layer, alpha)


def build_pattern_overlay(b, s, merge):
    rect = b.shape.rect
    layer, xy = b.new_layer('pattern', rect, s['opacity'], layer_mode(s['mode']))
    add_layer(b, layer, xy, RANKS[('pattern-overlay', 'main')], 'above')
    layer = pattern_fill(layer, s['pattern'], s['scale'], s['interpolation'])
    b.layers[-1] = (layer, 'main')
    if not merge:
        g = Graph()
        finish_filled(b, g, layer, g.region(b.shape.alpha_node(g), rect))


# ------------------------------------------------------------ arguments

class Arg:
    def __init__(self, kind, name, label, blurb, *extra):
        self.kind = kind
        self.name = name
        self.label = label
        self.blurb = blurb
        self.extra = extra

    def default(self):
        if self.kind in ('double', 'int'):
            return self.extra[2]
        if self.kind in ('boolean', 'choice'):
            return self.extra[-1]
        if self.kind == 'color':
            return self.extra[0]
        return None


def color_arg(name, label, blurb, css):
    return Arg('color', name, label, blurb, css)


def choice_arg(name, label, blurb, table, default):
    return Arg('choice', name, label, blurb, table, default)


def mode_arg(name='mode', label='_Blend Mode', blurb="The effect layer's blend mode",
             default='normal'):
    return choice_arg(name, label, blurb, MODES, default)


def percent_arg(name, label, blurb, default):
    return Arg('double', name, label, blurb, 0.0, 100.0, default)


def opacity_arg(default, name='opacity', label='_Opacity', blurb="The effect's opacity"):
    return percent_arg(name, label, blurb, default)


def contour_arg(name='contour', label='Con_tour',
                blurb="A contour used to modify the effect's intensity curve", default='linear'):
    return choice_arg(name, label, blurb, CONTOURS, default)


def size_arg(default, label='S_ize', blurb="The size of the effect's blur", low=0):
    return Arg('int', 'size', label, blurb, low, 250, default)


def angle_arg(name, label, blurb, default):
    return Arg('double', name, label, blurb, -180.0, 180.0, default)


def distance_arg(default):
    return Arg('double', 'offset-distance', '_Distance',
               'The distance between the layer and the effect', 0.0, 30000.0, default)


def bool_arg(name, label, blurb, default=False):
    return Arg('boolean', name, label, blurb, default)


def merge_arg():
    return bool_arg('merge', '_Merge with layer',
                    'Merge the effect with the layer (it cannot be reapplied then)')


def gradient_args(width_default):
    return [
        Arg('gradient', 'gradient', '_Gradient', 'The gradient'),
        choice_arg('gradient-type', 'Gradient _Type', 'The type of gradient',
                   GRADIENT_TYPES, 'linear'),
        choice_arg('repeat', 'Repeat', 'The repeat mode of the gradient', REPEATS, 'none'),
        bool_arg('reverse', '_Reverse', 'Use the reverse gradient'),
        Arg('double', 'center-x', '_Center X', 'X coordinate of the center (in the image)',
            0.0, 262144.0, 0.0),
        Arg('double', 'center-y', 'Center _Y', 'Y coordinate of the center (in the image)',
            0.0, 262144.0, 0.0),
        angle_arg('angle', 'Gradient _Angle', 'The angle of the gradient', 90.0),
        Arg('double', 'width', 'Gradient _Width', 'The width of the gradient', 0.0, 262144.0,
            width_default),
    ]


def pattern_args(scale_label='Scale'):
    return [
        Arg('pattern', 'pattern', '_Pattern', 'The pattern'),
        Arg('double', 'scale', scale_label, 'The scale of the pattern, in percent',
            1.0, 1000.0, 100.0),
        choice_arg('interpolation', 'Interpolation', 'The interpolation of the scaled pattern',
                   INTERPOLATIONS, 'none'),
    ]


class Effect:
    def __init__(self, name, title, menu_label, blurb, image_types, args, build, layout=None):
        self.name = name
        self.title = title
        self.menu_label = menu_label
        self.blurb = blurb
        self.image_types = image_types
        self.needs_alpha = image_types == 'RGBA, GRAYA'
        self.args = args
        self.build = build
        self.layout = layout or [a.name for a in args]

    def arg(self, name):
        for a in self.args:
            if a.name == name:
                return a
        return None

    def inside(self, s):
        """Whether the effect stays inside the layer's shape (for merging)."""
        if self.name in ('inner-shadow', 'inner-glow', 'satin', 'color-overlay',
                         'gradient-overlay', 'pattern-overlay'):
            return True
        if self.name == 'stroke':
            return s['position'] <= 0.0
        if self.name == 'bevel-emboss':
            return s['style'] == 'inner-bevel'
        return False


EFFECT_LIST = [
    Effect('drop-shadow', 'Drop Shadow', '_Drop Shadow...', 'Adds a drop shadow to a layer.',
           'RGBA, GRAYA', [
               color_arg('color', 'Shadow _Color', "The shadow's color", 'black'),
               opacity_arg(75.0, blurb="The shadow's opacity"),
               contour_arg(blurb="A contour used to modify the shadow's intensity curve"),
               percent_arg('noise', '_Noise', 'The amount of noise applied to the shadow', 0.0),
               mode_arg(blurb="The shadow layer's blend mode", default='multiply'),
               percent_arg('spread', '_Spread', 'Spread', 0.0),
               size_arg(5, blurb="The size of the shadow's blur"),
               angle_arg('offset-angle', '_Angle', 'The angle the shadow is cast in', 120.0),
               distance_arg(5.0),
               bool_arg('knockout', 'Layer _knocks out Drop Shadow',
                        'Layer knocks out Drop Shadow'),
               merge_arg(),
           ], lambda b, s, merge: build_drop_shadow(b, s),
           layout=['color', 'mode', 'opacity', 'offset-angle', 'offset-distance', 'spread',
                   'size', 'contour', 'noise', 'knockout', 'merge']),
    Effect('inner-shadow', 'Inner Shadow', 'I_nner Shadow...', 'Adds an inner shadow to a layer.',
           'RGB*, GRAY*', [
               color_arg('color', 'Shadow _Color', "The shadow's color", 'black'),
               opacity_arg(75.0, blurb="The shadow's opacity"),
               contour_arg(blurb="A contour used to modify the shadow's intensity curve"),
               percent_arg('noise', '_Noise', 'The amount of noise applied to the shadow', 0.0),
               mode_arg(blurb="The shadow layer's blend mode", default='multiply'),
               choice_arg('source', 'Source', 'Source', SOURCES, 'edge'),
               percent_arg('choke', 'C_hoke', 'Choke', 0.0),
               size_arg(5, blurb="The size of the shadow's blur"),
               angle_arg('offset-angle', '_Angle', 'The angle the shadow is cast in', 120.0),
               distance_arg(5.0),
               merge_arg(),
           ], build_inner_shadow,
           layout=['color', 'mode', 'opacity', 'offset-angle', 'offset-distance', 'source',
                   'choke', 'size', 'contour', 'noise', 'merge']),
    Effect('outer-glow', 'Outer Glow', '_Outer Glow...',
           'Creates an outer glow effect around a layer.', 'RGBA, GRAYA', [
               color_arg('color', 'Glow _Color', "The glow's color", '#ffffbe'),
               opacity_arg(75.0, blurb="The glow's opacity"),
               contour_arg(blurb="A contour used to modify the glow's intensity curve"),
               percent_arg('noise', '_Noise', 'The amount of noise applied to the glow', 0.0),
               mode_arg(blurb="The glow layer's blend mode", default='screen'),
               percent_arg('spread', '_Spread', 'Spread', 0.0),
               size_arg(5, blurb="The size of the glow's blur"),
               bool_arg('knockout', 'Layer _knocks out Outer Glow', 'Layer knocks out Outer Glow'),
               merge_arg(),
               choice_arg('fill-type', 'Fill', 'Fill the glow with a color or a gradient',
                          GLOW_FILLS, 'color'),
               Arg('gradient', 'gradient', '_Gradient', 'The gradient of the glow'),
           ], lambda b, s, merge: build_outer_glow(b, s),
           layout=['fill-type', 'color', 'gradient', 'mode', 'opacity', 'spread', 'size',
                   'contour', 'noise', 'knockout', 'merge']),
    Effect('inner-glow', 'Inner Glow', '_Inner Glow...',
           'Creates an inner glow effect around a layer.', 'RGB*, GRAY*', [
               color_arg('color', 'Glow _Color', "The glow's color", '#ffffbe'),
               opacity_arg(75.0, blurb="The glow's opacity"),
               contour_arg(blurb="A contour used to modify the glow's intensity curve"),
               percent_arg('noise', '_Noise', 'The amount of noise applied to the glow', 0.0),
               mode_arg(blurb="The glow layer's blend mode", default='screen'),
               choice_arg('source', 'Source', 'Source', SOURCES, 'edge'),
               percent_arg('choke', 'C_hoke', 'Choke', 0.0),
               size_arg(5, blurb="The size of the glow's blur"),
               merge_arg(),
               choice_arg('fill-type', 'Fill', 'Fill the glow with a color or a gradient',
                          GLOW_FILLS, 'color'),
               Arg('gradient', 'gradient', '_Gradient', 'The gradient of the glow'),
           ], build_inner_glow,
           layout=['fill-type', 'color', 'gradient', 'mode', 'opacity', 'source', 'choke',
                   'size', 'contour', 'noise', 'merge']),
    Effect('bevel-emboss', 'Bevel and Emboss', '_Bevel and Emboss...',
           'Creates beveling and embossing effects over a layer.', 'RGBA, GRAYA', [
               choice_arg('style', 'S_tyle', 'Beveling style', STYLES, 'outer-bevel'),
               Arg('int', 'depth', '_Depth', 'Depth', 1, 65, 3),
               choice_arg('direction', 'Direction', 'Direction', DIRECTIONS, 'up'),
               size_arg(5, blurb='The size of the bevel'),
               Arg('int', 'soften', 'So_ften', 'Soften', 0, 16, 0),
               angle_arg('angle', '_Angle', 'Angle of the light source', 120.0),
               Arg('double', 'altitude', 'A_ltitude', 'Altitude of the light source',
                   0.0, 90.0, 30.0),
               contour_arg('gloss-contour', 'Gloss Con_tour',
                           "A contour used to modify the gloss's intensity curve"),
               color_arg('highlight-color', 'Highlight Color', 'The highlight color', 'white'),
               mode_arg('highlight-mode', 'Highlight Mode', "The highlight layer's blend mode",
                        'screen'),
               opacity_arg(75.0, 'highlight-opacity', 'Highlight Opacity',
                           "The highlight's opacity"),
               color_arg('shadow-color', 'Shadow Color', 'The shadow color', 'black'),
               mode_arg('shadow-mode', 'Shadow Mode', "The shadow layer's blend mode",
                        'multiply'),
               opacity_arg(75.0, 'shadow-opacity', 'Shadow Opacity', "The shadow's opacity"),
               contour_arg('surface-contour', 'Surface Contour',
                           'A contour used to modify the surface shape'),
               bool_arg('use-texture', 'Use Texture', 'Apply a texture to the surface'),
               Arg('pattern', 'pattern', '_Pattern', 'The texture pattern'),
               Arg('double', 'scale', 'Scale', 'The texture scale, in percent',
                   1.0, 1000.0, 100.0),
               Arg('double', 'tex-depth', 'Depth', 'The texture depth', -1000.0, 1000.0, 100.0),
               bool_arg('invert', '_Invert', 'Invert'),
               merge_arg(),
           ], build_bevel_emboss),
    Effect('satin', 'Satin', '_Satin...', 'Creates a satin effect over a layer.',
           'RGBA, GRAYA', [
               color_arg('color', 'Satin _Color', 'The satin color', 'black'),
               opacity_arg(75.0, blurb='The satin opacity'),
               mode_arg(blurb="The satin layer's blend mode", default='multiply'),
               angle_arg('offset-angle', '_Angle', 'The angle of the offset', 19.0),
               Arg('double', 'offset-distance', '_Distance', 'The offset distance',
                   0.0, 30000.0, 11.0),
               size_arg(14, blurb="The size of the satin's blur"),
               contour_arg(blurb="A contour used to modify the satin's intensity curve",
                           default='gaussian'),
               bool_arg('invert', 'Invert', 'Invert', True),
               merge_arg(),
           ], build_satin,
           layout=['color', 'mode', 'opacity', 'offset-angle', 'offset-distance', 'size',
                   'contour', 'invert', 'merge']),
    Effect('stroke', 'Stroke', 'S_troke...', 'Creates a stroke around a layer.',
           'RGBA, GRAYA', [
               color_arg('color', 'Stroke _Color', 'The stroke color', 'red'),
               opacity_arg(100.0, blurb='The stroke opacity'),
               mode_arg(blurb="The stroke layer's blend mode"),
               size_arg(3, blurb="The stroke's width", low=1),
               percent_arg('position', 'Position',
                           "The stroke's position; 0 = inside the layer's edge, 100 = outside "
                           'it', 50.0),
               merge_arg(),
               choice_arg('fill-type', 'Fill', 'Fill the stroke with a color, a gradient or a '
                          'pattern', STROKE_FILLS, 'color'),
           ] + gradient_args(0.0) + pattern_args(), build_stroke,
           layout=['size', 'position', 'mode', 'opacity', 'fill-type', 'color', 'gradient',
                   'gradient-type', 'repeat', 'reverse', 'center-x', 'center-y', 'angle', 'width',
                   'pattern', 'scale', 'interpolation', 'merge']),
    Effect('color-overlay', 'Color Overlay', '_Color Overlay...', 'Overlays a color over a layer.',
           'RGB*, GRAY*', [
               color_arg('color', 'Overlay _Color', 'The color to overlay', 'white'),
               opacity_arg(100.0, blurb='The overlay opacity'),
               mode_arg(blurb="The overlay layer's blend mode"),
               merge_arg(),
           ], build_color_overlay, layout=['color', 'mode', 'opacity', 'merge']),
    Effect('gradient-overlay', 'Gradient Overlay', '_Gradient Overlay...',
           'Overlays a gradient over a layer.', 'RGB*, GRAY*',
           gradient_args(10.0)[:4] + [
               opacity_arg(100.0, blurb='The overlay opacity'),
               mode_arg(blurb="The overlay layer's blend mode"),
           ] + gradient_args(10.0)[4:] + [merge_arg()], build_gradient_overlay,
           layout=['gradient', 'gradient-type', 'repeat', 'reverse', 'mode', 'opacity',
                   'center-x', 'center-y', 'angle', 'width', 'merge']),
    Effect('pattern-overlay', 'Pattern Overlay', '_Pattern Overlay...',
           'Overlays a pattern over a layer.', 'RGB*, GRAY*',
           pattern_args()[:1] + [
               opacity_arg(100.0, blurb='The overlay opacity'),
               mode_arg(blurb="The overlay layer's blend mode"),
           ] + pattern_args()[1:] + [merge_arg()], build_pattern_overlay,
           layout=['pattern', 'mode', 'opacity', 'scale', 'interpolation', 'merge']),
]
EFFECTS = {e.name: e for e in EFFECT_LIST}
REAPPLY = 'reapply-effects'


# ------------------------------------------------------------ settings

def settings_from_config(effect, config):
    return {a.name: config.get_property(a.name) for a in effect.args}


def fill_color_defaults(effect, config):
    """GIMP 3.2 hands colour arguments to a config made by another plug-in
    as transparent black instead of their defaults; such a colour, which
    would draw nothing, stands for the default."""
    for a in effect.args:
        if a.kind != 'color':
            continue
        rgba = config.get_property(a.name).get_rgba()
        if (rgba.red, rgba.green, rgba.blue, rgba.alpha) == (0.0, 0.0, 0.0, 0.0):
            config.set_property(a.name, Gegl.Color.new(a.extra[0]))


def encode_settings(effect, s):
    out = {}
    for a in effect.args:
        if a.name == 'merge':
            continue
        v = s[a.name]
        if a.kind == 'color':
            rgba = v.get_rgba()
            out[a.name] = [rgba.red, rgba.green, rgba.blue, rgba.alpha]
        elif a.kind in ('gradient', 'pattern'):
            out[a.name] = v.get_name() if v is not None else None
        else:
            out[a.name] = v
    return out


def decode_settings(effect, data):
    """Settings from a parasite; what is missing or invalid gets its
    default."""
    s = {}
    for a in effect.args:
        v = data.get(a.name)
        if a.kind == 'color':
            color = Gegl.Color.new(a.extra[0])
            if isinstance(v, list) and len(v) == 4:
                color.set_rgba(*[float(c) for c in v])
            s[a.name] = color
        elif a.kind == 'gradient':
            res = Gimp.Gradient.get_by_name(v) if isinstance(v, str) else None
            s[a.name] = res or Gimp.context_get_gradient()
        elif a.kind == 'pattern':
            res = Gimp.Pattern.get_by_name(v) if isinstance(v, str) else None
            s[a.name] = res or Gimp.context_get_pattern()
        elif a.kind == 'choice':
            table = a.extra[0]
            s[a.name] = v if v in [t[0] for t in table] else a.default()
        elif a.kind == 'boolean':
            s[a.name] = bool(v) if isinstance(v, (bool, int)) else a.default()
        elif a.kind == 'int':
            lo, hi = a.extra[0], a.extra[1]
            s[a.name] = min(max(int(v), lo), hi) if isinstance(v, (int, float)) else a.default()
        elif a.kind == 'double':
            lo, hi = a.extra[0], a.extra[1]
            s[a.name] = min(max(float(v), lo), hi) if isinstance(v, (int, float)) else a.default()
    s['merge'] = False
    return s


def check_settings(effect, s):
    for a in effect.args:
        if a.kind in ('gradient', 'pattern') and s.get(a.name) is None:
            if a.kind == 'gradient':
                s[a.name] = Gimp.context_get_gradient()
            else:
                s[a.name] = Gimp.context_get_pattern()


# ------------------------------------------------------------ applying

def find_effect_layers(group, effect_name):
    if group is None:
        return []
    return [c for c in group.get_children()
            if (effect_info(c) or {}).get('effect') == effect_name]


def group_name(source):
    return '%s-with-effects' % source.get_name()


def make_group(image, source):
    parent = source.get_parent()
    position = image.get_item_position(source)
    group = Gimp.GroupLayer.new(image, group_name(source))
    image.insert_layer(group, parent, position)
    group.set_mode(Gimp.LayerMode.PASS_THROUGH)
    set_group_source(group, source)
    image.reorder_item(source, group, 0)
    return group


def set_group_source(group, source):
    """Notes source as the layer of the group's effects; the group takes
    its new name if the layer was renamed (text layers are renamed after
    their text) and the group still has the name it was given."""
    old = group_info(group) or {}
    if old.get('name') and group.get_name() == '%s-with-effects' % old['name'] and \
            old['name'] != source.get_name():
        group.set_name(group_name(source))
    attach_json(group, PARASITE_GROUP, {'version': PARASITE_VERSION,
                                        'source': source.get_tattoo(),
                                        'name': source.get_name()})


class Placer:
    """Puts the layers of an effect into the layer stack: in the group
    of the effects, where the effect was before or in the order of
    RANKS, or right next to the layer (for merging and previews)."""

    def __init__(self, image, source, group, adjacent, old_index=None, old_side=None):
        self.image = image
        self.source = source
        self.group = group
        self.adjacent = adjacent
        self.old_index = old_index
        self.old_side = old_side
        self.ranks = {}

    def rank(self, item):
        if item.get_id() in self.ranks:
            return self.ranks[item.get_id()]
        return rank_of(item, self.source)

    def __call__(self, layer, rank, side):
        self.ranks[layer.get_id()] = rank
        image = self.image
        if self.adjacent or self.group is None:
            parent = self.source.get_parent()
            pos = image.get_item_position(self.source)
            image.insert_layer(layer, parent, pos + (1 if side == 'below' else 0))
            return
        children = self.group.get_children()
        if self.old_index is not None and self.old_side == side:
            index = self.old_index
        else:
            index = len(children)
            for i, child in enumerate(children):
                r = self.rank(child)
                if r is not None and r > rank:
                    index = i
                    break
        # a second layer of the same effect (Bevel and Emboss) goes to the
        # same index, above the first
        image.insert_layer(layer, self.group, index)


def layer_mask_buffer(layer):
    mask = layer.get_mask()
    if mask is None:
        return None
    w, h = layer.get_width(), layer.get_height()
    return cast_buffer(mask.get_buffer(), (0, 0, w, h), 'Y float', 'Y float')


def merge_layers(image, source, layers, effect, s):
    """Merges the layers of the effect with source, as the original did;
    returns the merged layer."""
    name = source.get_name()
    # merged down in GIMP 3, a layer in a mode such as Screen or Multiply
    # is clipped to the layer below it ("auto" composite mode) unless its
    # composite mode is Union; in GIMP 2 it was not clipped
    for layer in layers:
        layer.set_composite_mode(Gimp.LayerCompositeMode.UNION)
    inside = effect.inside(s)
    side = effect_side(effect.name, s)
    rect = layer_rect(source)
    mask = layer_mask_buffer(source)
    mask_on = source.get_apply_mask() if mask is not None else False
    if inside:
        # the effect stays inside the layer's shape: the layer keeps its
        # alpha, and its mask
        g = Graph()
        alpha = g.render(g.op('gegl:component-extract', g.src(source.get_buffer()),
                              component='alpha', linear=True), (0, 0, rect[2], rect[3]))
        if mask is not None:
            source.remove_mask(Gimp.MaskApplyMode.DISCARD)
        merged = source
        for layer in reversed(layers):     # the lowest first
            merged = image.merge_down(layer, Gimp.MergeType.EXPAND_AS_NECESSARY)
        if merged.has_alpha():
            g = Graph()
            write_layer(g, merged, straight_alpha_replace(g, merged, alpha, rect))
    else:
        # the effect reaches out of the layer: a mask in use is applied
        # first, as in the original; one that is off is kept
        if mask is not None:
            source.remove_mask(Gimp.MaskApplyMode.APPLY if mask_on else
                               Gimp.MaskApplyMode.DISCARD)
            if mask_on:
                mask = None
        if side == 'below':
            merged = image.merge_down(source, Gimp.MergeType.EXPAND_AS_NECESSARY)
        else:
            merged = source
            for layer in reversed(layers):
                merged = image.merge_down(layer, Gimp.MergeType.EXPAND_AS_NECESSARY)
    if mask is not None:
        restore_mask(merged, mask, rect, mask_on)
    merged.set_name(name)
    return merged


def restore_mask(layer, mask, rect, apply):
    """Gives layer the mask (a buffer at (0, 0) of the size of rect, where
    the layer was), white where the layer has grown."""
    new_mask = layer.create_mask(Gimp.AddMaskType.WHITE)
    layer.add_mask(new_mask)
    lx, ly, lw, lh = layer_rect(layer)
    g = Graph()
    hidden = g.region(g.inv(g.src(mask, rect[0], rect[1])), (lx, ly, lw, lh))
    write_layer(g, new_mask, g.inv(hidden))
    layer.set_apply_mask(apply)


def straight_alpha_replace(g, layer, alpha, rect):
    """The colors of layer with alpha (a buffer over rect, in layer
    coordinates at rect's origin) as its alpha: the merged colors of an
    inside effect, clipped to the layer's own shape as before."""
    lx, ly, lw, lh = layer_rect(layer)
    raw = layer.get_buffer().get(Gegl.Rectangle.new(0, 0, lw, lh), 1.0, 'RGB float',
                                 Gegl.AbyssPolicy.NONE)
    rgb = Gegl.Buffer.new('RGB float', 0, 0, lw, lh)
    rgb.set(Gegl.Rectangle.new(0, 0, lw, lh), 'RGB float', raw)
    a = g.region(g.src(alpha, rect[0], rect[1]), (lx, ly, lw, lh))
    return g.op('gegl:opacity', g.src(rgb, lx, ly), a)


def apply_effect(image, source, effect, s, preview=False):
    """Builds the effect with the settings s for source; returns the
    layers made (or the merged layer)."""
    check_settings(effect, s)
    merge = bool(s.get('merge'))
    group = effects_group(source)
    old = find_effect_layers(group, effect.name)
    old_index = old_side = None
    old_visible = True
    if old:
        old_index = image.get_item_position(old[0])
        old_side = effect_side(effect.name, (effect_info(old[0]) or {}).get('settings', {}))
        old_visible = old[0].get_visible()
        if not preview:
            for layer in old:
                image.remove_layer(layer)
    if not merge and not preview and group is None:
        group = make_group(image, source)
    place = Placer(image, source, group, adjacent=merge or preview,
                   old_index=None if (merge or preview) else old_index, old_side=old_side)
    b = Build(image, source, place)
    effect.build(b, s, merge)
    layers = [layer for layer, role in b.layers]
    if merge:
        merged = merge_layers(image, source, layers, effect, s)
        # (a preview merges a copy of the layer: the group is not told)
        if group is not None and not preview:
            set_group_source(group, merged)
        return [merged]
    if not preview:
        data = encode_settings(effect, s)
        for layer, role in b.layers:
            attach_json(layer, PARASITE_EFFECT, {'version': PARASITE_VERSION,
                                                 'effect': effect.name, 'role': role,
                                                 'settings': data})
            if not old_visible:
                layer.set_visible(False)
        if group is not None:
            set_group_source(group, source)
    return layers


def effect_settings_of(source, effect):
    """The settings of the effect as it is on source, or None."""
    group = effects_group(source)
    old = find_effect_layers(group, effect.name)
    if not old:
        return None
    return decode_settings(effect, (effect_info(old[0]) or {}).get('settings', {}))


def reapply_effects(image, source):
    group = effects_group(source)
    found = []
    if group is not None:
        for child in group.get_children():
            info = effect_info(child)
            if info is not None and info['effect'] not in found:
                found.append(info['effect'])
    if not found:
        raise LayerFXError('No effects found on this layer.')
    for name in found:
        effect = EFFECTS[name]
        s = effect_settings_of(source, effect)
        apply_effect(image, source, effect, s)
    return found


class SelectionKeeper:
    """Saves the selection and removes it while the effect is built, and
    restores it after; the context too."""

    def __init__(self, image):
        self.image = image

    def __enter__(self):
        Gimp.context_push()
        self.saved = None
        if not Gimp.Selection.is_empty(self.image):
            self.saved = Gimp.Selection.save(self.image)
        Gimp.Selection.none(self.image)
        return self

    def __exit__(self, *exc):
        try:
            if self.saved is not None:
                self.image.select_item(Gimp.ChannelOps.REPLACE, self.saved)
                self.image.remove_channel(self.saved)
            else:
                Gimp.Selection.none(self.image)
        finally:
            Gimp.context_pop()
        return False


def run_effect(image, source, effect, s):
    image.undo_group_start()
    try:
        with SelectionKeeper(image):
            layers = apply_effect(image, source, effect, s)
        selected = layers[0] if s.get('merge') else source
        image.set_selected_layers([selected])
    finally:
        image.undo_group_end()
    return layers


# ------------------------------------------------------------ the dialog

class Preview:
    """Builds the effect in the image while the dialog is open (with
    the undo history frozen), and removes it again."""

    def __init__(self, image, source, effect, config):
        self.image = image
        self.source = source
        self.effect = effect
        self.config = config
        self.layers = []
        self.hidden = []
        self.copy = None
        self.frozen = False
        self.pending = None

    def changed(self, config, pspec):
        if self.pending is None:
            self.pending = GLib.timeout_add(150, self.update)

    def update(self):
        self.pending = None
        self.clear()
        if not self.config.get_property('preview'):
            Gimp.displays_flush()
            return False
        if not self.frozen:
            self.image.undo_freeze()
            self.frozen = True
        try:
            s = settings_from_config(self.effect, self.config)
            group = effects_group(self.source)
            for layer in find_effect_layers(group, self.effect.name):
                if layer.get_visible():
                    layer.set_visible(False)
                    self.hidden.append(layer)
            source = self.source
            if s.get('merge'):
                self.copy = self.source.copy()
                parent = self.source.get_parent()
                self.image.insert_layer(self.copy, parent,
                                        self.image.get_item_position(self.source))
                if self.source.get_visible():
                    self.source.set_visible(False)
                    self.hidden.append(self.source)
                source = self.copy
            with SelectionKeeper(self.image):
                self.layers = apply_effect(self.image, source, self.effect, s, preview=True)
        except Exception:
            traceback.print_exc()
        Gimp.displays_flush()
        return False

    def clear(self):
        for layer in self.layers:
            if layer.is_valid():
                self.image.remove_layer(layer)
        self.layers = []
        if self.copy is not None and self.copy.is_valid():
            self.image.remove_layer(self.copy)
        self.copy = None
        for layer in self.hidden:
            if layer.is_valid():
                layer.set_visible(True)
        self.hidden = []

    def stop(self):
        if self.pending is not None:
            GLib.source_remove(self.pending)
            self.pending = None
        self.clear()
        if self.frozen:
            self.image.undo_thaw()
            self.frozen = False
        Gimp.displays_flush()


def follow_fill_type(config, widgets):
    """Makes the widgets of each fill type (a dict: type -> widget)
    sensitive only while that fill type is chosen. (The dialog's own
    gimp_procedure_dialog_set_sensitive_if_in () did nothing here.)"""
    def update(*args):
        chosen = config.get_property('fill-type')
        for value, widget in widgets.items():
            widget.set_sensitive(value == chosen)
    update()
    return config.connect('notify::fill-type', update)


def layout_dialog(dialog, config, effect):
    """Lays out the dialog as the original did; returns the handlers
    connected to config."""
    from gi.repository import Gtk
    name = effect.name
    handlers = []

    def columns(box_id, left, right):
        dialog.fill_box(box_id + '-left', left)
        dialog.fill_box(box_id + '-right', right)
        box = dialog.fill_box(box_id, [box_id + '-left', box_id + '-right'])
        box.set_orientation(Gtk.Orientation.HORIZONTAL)
        box.set_spacing(18)
        return box

    # sliders, as in the original, for the numbers with a short range
    for a in effect.args:
        if a.kind in ('double', 'int') and a.extra[1] - a.extra[0] <= 2000:
            dialog.get_spin_scale(a.name, 1.0)
    for radio in ('fill-type', 'source', 'direction'):
        if effect.arg(radio) is not None:
            dialog.get_widget(radio, GimpUi.IntRadioFrame.__gtype__)
    if name == 'bevel-emboss':
        dialog.fill_box('structure-box', ['style', 'depth', 'direction', 'size', 'soften',
                                          'surface-contour'])
        dialog.fill_frame('structure', 'structure-label', False, 'structure-box')
        dialog.fill_box('shading-box', ['angle', 'altitude', 'gloss-contour', 'highlight-mode',
                                        'highlight-color', 'highlight-opacity', 'shadow-mode',
                                        'shadow-color', 'shadow-opacity'])
        dialog.fill_frame('shading', 'shading-label', False, 'shading-box')
        dialog.fill_box('texture-box', ['pattern', 'invert', 'scale', 'tex-depth'])
        dialog.fill_frame('texture', 'use-texture', False, 'texture-box')
        columns('columns', ['structure', 'texture'], ['shading'])
        dialog.fill(['columns', 'merge', 'preview'])
    elif name == 'stroke':
        frames = {}
        for fill, contents in (('color', ['color']),
                               ('gradient', ['gradient', 'gradient-type', 'repeat', 'reverse',
                                             'center-x', 'center-y', 'angle', 'width']),
                               ('pattern', ['pattern', 'scale', 'interpolation'])):
            dialog.fill_box(fill + '-box', contents)
            frames[fill] = dialog.fill_frame(fill + '-frame', fill + '-label', False,
                                             fill + '-box')
        columns('columns', ['size', 'position', 'mode', 'opacity', 'fill-type', 'color-frame',
                            'pattern-frame'], ['gradient-frame'])
        dialog.fill(['columns', 'merge', 'preview'])
        handlers.append(follow_fill_type(config, frames))
    elif effect.arg('fill-type') is not None:
        boxes = {'color': dialog.fill_box('color-box', ['color']),
                 'gradient': dialog.fill_box('gradient-box', ['gradient'])}
        layout = [{'color': 'color-box', 'gradient': 'gradient-box'}.get(n, n)
                  for n in effect.layout]
        dialog.fill(layout + ['preview'])
        handlers.append(follow_fill_type(config, boxes))
    else:
        dialog.fill(effect.layout + ['preview'])
    return handlers


GimpUi = None


def show_dialog(procedure, config, effect, image, source):
    global GimpUi
    gi.require_version('GimpUi', '3.0')
    from gi.repository import GimpUi as _GimpUi
    GimpUi = _GimpUi
    GimpUi.init(PLUG_IN_BINARY)
    dialog = GimpUi.ProcedureDialog.new(procedure, config, effect.title)
    # labels for the frames
    for label_id, text in (('structure-label', 'Structure'), ('shading-label', 'Shading'),
                           ('color-label', 'Color'), ('gradient-label', 'Gradient'),
                           ('pattern-label', 'Pattern')):
        dialog.get_label(label_id, text, False, False)
    # Preview starts off, as in the original: building the effect can
    # take a while on large layers
    config.set_property('preview', False)
    handlers = layout_dialog(dialog, config, effect)
    preview = Preview(image, source, effect, config)
    handlers.append(config.connect('notify', preview.changed))
    try:
        ok = dialog.run()
    finally:
        for handler in handlers:
            config.disconnect(handler)
        preview.stop()
        dialog.destroy()
    return ok


# ------------------------------------------------------------ the plug-in

def error_values(procedure, status, message):
    return procedure.new_return_values(status, GLib.Error(message))


def run_procedure(procedure, run_mode, image, drawables, config, data):
    name = procedure.get_name()[len(PREFIX):]
    try:
        source = resolve_layer(image, drawables)
        if name == REAPPLY:
            if image.get_base_type() not in (Gimp.ImageBaseType.RGB, Gimp.ImageBaseType.GRAY):
                raise LayerFXError('Layer Effects work on RGB and grayscale images, not on '
                                   'indexed images (Image > Mode).')
            image.undo_group_start()
            try:
                with SelectionKeeper(image):
                    reapply_effects(image, source)
                image.set_selected_layers([source])
            finally:
                image.undo_group_end()
            Gimp.displays_flush()
            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)
        effect = EFFECTS[name]
        check_layer(image, source, effect)
        fill_color_defaults(effect, config)
        if run_mode == Gimp.RunMode.INTERACTIVE:
            existing = effect_settings_of(source, effect)
            if existing is not None:
                for a in effect.args:
                    if a.name != 'merge':
                        config.set_property(a.name, existing[a.name])
            if not show_dialog(procedure, config, effect, image, source):
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)
        s = settings_from_config(effect, config)
        run_effect(image, source, effect, s)
        Gimp.displays_flush()
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)
    except LayerFXError as e:
        if run_mode != Gimp.RunMode.NONINTERACTIVE:
            # GIMP would show a returned error as a "Calling error for
            # procedure ..."; the message alone says it better
            Gimp.message(str(e))
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)
        return error_values(procedure, Gimp.PDBStatusType.CALLING_ERROR, str(e))
    except Exception as e:
        traceback.print_exc()
        return error_values(procedure, Gimp.PDBStatusType.EXECUTION_ERROR,
                            'Layer Effects failed: %s' % e)


# the mnemonics of the dialog's own buttons (_Help, _Reset, _Cancel, _OK,
# _Load Saved Settings, _Save Settings) and of Preview
BUTTON_MNEMONICS = set('hrcolsv')
PREVIEW_LABEL = 'Pre_view'


def dialog_labels(effect):
    """The labels of the effect's arguments with mnemonics that differ
    from each other and from the buttons': the original's letter where it
    can be, else another letter of the label. A matching of labels to
    letters (Kuhn's algorithm, the labels in the order of the dialog, so
    that the first keep theirs), since the dialogs with many settings
    have hardly enough letters."""
    names = [n for n in effect.layout if effect.arg(n)] + \
        [a.name for a in effect.args if a.name not in effect.layout]
    choices = {}
    for name in names:
        label = effect.arg(name).label
        plain = label.replace('_', '')
        first = label.find('_')
        order = ([first] if first >= 0 else []) + list(range(len(plain)))
        seen = []
        for i in order:
            ch = plain[i].lower()
            if ch.isalpha() and ch not in BUTTON_MNEMONICS and ch not in [c for c, j in seen]:
                seen.append((ch, i))
        choices[name] = seen
    owner = {}          # letter -> name

    def assign(name, visited):
        for ch, i in choices[name]:
            if ch in visited:
                continue
            visited.add(ch)
            if ch not in owner or assign(owner[ch], visited):
                owner[ch] = name
                return True
        return False
    for name in names:
        assign(name, set())
    labels = {}
    for name in names:
        plain = effect.arg(name).label.replace('_', '')
        labels[name] = plain
        for ch, i in choices[name]:
            if owner.get(ch) == name:
                labels[name] = plain[:i] + '_' + plain[i:]
                break
    return labels


def make_choice(table):
    choice = Gimp.Choice.new()
    for i, entry in enumerate(table):
        choice.add(entry[0], i, entry[1].replace('_', ''), '')
    return choice


def add_argument(procedure, a, label):
    flags = GObject.ParamFlags.READWRITE
    if a.kind == 'color':
        color = Gegl.Color.new(a.extra[0])
        procedure.add_color_argument(a.name, label, a.blurb, True, color, flags)
    elif a.kind == 'double':
        procedure.add_double_argument(a.name, label, a.blurb, *a.extra, flags)
    elif a.kind == 'int':
        procedure.add_int_argument(a.name, label, a.blurb, *a.extra, flags)
    elif a.kind == 'boolean':
        procedure.add_boolean_argument(a.name, label, a.blurb, a.extra[0], flags)
    elif a.kind == 'choice':
        procedure.add_choice_argument(a.name, label, a.blurb, make_choice(a.extra[0]),
                                      a.extra[1], flags)
    elif a.kind == 'gradient':
        procedure.add_gradient_argument(a.name, label, a.blurb, False, None, True, flags)
    elif a.kind == 'pattern':
        procedure.add_pattern_argument(a.name, label, a.blurb, False, None, True, flags)


class LayerFX(Gimp.PlugIn):

    def do_set_i18n(self, name):
        return False

    def do_query_procedures(self):
        return [PREFIX + e.name for e in EFFECT_LIST] + [PREFIX + REAPPLY]

    def do_create_procedure(self, name):
        Gegl.init(None)
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN,
                                            run_procedure, None)
        effect_name = name[len(PREFIX):]
        if effect_name == REAPPLY:
            procedure.set_image_types('RGB*, GRAY*')
            procedure.set_menu_label('_Reapply Effects')
            procedure.set_documentation(
                'Reapply all effects previously applied to a layer.',
                'Rebuilds all effects of the layer with their settings, for example after '
                'the layer has been edited. Effects that were merged with the layer cannot be '
                'reapplied. Select the layer, its effects group or one of its effect layers.',
                name)
        else:
            effect = EFFECTS[effect_name]
            procedure.set_image_types(effect.image_types)
            procedure.set_menu_label(effect.menu_label)
            procedure.set_documentation(
                effect.blurb,
                effect.blurb + ' The effect is built as its own layer (or layers), in a '
                'pass-through layer group with the layer; its settings are kept with it for '
                'Reapply Effects.',
                name)
            labels = dialog_labels(effect)
            for a in effect.args:
                add_argument(procedure, a, labels[a.name])
            procedure.add_boolean_aux_argument('preview', PREVIEW_LABEL,
                                               'Show the effect in the image', False,
                                               GObject.ParamFlags.READWRITE)
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
        procedure.set_attribution(AUTHOR, COPYRIGHT, DATE)
        procedure.add_menu_path(IMAGE_MENU)
        procedure.add_menu_path(LAYERS_MENU)
        return procedure


if __name__ == '__main__':
    Gimp.main(LayerFX.__gtype__, sys.argv)
