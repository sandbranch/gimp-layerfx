# Helpers for the tests of Layer Effects, which run inside GIMP
# (tests/gimp-test.py): images with simple shapes, calling the
# procedures, reading pixels, and the list of cases.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
import builtins
import functools
import importlib.util
import json
import math
import os
import struct
import sys
import time
import traceback

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('Gegl', '0.4')
from gi.repository import Gimp, Gegl, Gio, GLib, GObject

print = functools.partial(builtins.print, flush=True)
Gegl.init(None)
PDB = Gimp.get_pdb()
SRC = os.environ.get('LFX_SRC', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.environ.get('LFX_OUT', os.path.join(SRC, 'tests', 'output'))
FMT = 'RGBA float'


def load_plugin_module():
    """The plug-in's own code, to test its parts (the ramps, the curves)
    directly."""
    path = os.path.join(SRC, 'layerfx', 'layerfx.py')
    spec = importlib.util.spec_from_file_location('layerfx_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LFX = load_plugin_module()

U8 = Gimp.Precision.U8_NON_LINEAR
U16 = Gimp.Precision.U16_LINEAR
FLOAT = Gimp.Precision.FLOAT_LINEAR

cases = []


def case(func):
    cases.append(func)
    return func


class Fail(Exception):
    pass


def check(cond, msg):
    if not cond:
        raise Fail(msg)


def approx(a, b, tol, what=''):
    check(abs(a - b) <= tol, '%s%s, expected %s (+-%s)' % (what + ' ' if what else '', a, b, tol))


# ---------------------------------------------------------------- images

def disc(cx, cy, r, aa=True):
    """The coverage of a disc, antialiased (4x4 samples per pixel) or not."""
    def cover(x, y):
        if not aa:
            return 1.0 if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r else 0.0
        n = 0
        for i in range(4):
            for j in range(4):
                if (x + (i + 0.5) / 4 - cx) ** 2 + (y + (j + 0.5) / 4 - cy) ** 2 <= r * r:
                    n += 1
        return n / 16.0
    return cover


def box(x0, y0, x1, y1):
    return lambda x, y: 1.0 if x0 <= x < x1 and y0 <= y < y1 else 0.0


def put(drawable, pixel, fmt=FMT):
    """Fills drawable with pixel(x, y) -> (r, g, b, a), in drawable
    coordinates."""
    w, h = drawable.get_width(), drawable.get_height()
    n = len(pixel(0, 0))
    data = bytearray()
    for y in range(h):
        for x in range(w):
            data += struct.pack('%df' % n, *pixel(x, y))
    buf = drawable.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, w, h), fmt if n == 4 else 'Y float', bytes(data))
    buf.flush()
    drawable.update(0, 0, w, h)


def new_image(w=160, h=160, base=Gimp.ImageBaseType.RGB, precision=U8, background=0.5):
    """An image with an opaque grey background layer (or none)."""
    image = Gimp.Image.new_with_precision(w, h, base, precision)
    if background is not None:
        itype = Gimp.ImageType.RGB_IMAGE if base == Gimp.ImageBaseType.RGB else \
            Gimp.ImageType.GRAY_IMAGE
        bg = Gimp.Layer.new(image, 'background', w, h, itype, 100, Gimp.LayerMode.NORMAL)
        image.insert_layer(bg, None, 0)
        put(bg, lambda x, y: (background, background, background, 1.0))
    return image


def shape_layer(image, shape, w=None, h=None, x=0, y=0, color=(0.2, 0.4, 0.8), name='disc',
                alpha=True):
    """A layer with shape(x, y) -> coverage as its alpha (in layer
    coordinates), filled with color."""
    w = w or image.get_width()
    h = h or image.get_height()
    gray = image.get_base_type() == Gimp.ImageBaseType.GRAY
    if alpha:
        itype = Gimp.ImageType.GRAYA_IMAGE if gray else Gimp.ImageType.RGBA_IMAGE
    else:
        itype = Gimp.ImageType.GRAY_IMAGE if gray else Gimp.ImageType.RGB_IMAGE
    layer = Gimp.Layer.new(image, name, w, h, itype, 100, Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, None, 0)
    layer.set_offsets(x, y)
    put(layer, lambda px, py: tuple(color) + (shape(px, py) if alpha else 1.0,))
    return layer


