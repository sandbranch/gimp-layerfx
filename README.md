# GIMP Layer Effects for GIMP 3

Layer styles for GIMP 3, as in other image editors: drop shadows, glows,
bevels, satin, strokes and overlays, each built as a layer of its own with
its own blend mode and opacity, next to the layer it belongs to. The
settings stay with the effect, so that the effects can be rebuilt after
the layer has changed (a text edited, a shape repainted).

This is a port of **GIMP Layer Effects** by **Jonathan Stipe**
(layerfx.2.8.py, 2008 to 2012), from the old GIMP Plugin Registry
(registry.gimp.org/node/186, mirrored at
[github.com/earl-kent/layerfx](https://github.com/earl-kent/layerfx)), to
GIMP 3 and Python 3. The original is kept unchanged in
[original/layerfx.2.8.py](original/layerfx.2.8.py). Like it, this port is
free software under the GNU General Public License, version 3 or later.

## The effects

All are in **Layer > Layer Effects** and in the context menu of the Layers
dialog (**Layer Effects**):

| Effect | Makes | Mode |
|---|---|---|
| Drop Shadow | a shadow below the layer, moved away from the light | Multiply |
| Inner Shadow | a shadow inside the layer's edge, from the edge or the centre | Multiply |
| Outer Glow | a glow around the layer, in a colour or a gradient | Screen |
| Inner Glow | a glow inside the edge, in a colour or a gradient | Screen |
| Bevel and Emboss | a highlight and a shadow layer: outer and inner bevel, emboss, pillow emboss, with a texture | Screen, Multiply |
| Satin | satin like shading inside the layer | Multiply |
| Stroke | an outline inside, centred on or outside the edge, in a colour, a gradient or a pattern | Normal |
| Color Overlay | a colour over the layer's shape | Normal |
| Gradient Overlay | a gradient over the layer's shape | Normal |
| Pattern Overlay | a pattern over the layer's shape | Normal |
| Reapply Effects | rebuilds all effects of the layer with their settings | |

Mode is the default blend mode. The options are those of the
original: opacity, blend mode (21 modes), size, spread or choke, contour
(12 curves), noise, angle and distance, knockout, and **Merge with
layer**, which merges the effect into the layer instead of making a
layer of its own (it cannot be reapplied then). **Preview** in each dialog
builds the effect in the image while the dialog is open.

## How the effects are built

The layer and its effect layers go into a layer group named
`<layer>-with-effects`, in **Pass Through** mode, so that each effect
blends with the image below it: a Multiply shadow darkens the background,
a Screen glow lightens it. (GIMP 3's own filters have a blend mode too,
but it blends the filter's result with the layer the filter is on: GIMP
3.2's Drop Shadow filter in Multiply mode leaves the background as it
was.) Effect layers are ordinary layers that can be painted on, masked,
hidden or moved.

Inside the group the effects are kept in this order, top to bottom:
Bevel and Emboss (highlight, then shadow), Stroke, Inner Shadow, Inner
Glow, Satin, Color Overlay, Gradient Overlay, Pattern Overlay, the layer,
an outside Stroke, Outer Glow, Drop Shadow. An effect applied again
replaces the old one where it is, also if you moved it.

The settings of each effect are stored on its layer (a parasite named
`layerfx-effect`, as JSON), and are saved in XCF files. Opening an
effect's dialog for a layer that has that effect shows its settings.
**Reapply Effects** rebuilds every effect of the layer with them, for
example after editing a text layer. Any of the layer, its group or one of
its effect layers can be selected for this, or for adding an effect.

The effects work on RGB and grayscale images of every precision (8, 16
and 32 bit integer, 16 and 32 bit floating point, linear or perceptual),
on layers with offsets, with layer masks (the mask is part of the shape)
and on text layers. Drop Shadow, Outer Glow, Bevel and Emboss, Satin and
Stroke need a layer with an alpha channel, as in the original; for a
layer without one they say so and change nothing.

## Differences from layerfx 2.8

- **One group per layer.** 2.8 wrapped the layer and the new effect in a
  new group (Normal mode) for each effect applied, so several effects
  nested groups in the order they were applied. Here there is one Pass
  Through group per layer, in a fixed order (see above).
- **Ramps without steps, in one go.** 2.8 built the gradual edges of
  shadows, glows and bevels by growing or shrinking the selection one
  pixel at a time and filling each step with the next grey, which is slow
  for large sizes and gives an 8-bit staircase. Here the same ramps come
  from a Euclidean distance transform of the layer's alpha
  (`gegl:distance-transform`), computed in floating point in the plug-in
  and written to the image once. They are straight lines through the
  corners of the old staircase: on discs and rectangles they are within
  0.22 of a step of the original on average, 0.66 of a step at most
  (tests/cases/15-ramp.py). An effect on a 12 megapixel layer takes about
  3 to 5 seconds. The effects are not clipped to the canvas, as the
  selection was.
- **Contours in floating point.** The contour curves are the original's
  points and tables; the smooth ones are computed with GIMP's curve
  algorithm (identical to GIMP 3.2's Curves, tested) and applied to the
  plain mask values, as 2.8 applied them to 8-bit masks. (GIMP 3's Curves
  would apply them to perceptual values instead.)
- **GIMP 3 means for the removed procedures.** `gegl:bump-map` replaces
  plug-in-bump-map, `gegl:noise-hsv` plug-in-hsv-noise,
  `gegl:gaussian-blur` plug-in-gauss-rle (with the same radius),
  `Gimp.GroupLayer` gimp-layer-group-new, and the bounds of the satin are
  computed instead of plug-in-autocrop-layer. Gradient glows map the
  gradient's colours (and alpha) directly instead of plug-in-gradmap.
- **Blend modes.** The 21 modes of the original are GIMP 3's modes of the
  same names (not the "legacy" ones); they blend in linear light, so
  results can look slightly different from GIMP 2.8.
- **Arguments.** Procedures are named `python-layerfx-drop-shadow` and so
  on (2.8: `python_layerfx_drop_shadow`, and a copy
  `python_layer_fx_drop_shadow` for the Layers dialog; GIMP 3 has one
  procedure with both menus). The blend mode, contour, source, style,
  direction, gradient type, repeat and interpolation are choices by name
  (`"multiply"`, `"gaussian"`, ...) instead of numbers. 2.8's colour
  argument that could also be a gradient name (glows) or a tuple
  (strokes) is split into `fill-type`, `color`, `gradient`,
  `gradient-type` and so on; these new arguments come after the old ones.
  The interpolation "Sinc (Lanczos3)" is NoHalo, which replaced Lanczos
  in GIMP 2.10.
- **Semi-transparent layers.** 2.8's partly selected fills gave uneven
  results for layers that are partly transparent throughout. Here the
  shape's edges are those of its alpha divided by its local maximum, and
  the effects that reach outside the layer take its alpha level: a layer
  at 50 % gets a shadow at 50 %. Knockout removes the shadow or glow under
  the whole layer (2.8 filled black through the layer's alpha, which only
  halves it under a layer at 50 %). For opaque layers with antialiased
  edges nothing changes.
- **Fixes.** A pattern stroke outside the layer is not cut off at the
  layer's bounds; a shaped gradient (angular, spherical, dimpled) in the
  Gradient Overlay is not applied twice to the alpha at the edges;
  merging keeps effects that reach out of the layer (GIMP 3 would clip
  Screen or Multiply layers to the layer below when merging down).
- **Reapply** finds the effects in the group by their parasites. 2.8
  stored the effect layer's name on the layer and looked it up among the
  image's top-level layers. Reapply keeps hidden effect layers hidden and
  the order you gave them; the group and the effect layers take the
  layer's new name (text layers are renamed after their text). The
  parasites are saved with the image (2.8's were not persistent).
- **Preview** starts off each time (it builds the effect, which takes a
  moment on large layers); the undo history is frozen meanwhile, and the
  preview layers are removed on Cancel. The whole effect is one step in
  the undo history.
- **Refusals** are messages, never tracebacks: an indexed image, a layer
  group that is not an effects group, a channel, or a layer without alpha
  for the effects that need one. A layer mask selected stands for its
  layer.
- **Noise** comes from `gegl:noise-hsv`, with a new random pattern each
  time the effect is built, as in 2.8.

## Install

The plug-in is the folder `layerfx/` with the Python file `layerfx.py` in
it. It needs GIMP 3 with Python 3 plug-ins; it is tested with GIMP 3.2.6,
the Flatpak org.gimp.GIMP from Flathub, which has them.

**GIMP 3 installed natively:** copy the folder into the `plug-ins` folder
of your GIMP profile and make the file executable, then restart GIMP:

    mkdir -p ~/.config/GIMP/3.2/plug-ins
    cp -r layerfx ~/.config/GIMP/3.2/plug-ins/
    chmod +x ~/.config/GIMP/3.2/plug-ins/layerfx/layerfx.py

On Windows the folder is `%APPDATA%\GIMP\3.2\plug-ins\`, on macOS
`~/Library/Application Support/GIMP/3.2/plug-ins/`. Edit > Preferences >
Folders > Plug-ins in GIMP shows the folders it reads.

**The Flatpak (org.gimp.GIMP):** it uses the same profile folder,
`~/.config/GIMP/3.2/plug-ins`, so the commands above work for it too.

The folder name and the file name must stay `layerfx`. Uninstall by
removing the folder.

## Tests

    tests/run.sh

runs GIMP without a window, with a throwaway profile in `tests/output/`
(your own GIMP profile and plug-ins are not used or changed), and prints
PASS or FAIL for each case; it exits non-zero if a case fails or the
plug-in printed a traceback or a warning. It needs no network and no
display. The cases (in `tests/cases/`) check:

- that every procedure is registered with the arguments of the original,
  in its order, with its ranges, defaults, menus and image types;
- the ramps against the original's grow-by-one-pixel loop, run with GIMP
  3's own Grow and Shrink, and the contour curves against GIMP's Curves;
- each effect on an opaque disc on a transparent layer: the layers made,
  their order, blend mode, opacity and size, and their pixels (the
  direction and distance of shadows, glows outside only and inner effects
  inside only, the three stroke positions, knockout, spread, contour,
  noise, satin, overlays only over the shape, the highlight and shadow of
  each bevel style on the right sides for the light, and effects blending
  with the image below);
- Merge with layer for every effect, with and without a layer mask;
- Reapply after the layer changed (the same settings, the new shape, the
  order kept), from the layer, its group or an effect layer, and after
  saving and loading an XCF;
- every precision in RGB and grayscale against a floating point result,
  layers with offsets, layers with masks (also switched off), layers in
  layer groups;
- every blend mode, contour, gradient type, repeat and interpolation, and
  every effect with its settings at the ends of their ranges;
- the preview (without the dialog): built, and the image exactly as
  before afterwards;
- the refusals, the selection and context being left as they were;
- a text layer, whose text is changed before Reapply (in a second GIMP
  that loads fonts: GIMP 3.2 can hang loading fonts, so a hang there is
  reported as SKIP);
- the time taken on a 1200 x 800 layer.

When a headless Chrome (or Chromium) and node 22 are there, `run.sh` also
runs `tests/gui/gui-test.sh`: GIMP on a Broadway display, driven through
[gimp-plugin-devtools](https://github.com/sandbranch/gimp-plugin-devtools)'
`gui/cdp.mjs` (expected next to this folder, or in
`$GIMP_PLUGIN_DEVTOOLS`). It opens the Drop Shadow dialog, turns Preview
on and presses OK (one shadow is made) or Cancel (the preview is
removed), opens it on a layer that has a drop shadow (the dialog shows
that shadow's settings), and presses Ctrl+Z after an effect (the image is
as before, after one undo). On Broadway the keys of a GIMP session
sometimes reach none of its windows; the undo session is then repeated
(up to 6 times), while a wrong result after an undo fails at once.
Screenshots are left in `tests/output/gui/`. `tests/gui/look.sh <effect>`
opens any effect's dialog and takes a screenshot of it.

    LFX_ONLY=stroke tests/run.sh   only the cases whose names contain "stroke"
    LFX_GUI=0 tests/run.sh         without the Broadway tests
    GIMP_FLATPAK=0 tests/run.sh    with a native gimp-console-3.2 or gimp-console

## License

GPL version 3 or later, see [COPYING](COPYING).

    GIMP Layer Effects
    Copyright (c) 2008 Jonathan Stipe
    Copyright 2026 David, port to GIMP 3
