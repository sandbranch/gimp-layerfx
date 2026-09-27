# Every procedure is registered with the arguments of the original, in
# its order, with its ranges and defaults.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later

EXPECTED_ARGS = {
    'drop-shadow': ['color', 'opacity', 'contour', 'noise', 'mode', 'spread', 'size',
                    'offset-angle', 'offset-distance', 'knockout', 'merge'],
    'inner-shadow': ['color', 'opacity', 'contour', 'noise', 'mode', 'source', 'choke', 'size',
                     'offset-angle', 'offset-distance', 'merge'],
    'outer-glow': ['color', 'opacity', 'contour', 'noise', 'mode', 'spread', 'size', 'knockout',
                   'merge', 'fill-type', 'gradient'],
    'inner-glow': ['color', 'opacity', 'contour', 'noise', 'mode', 'source', 'choke', 'size',
                   'merge', 'fill-type', 'gradient'],
    'bevel-emboss': ['style', 'depth', 'direction', 'size', 'soften', 'angle', 'altitude',
                     'gloss-contour', 'highlight-color', 'highlight-mode', 'highlight-opacity',
                     'shadow-color', 'shadow-mode', 'shadow-opacity', 'surface-contour',
                     'use-texture', 'pattern', 'scale', 'tex-depth', 'invert', 'merge'],
    'satin': ['color', 'opacity', 'mode', 'offset-angle', 'offset-distance', 'size', 'contour',
              'invert', 'merge'],
    'stroke': ['color', 'opacity', 'mode', 'size', 'position', 'merge', 'fill-type', 'gradient',
               'gradient-type', 'repeat', 'reverse', 'center-x', 'center-y', 'angle', 'width',
               'pattern', 'scale', 'interpolation'],
    'color-overlay': ['color', 'opacity', 'mode', 'merge'],
    'gradient-overlay': ['gradient', 'gradient-type', 'repeat', 'reverse', 'opacity', 'mode',
                         'center-x', 'center-y', 'angle', 'width', 'merge'],
    'pattern-overlay': ['pattern', 'opacity', 'mode', 'scale', 'interpolation', 'merge'],
    'reapply-effects': [],
}

# name: (default, minimum, maximum) from the original's registration and
# dialogs
EXPECTED_VALUES = {
    'drop-shadow': {'opacity': (75.0, 0.0, 100.0), 'contour': ('linear',), 'noise': (0.0, 0.0, 100.0),
                    'mode': ('multiply',), 'spread': (0.0, 0.0, 100.0), 'size': (5, 0, 250),
                    'offset-angle': (120.0, -180.0, 180.0), 'offset-distance': (5.0, 0.0, 30000.0),
                    'knockout': (False,), 'merge': (False,), 'color': ((0, 0, 0, 1),)},
    'inner-shadow': {'opacity': (75.0, 0.0, 100.0), 'mode': ('multiply',), 'source': ('edge',),
                     'choke': (0.0, 0.0, 100.0), 'size': (5, 0, 250),
                     'offset-angle': (120.0, -180.0, 180.0), 'offset-distance': (5.0, 0.0, 30000.0),
                     'color': ((0, 0, 0, 1),)},
    'outer-glow': {'opacity': (75.0, 0.0, 100.0), 'mode': ('screen',), 'spread': (0.0, 0.0, 100.0),
                   'size': (5, 0, 250), 'fill-type': ('color',),
                   'color': ((1.0, 1.0, 190 / 255.0, 1),)},
    'inner-glow': {'opacity': (75.0, 0.0, 100.0), 'mode': ('screen',), 'source': ('edge',),
                   'choke': (0.0, 0.0, 100.0), 'size': (5, 0, 250),
                   'color': ((1.0, 1.0, 190 / 255.0, 1),)},
    'bevel-emboss': {'style': ('outer-bevel',), 'depth': (3, 1, 65), 'direction': ('up',),
                     'size': (5, 0, 250), 'soften': (0, 0, 16), 'angle': (120.0, -180.0, 180.0),
                     'altitude': (30.0, 0.0, 90.0), 'gloss-contour': ('linear',),
                     'highlight-mode': ('screen',), 'highlight-opacity': (75.0, 0.0, 100.0),
                     'shadow-mode': ('multiply',), 'shadow-opacity': (75.0, 0.0, 100.0),
                     'surface-contour': ('linear',), 'use-texture': (False,),
                     'scale': (100.0, 1.0, 1000.0), 'tex-depth': (100.0, -1000.0, 1000.0),
                     'invert': (False,), 'highlight-color': ((1, 1, 1, 1),),
                     'shadow-color': ((0, 0, 0, 1),)},
    'satin': {'opacity': (75.0, 0.0, 100.0), 'mode': ('multiply',),
              'offset-angle': (19.0, -180.0, 180.0), 'offset-distance': (11.0, 0.0, 30000.0),
              'size': (14, 0, 250), 'contour': ('gaussian',), 'invert': (True,),
              'color': ((0, 0, 0, 1),)},
    'stroke': {'opacity': (100.0, 0.0, 100.0), 'mode': ('normal',), 'size': (3, 1, 250),
               'position': (50.0, 0.0, 100.0), 'fill-type': ('color',),
               'gradient-type': ('linear',), 'repeat': ('none',), 'reverse': (False,),
               'angle': (90.0, -180.0, 180.0), 'width': (0.0, 0.0, 262144.0),
               'scale': (100.0, 1.0, 1000.0), 'interpolation': ('none',),
               'color': ((1, 0, 0, 1),)},
    'color-overlay': {'opacity': (100.0, 0.0, 100.0), 'mode': ('normal',),
                      'color': ((1, 1, 1, 1),)},
    'gradient-overlay': {'gradient-type': ('linear',), 'repeat': ('none',), 'reverse': (False,),
                         'opacity': (100.0, 0.0, 100.0), 'mode': ('normal',),
                         'center-x': (0.0, 0.0, 262144.0), 'center-y': (0.0, 0.0, 262144.0),
                         'angle': (90.0, -180.0, 180.0), 'width': (10.0, 0.0, 262144.0)},
    'pattern-overlay': {'opacity': (100.0, 0.0, 100.0), 'mode': ('normal',),
                        'scale': (100.0, 1.0, 1000.0), 'interpolation': ('none',)},
}