def disc_image(precision=U8, base=Gimp.ImageBaseType.RGB, aa=True, r=30, size=160,
               offset=(0, 0), layer_size=None, background=0.5):
    """An image with a grey background and a disc of radius r in the
    middle of a transparent layer."""
    image = new_image(size, size, base, precision, background)
    lw, lh = layer_size or (size, size)
    ox, oy = offset
    cx, cy = size / 2.0 - ox, size / 2.0 - oy
    layer = shape_layer(image, disc(cx, cy, r, aa), lw, lh, ox, oy)
    return image, layer


# ---------------------------------------------------------------- pixels

def read(drawable, fmt=FMT, rect=None):
    """The pixels of drawable (over rect, in drawable coordinates) as a
    dict of rows: px[y][x] = tuple."""
    w, h = drawable.get_width(), drawable.get_height()
    x0, y0, rw, rh = rect or (0, 0, w, h)
    n = {'RGBA float': 4, 'Y float': 1, 'YA float': 2, 'RGB float': 3}[fmt]
    raw = drawable.get_buffer().get(Gegl.Rectangle.new(x0, y0, rw, rh), 1.0, fmt,
                                    Gegl.AbyssPolicy.NONE)
    vals = struct.unpack('%df' % (rw * rh * n), raw)
    return [[vals[(y * rw + x) * n:(y * rw + x + 1) * n] for x in range(rw)] for y in range(rh)]


class Pixels:
    """The pixels of a layer, by image coordinates; transparent outside."""

    def __init__(self, layer, fmt=FMT):
        self.layer = layer
        ok, self.x, self.y = layer.get_offsets()
        self.w, self.h = layer.get_width(), layer.get_height()
        self.rows = read(layer, fmt)
        self.fmt = fmt

    def __call__(self, x, y):
        lx, ly = x - self.x, y - self.y
        if 0 <= lx < self.w and 0 <= ly < self.h:
            return self.rows[ly][lx]
        return (0.0,) * len(self.rows[0][0])

    def alpha(self, x, y):
        return self(x, y)[-1]


def visible(image):
    """The composite of the image, as a Pixels."""
    layer = Gimp.Layer.new_from_visible(image, image, 'visible')
    image.insert_layer(layer, None, 0)
    px = Pixels(layer)
    image.remove_layer(layer)
    return px


# ---------------------------------------------------------------- the plug-in

def proc(effect):
    return PDB.lookup_procedure(LFX.PREFIX + effect)


def color(css):
    c = Gegl.Color.new(css)
    return c


def run(effect, image, layer, run_mode=Gimp.RunMode.NONINTERACTIVE, **args):
    """Runs an effect; returns (status, message)."""
    p = proc(effect)
    config = p.create_config()
    config.set_property('run-mode', run_mode)
    config.set_property('image', image)
    config.set_core_object_array('drawables', [layer] if layer is not None else [])
    # (GIMP 3.2 leaves the colour arguments of this config transparent
    # black, without their defaults: the plug-in takes that for the
    # default, tests/cases/10-register.py)
    for key, value in args.items():
        key = key.replace('_', '-')
        if isinstance(value, str) and key.endswith('color'):
            value = color(value)
        config.set_property(key, value)
    values = p.run(config)
    status = values.index(0)
    # an error comes with its message
    msg = values.index(1) if status != Gimp.PDBStatusType.SUCCESS and values.length() > 1 else ''
    return status, msg


