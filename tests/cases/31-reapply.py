# Reapply Effects, replacing an effect, and the order of the effects.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later

CANONICAL = ['disc-highlight', 'disc-shadow', 'disc-stroke', 'disc-innershadow',
             'disc-innerglow', 'disc-satin', 'disc-color', 'disc-gradient', 'disc-pattern',
             'disc', 'disc-outerglow', 'disc-dropshadow']


def settings_of(image):
    return {c.get_name(): info(c)['settings'] for c in
            by_name(image, 'disc-with-effects').get_children() if info(c)}


@case
def reapply_after_editing():
    image, layer = disc_image()
    ok(run('drop-shadow', image, layer, size=8, offset_distance=10.0, offset_angle=90.0,
           opacity=60.0, color='#400000'))
    ok(run('stroke', image, layer, size=3, position=100.0, color='#0000ff'))
    ok(run('inner-glow', image, layer, size=6))
    order = children(image)
    settings = settings_of(image)
    shadow_before = Pixels(by_name(image, 'disc-dropshadow'))
    # the layer becomes a square
    put(layer, lambda x, y: (0.2, 0.4, 0.8, box(50, 50, 110, 110)(x, y)))
    ok(run('reapply-effects', image, layer))
    check(children(image) == order, 'order %s, was %s' % (children(image), order))
    check(settings_of(image) == settings, 'the settings changed')
    shadow = by_name(image, 'disc-dropshadow')
    approx(shadow.get_opacity(), 60.0, 1e-6, 'opacity')
    px = Pixels(shadow)
    # below the square's lower right corner, where the disc had no shadow
    check(px.alpha(104, 114) > 0.99, 'no shadow of the square: %.3f' % px.alpha(104, 114))
    check(shadow_before.alpha(104, 114) < 0.01, 'the test point was in the old shadow')
    stroke = Pixels(by_name(image, 'disc-stroke'))
    check(stroke.alpha(111, 80) > 0.9 and stroke.alpha(100, 80) < 0.01, 'stroke not rebuilt')
    check(image.get_selected_layers() == [layer], 'selected %s' % image.get_selected_layers())


@case
def reapply_from_group_or_effect_layer():
    for pick in ('disc-with-effects', 'disc-dropshadow', 'disc-stroke'):
        image, layer = disc_image()
        ok(run('drop-shadow', image, layer))
        ok(run('stroke', image, layer))
        put(layer, lambda x, y: (0.2, 0.4, 0.8, box(50, 50, 110, 110)(x, y)))
        ok(run('reapply-effects', image, by_name(image, pick)))
        px = Pixels(by_name(image, 'disc-stroke'))
        check(px.alpha(111, 80) > 0.5, 'from %s: the stroke was not rebuilt' % pick)


@case
def reapply_keeps_hidden_and_moved_layers():
    image, layer = disc_image()
    ok(run('color-overlay', image, layer))
    ok(run('inner-glow', image, layer))
    ok(run('drop-shadow', image, layer))
    by_name(image, 'disc-dropshadow').set_visible(False)
    group = by_name(image, 'disc-with-effects')
    # the user puts the colour overlay above the glow
    image.reorder_item(by_name(image, 'disc-color'), group, 0)
    order = children(image)
    check(order == ['disc-color', 'disc-innerglow', 'disc', 'disc-dropshadow'], 'order %s' % order)
    ok(run('reapply-effects', image, layer))
    check(children(image) == order, 'order %s, was %s' % (children(image), order))
    check(not by_name(image, 'disc-dropshadow').get_visible(), 'the hidden shadow is shown')


@case
def reapply_without_effects():
    image, layer = disc_image()
    refused(run('reapply-effects', image, layer), ['no effects'])
    check(structure(image) == ['disc', 'background'], 'layers %s' % structure(image))


@case
def reapplying_an_effect_replaces_it():
    image, layer = disc_image()
    ok(run('drop-shadow', image, layer))
    ok(run('inner-glow', image, layer))
    ok(run('drop-shadow', image, layer, opacity=40.0, size=12))
    check(children(image) == ['disc-innerglow', 'disc', 'disc-dropshadow'],
          'layers %s' % children(image))
    shadow = by_name(image, 'disc-dropshadow')
    approx(shadow.get_opacity(), 40.0, 1e-6, 'opacity')
    check(info(shadow)['settings']['size'] == 12, 'settings %s' % info(shadow)['settings'])
    # the stroke moves from above the layer to below it
    ok(run('stroke', image, layer, position=50.0))
    ok(run('stroke', image, layer, position=100.0))
    check(children(image) == ['disc-innerglow', 'disc', 'disc-stroke', 'disc-dropshadow'],
          'layers %s' % children(image))


@case
def effects_in_order():
    image, layer = disc_image()
    for effect in ('satin', 'drop-shadow', 'color-overlay', 'bevel-emboss', 'pattern-overlay',
                   'inner-shadow', 'outer-glow', 'stroke', 'gradient-overlay', 'inner-glow'):
        ok(run(effect, image, layer))
    check(children(image) == CANONICAL, 'layers %s' % children(image))
    ok(run('reapply-effects', image, layer))
    check(children(image) == CANONICAL, 'after reapply: %s' % children(image))
    # applying one of them again keeps its place
    ok(run('satin', image, layer, opacity=30.0))
    check(children(image) == CANONICAL, 'after satin again: %s' % children(image))


@case
def settings_survive_saving():
    image, layer = disc_image()
    ok(run('bevel-emboss', image, layer, style='pillow-emboss', depth=7, highlight_color='#ffe000'))
    ok(run('outer-glow', image, layer, fill_type='gradient',
           gradient=Gimp.Gradient.get_by_name('Golden')))
    path = os.path.join(OUT, 'saved.xcf')
    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(path), None)
    loaded = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(path))
    group = loaded.get_layer_by_name('disc-with-effects')
    check(group is not None and group.get_mode() == Gimp.LayerMode.PASS_THROUGH, 'group')
    hl = loaded.get_layer_by_name('disc-highlight')
    s = info(hl)['settings']
    check(s['style'] == 'pillow-emboss' and s['depth'] == 7, 'settings %s' % s)
    check(info(loaded.get_layer_by_name('disc-outerglow'))['settings']['gradient'] == 'Golden',
          'the gradient was not kept')
    source = loaded.get_layer_by_name('disc')
    put(source, lambda x, y: (0.2, 0.4, 0.8, box(50, 50, 110, 110)(x, y)))
    ok(run('reapply-effects', loaded, source))
    px = Pixels(loaded.get_layer_by_name('disc-outerglow'))
    check(px.alpha(112, 112) > 0.3, 'the glow was not rebuilt for the square')
