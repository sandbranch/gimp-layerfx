# Runs inside GIMP on a Broadway display (tests/gui/start.sh). Opens an
# image with a grey background and a disc, then, by LFX_GUI_MODE:
#
#   dialog  opens the dialog of the effect LFX_GUI_EFFECT (with
#           LFX_GUI_EXISTING=1 on a layer that has the effect already, with
#           an opacity of 44 in its stored settings); when it is closed,
#           writes the status, the layers and their opacities to
#           LFX_OUT/result.txt
#   undo    applies the effect without a dialog and writes the same
#   refuse  runs Drop Shadow interactively on a layer without an alpha
#           channel, writes the status to LFX_OUT/result.txt and waits
#           for LFX_OUT/seen (for a screenshot of the message)
#
# After dialog and undo it waits until the layers change (the test
# presses Ctrl+Z) or LFX_OUT/undone exists, and writes the layers and
# whether the disc's pixels are as before to LFX_OUT/undo.txt. Then it
# quits GIMP.
#
# Copyright 2026 David
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import struct
import time

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('Gegl', '0.4')
from gi.repository import Gimp, Gegl

out = os.environ['LFX_OUT']
mode = os.environ.get('LFX_GUI_MODE', 'dialog')
effect = os.environ.get('LFX_GUI_EFFECT', 'drop-shadow')
W, H = 360, 260


def structure(items):
    names = []
    for it in items:
        if it.is_group():
            names.append('%s[%s]' % (it.get_name(), ','.join(structure(it.get_children()))))
        else:
            names.append(it.get_name())
    return names


def pixels(layer):
    w, h = layer.get_width(), layer.get_height()
    return layer.get_buffer().get(Gegl.Rectangle.new(0, 0, w, h), 1.0, 'RGBA float',
                                  Gegl.AbyssPolicy.NONE)


def write(name, lines):
    with open(os.path.join(out, name + '.tmp'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    os.rename(os.path.join(out, name + '.tmp'), os.path.join(out, name))


image = Gimp.Image.new(W, H, Gimp.ImageBaseType.RGB)
bg = Gimp.Layer.new(image, 'background', W, H, Gimp.ImageType.RGB_IMAGE, 100,
                    Gimp.LayerMode.NORMAL)
image.insert_layer(bg, None, 0)
grey = Gegl.Color.new('#b0b0b0')
Gimp.context_set_foreground(grey)
bg.edit_fill(Gimp.FillType.FOREGROUND)
disc = Gimp.Layer.new(image, 'disc', W, H, Gimp.ImageType.RGB_IMAGE if mode == 'refuse'
                      else Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
image.insert_layer(disc, None, 0)
data = bytearray()
for y in range(H):
    for x in range(W):
        n = sum(1 for i in range(4) for j in range(4)
                if (x + (i + 0.5) / 4 - W / 2) ** 2 + (y + (j + 0.5) / 4 - H / 2) ** 2 <= 70 ** 2)
        data += struct.pack('4f', 0.1, 0.35, 0.8, n / 16.0)
buf = disc.get_buffer()
# (for the layer without alpha, the alpha is dropped)
buf.set(Gegl.Rectangle.new(0, 0, W, H), 'RGBA float', bytes(data))
buf.flush()
image.clean_all()
display = Gimp.Display.new(image)
Gimp.displays_flush()
pdb = Gimp.get_pdb()


def present():
    """Brings the image window to the front (on Broadway its title cannot
    be clicked: it opens centred on the page's top left corner)."""
    proc = pdb.lookup_procedure('gimp-display-present')
    config = proc.create_config()
    config.set_property('display', display)
    proc.run(config)


if mode == 'refuse':
    proc = pdb.lookup_procedure('python-layerfx-drop-shadow')
    config = proc.create_config()
    config.set_property('run-mode', Gimp.RunMode.INTERACTIVE)
    config.set_property('image', image)
    config.set_core_object_array('drawables', [disc])
    status = proc.run(config).index(0)
    write('result.txt', ['status %s' % status.value_nick,
                         'layers %s' % ' '.join(structure(image.get_layers()))])
    t = time.time()
    while not os.path.exists(os.path.join(out, 'seen')) and time.time() - t < 60:
        time.sleep(0.5)
elif mode in ('dialog', 'undo'):
    before = pixels(disc)
    proc = pdb.lookup_procedure('python-layerfx-' + effect)
    if os.environ.get('LFX_GUI_EXISTING') == '1':
        config = proc.create_config()
        config.set_property('run-mode', Gimp.RunMode.NONINTERACTIVE)
        config.set_property('image', image)
        config.set_core_object_array('drawables', [disc])
        config.set_property('color', Gegl.Color.new('black'))
        config.set_property('opacity', 33.0)
        proc.run(config)
        for layer in disc.get_parent().get_children():
            p = layer.get_parasite('layerfx-effect')
            if p is not None:
                info = json.loads(bytes(p.get_data()).decode())
                info['settings']['opacity'] = 44.0
                layer.attach_parasite(Gimp.Parasite.new('layerfx-effect', p.get_flags(),
                                                        list(json.dumps(info).encode())))
    config = proc.create_config()
    config.set_property('run-mode', Gimp.RunMode.INTERACTIVE if mode == 'dialog'
                        else Gimp.RunMode.NONINTERACTIVE)
    config.set_property('image', image)
    config.set_core_object_array('drawables', [disc])
    result = proc.run(config)
    status = result.index(0)
    Gimp.displays_flush()
    present()
    opacities = ['%s=%.1f' % (l.get_name(), l.get_opacity())
                 for l in (disc.get_parent().get_children() if disc.get_parent() else [])]
    write('result.txt', ['status %s' % status.value_nick,
                         'layers %s' % ' '.join(structure(image.get_layers())),
                         'opacity %s' % ' '.join(opacities)])
    # the layers as soon as they change (the test presses Ctrl+Z until
    # they do), or when the test is done; the window is presented again
    # and again meanwhile, for the keyboard focus
    applied = structure(image.get_layers())
    t = time.time()
    n = 0
    while (structure(image.get_layers()) == applied and time.time() - t < 60 and
           not os.path.exists(os.path.join(out, 'undone'))):
        if n % 3 == 0:
            present()
        n += 1
        time.sleep(0.3)
    time.sleep(1.0)
    layers = image.get_layers()
    same = len(layers) == 2 and layers[0].get_name() == 'disc' and pixels(layers[0]) == before
    write('undo.txt', ['layers %s' % ' '.join(structure(layers)),
                       'pixels %s' % ('same' if same else 'different')])

quit_proc = pdb.lookup_procedure('gimp-quit')
quit_config = quit_proc.create_config()
quit_config.set_property('force', True)
quit_proc.run(quit_config)