def ok(result):
    status, msg = result
    check(status == Gimp.PDBStatusType.SUCCESS, 'status %s %s' % (status.value_nick, msg))


def refused(result, words=()):
    status, msg = result
    check(status in (Gimp.PDBStatusType.CALLING_ERROR, Gimp.PDBStatusType.EXECUTION_ERROR),
          'expected an error, got %s' % status.value_nick)
    for w in words:
        check(w.lower() in str(msg).lower(), 'the message %r does not mention %r' % (msg, w))


def structure(image):
    """The layer tree as nested lists of names."""
    def walk(items):
        out = []
        for it in items:
            if it.is_group():
                out.append((it.get_name(), walk(it.get_children())))
            else:
                out.append(it.get_name())
        return out
    return walk(image.get_layers())


def by_name(image, name):
    layer = image.get_layer_by_name(name)
    check(layer is not None, 'no layer %r in %s' % (name, structure(image)))
    return layer


def info(layer):
    return LFX.effect_info(layer)


def rect(layer):
    ok_, x, y = layer.get_offsets()
    return (x, y, layer.get_width(), layer.get_height())


def mode_nick(layer):
    return layer.get_mode().value_nick


def load_cases(folder):
    for name in sorted(os.listdir(folder)):
        if name.endswith('.py'):
            path = os.path.join(folder, name)
            code = compile(open(path).read(), path, 'exec')
            exec(code, globals())


def run_all(only=''):
    failures = []
    t0 = time.time()
    for func in cases:
        name = func.__name__.replace('_', '-')
        if only and only not in name:
            continue
        t = time.time()
        for image in Gimp.get_images():
            image.delete()
        try:
            func()
            print('LFX PASS %s (%.1f s)' % (name, time.time() - t))
        except Fail as e:
            failures.append(name)
            print('LFX FAIL %s: %s' % (name, e))
        except Exception as e:
            failures.append(name)
            print('LFX FAIL %s: %s' % (name, e))
            traceback.print_exc()
    for image in Gimp.get_images():
        image.delete()
    print('LFX cases: %d in %.0f s' % (len([c for c in cases if not only or only in
                                           c.__name__.replace('_', '-')]), time.time() - t0))
    print('LFX failures: %d' % len(failures))


def srgb_of(c):
    """The sRGB (perceptual) components of a GeglColor, 0..1."""
    rgba = c.get_rgba()

    def enc(v):
        return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return (enc(rgba.red), enc(rgba.green), enc(rgba.blue), rgba.alpha)


CX = CY = 80        # the centre of the disc of disc_image ()


def at(r, degrees, cx=CX, cy=CY):
    """The pixel whose centre is nearest to the point at distance r from
    the centre, in a direction given in degrees counter-clockwise from the
    right (y points down in images)."""
    a = math.radians(degrees)
    return (int(round(cx + r * math.cos(a) - 0.5)), int(round(cy - r * math.sin(a) - 0.5)))


def arc_mean(px, r0, r1, d0, d1, channel=-1):
    """The mean of a channel over the part of a ring between the
    directions d0 and d1 (degrees)."""
    vals = []
    for k in range(9):
        d = d0 + (d1 - d0) * k / 8.0
        for i in range(5):
            x, y = at(r0 + (r1 - r0) * i / 4.0, d)
            vals.append(px(x, y)[channel])
    return sum(vals) / len(vals)


def std(values):
    m = sum(values) / len(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def children(image, group='disc-with-effects'):
    g = by_name(image, group)
    return [c.get_name() for c in g.get_children()]


def band(px, r0, r1, cx=CX, cy=CY):
    """The alphas of the pixels whose centres are between r0 and r1 from
    (cx, cy)."""
    out = []
    for y in range(int(cy - r1) - 1, int(cy + r1) + 2):
        for x in range(int(cx - r1) - 1, int(cx + r1) + 2):
            r = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            if r0 <= r <= r1:
                out.append(px.alpha(x, y))
    return out