MENU_LABELS = {
    'drop-shadow': '_Drop Shadow...', 'inner-shadow': 'I_nner Shadow...',
    'outer-glow': '_Outer Glow...', 'inner-glow': '_Inner Glow...',
    'bevel-emboss': '_Bevel and Emboss...', 'satin': '_Satin...', 'stroke': 'S_troke...',
    'color-overlay': '_Color Overlay...', 'gradient-overlay': '_Gradient Overlay...',
    'pattern-overlay': '_Pattern Overlay...', 'reapply-effects': '_Reapply Effects',
}

NEEDS_ALPHA = ('drop-shadow', 'outer-glow', 'bevel-emboss', 'satin', 'stroke')


@case
def registered():
    for effect, expected in EXPECTED_ARGS.items():
        p = proc(effect)
        check(p is not None, '%s is not registered' % effect)
        names = [a.get_name() for a in p.get_arguments()]
        check(names == ['run-mode', 'image', 'drawables'] + expected,
              '%s: arguments %s' % (effect, names))
        check(p.get_menu_label() == MENU_LABELS[effect],
              '%s: menu label %r' % (effect, p.get_menu_label()))
        paths = p.get_menu_paths()
        check('<Image>/Layer/La_yer Effects' in paths and '<Layers>/_Layer Effects' in paths,
              '%s: menu paths %s' % (effect, paths))
        types = p.get_image_types()
        want = 'RGBA, GRAYA' if effect in NEEDS_ALPHA else 'RGB*, GRAY*'
        check(types == want, '%s: image types %r' % (effect, types))
        check('Jonathan Stipe' in p.get_authors(), '%s: authors %r' % (effect, p.get_authors()))
        # Preview is a setting of the dialog only, not an argument
        check('preview' not in names, '%s: preview is an argument' % effect)


@case
def defaults_and_ranges():
    for effect, values in EXPECTED_VALUES.items():
        p = proc(effect)
        specs = {a.get_name(): a for a in p.get_arguments()}
        for name, expected in values.items():
            spec = specs[name]
            default = spec.get_default_value()
            if name.endswith('color'):
                # the colour defaults are only in the plug-in's own table
                # (GIMP 3.2 does not report them to other plug-ins)
                c = Gegl.Color.new(LFX.EFFECTS[effect].arg(name).extra[0])
                got = srgb_of(c)
                for g_, e_ in zip(got, expected[0]):
                    approx(g_, e_, 0.002, '%s %s' % (effect, name))
                continue
            if isinstance(expected[0], str):
                check(default == expected[0], '%s %s: default %r' % (effect, name, default))
                continue
            if isinstance(expected[0], bool):
                check(default == expected[0], '%s %s: default %r' % (effect, name, default))
                continue
            check(default == expected[0], '%s %s: default %r' % (effect, name, default))
            check(spec.minimum == expected[1] and spec.maximum == expected[2],
                  '%s %s: range %r..%r' % (effect, name, spec.minimum, spec.maximum))


@case
def colour_defaults():
    # a config made by another plug-in has the colours transparent black
    # (GIMP 3.2); the effects then use their defaults
    config = proc('outer-glow').create_config()
    rgba = config.get_property('color').get_rgba()
    print('LFX INFO the colour of a new config: %s' % ((rgba.red, rgba.green, rgba.blue,
                                                        rgba.alpha),))
    for effect, name, want in (('drop-shadow', 'disc-dropshadow', (0.0, 0.0, 0.0)),
                               ('outer-glow', 'disc-outerglow', (1.0, 1.0, 190 / 255.0)),
                               ('stroke', 'disc-stroke', (1.0, 0.0, 0.0))):
        image, layer = disc_image()
        ok(run(effect, image, layer))
        px = Pixels(by_name(image, name))
        got = None
        for x in range(0, 160):
            p = px(x, CY)
            if p[3] > 0.5:
                got = p
                break
        check(got is not None, '%s: no pixels' % effect)
        c = Gegl.Color.new('black')
        c.set_rgba(got[0], got[1], got[2], 1.0)
        for g_, w_ in zip(srgb_of(c)[:3], want):
            approx(g_, w_, 0.01, '%s: colour' % effect)
