# What the effects refuse, with a message; and what they leave alone.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later

NEED_ALPHA = ['drop-shadow', 'outer-glow', 'bevel-emboss', 'satin', 'stroke']
NO_ALPHA_OK = ['inner-shadow', 'inner-glow', 'color-overlay', 'gradient-overlay',
               'pattern-overlay']


def opaque_layer_image():
    image = new_image()
    layer = shape_layer(image, None, 100, 100, 30, 30, name='photo', alpha=False)
    return image, layer


@case
def needs_alpha_channel():
    for effect in NEED_ALPHA:
        image, layer = opaque_layer_image()
        refused(run(effect, image, layer), ['alpha channel'])
        check(structure(image) == ['photo', 'background'], '%s changed the image: %s'
              % (effect, structure(image)))
    for effect in NO_ALPHA_OK:
        image, layer = opaque_layer_image()
        ok(run(effect, image, layer))
    # an inner glow on a layer without alpha: along its edges
    image, layer = opaque_layer_image()
    ok(run('inner-glow', image, layer, size=6))
    px = Pixels(by_name(image, 'photo-innerglow'))
    check(px.alpha(31, 80) > 0.5 and px.alpha(80, 80) < 0.01, 'no glow along the edges')


@case
def refuses_indexed_groups_channels():
    image, layer = disc_image()
    image.convert_indexed(Gimp.ConvertDitherType.NONE, Gimp.ConvertPaletteType.GENERATE, 16,
                          False, False, '')
    refused(run('color-overlay', image, image.get_layers()[0]), ['indexed'])
    refused(run('reapply-effects', image, image.get_layers()[0]), ['indexed'])
    image, layer = disc_image()
    group = Gimp.GroupLayer.new(image, 'group')
    image.insert_layer(group, None, 0)
    image.reorder_item(layer, group, 0)
    refused(run('drop-shadow', image, group), ['layer group'])
    channel = Gimp.Channel.new(image, 'channel', 160, 160, 50.0, color('red'))
    image.insert_channel(channel, None, 0)
    refused(run('drop-shadow', image, channel), ['channels'])
    image, layer = disc_image()
    refused(run('drop-shadow', image, None), ['one layer'])


@case
def mask_or_effect_layer_stands_for_the_layer():
    image, layer = disc_image()
    mask = layer.create_mask(Gimp.AddMaskType.WHITE)
    layer.add_mask(mask)
    ok(run('drop-shadow', image, mask))
    check(children(image) == ['disc', 'disc-dropshadow'], 'layers %s' % children(image))
    ok(run('stroke', image, by_name(image, 'disc-dropshadow')))
    check(children(image) == ['disc-stroke', 'disc', 'disc-dropshadow'],
          'layers %s' % children(image))
    ok(run('inner-glow', image, by_name(image, 'disc-with-effects')))
    check(children(image) == ['disc-stroke', 'disc-innerglow', 'disc', 'disc-dropshadow'],
          'layers %s' % children(image))


@case
def keeps_selection_and_context():
    image, layer = disc_image()
    image.select_rectangle(Gimp.ChannelOps.REPLACE, 10, 20, 50, 40)
    Gimp.context_set_foreground(color('#123456'))
    Gimp.context_set_pattern(Gimp.Pattern.get_by_name('Wood'))
    fg = srgb_of(Gimp.context_get_foreground())
    for effect in ('drop-shadow', 'stroke', 'gradient-overlay', 'pattern-overlay', 'bevel-emboss'):
        ok(run(effect, image, layer, pattern=Gimp.Pattern.get_by_name('Pine'))
           if effect == 'pattern-overlay' else run(effect, image, layer))
        bounds = Gimp.Selection.bounds(image)
        check(tuple(bounds)[1:] == (True, 10, 20, 60, 60), '%s: selection %s' % (effect, bounds))
        for a, b in zip(srgb_of(Gimp.context_get_foreground()), fg):
            approx(a, b, 1e-4, '%s: foreground' % effect)
        check(Gimp.context_get_pattern().get_name() == 'Wood', '%s: pattern' % effect)
    # and no channels were left behind
    check(len(image.get_channels()) == 0, 'channels %s' % image.get_channels())
