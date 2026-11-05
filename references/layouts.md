# Layouts and slot sizes

How to find the box a fragment fills and pick a viewBox for it. Legibility rules are in
[fragment-contract.md](fragment-contract.md) section 6.

## Measure your slot

1. Open the slide in a browser at the deck's stage size (or with the deck's own scaling active).
2. In devtools, select the container the fragment will live in, or run in the console:
   ```js
   const r = document.querySelector('<selector of the target container>').getBoundingClientRect();
   [r.width, r.height]
   ```
3. If the deck scales its stage to the window (most do), convert to stage pixels:
   `stage_px = measured_px * stage_width / stage_element.getBoundingClientRect().width`.
4. Record `width x height` in stage pixels.
5. Pick a viewBox with the same aspect ratio. Using the slot size itself (scale 1.0) keeps the
   maths trivial.
6. Text scale factor `s = rendered_width / viewBox_width`. Every font size in the viewBox times `s`
   must meet the contract minimum. Pass `rendered_width` to `check_fragment.py --rendered-width`.

If the slot does not exist yet, use the table below, build the slide with an empty box of that
size, then measure.

## Generic layouts, 1920x1080 stage

Assumes 120 px side margins (content width 1680), a one-line title ending around y 240 and the
body starting at y 340 (320 in the split and portrait layouts, where the text column sets the top),
footer zone from y 980. These are typical free boxes; measure your own slide.

| Layout | Free box (x, y) | Size | Suggested viewBox |
|---|---|---|---|
| Full bleed, no title | x 120-1800, y 120-960 | 1680 x 840 | `0 0 1680 840` |
| Title + full-width body | x 120-1800, y 340-950 | 1680 x 610 | `0 0 1680 600` |
| Title + body above a caption / lede line | x 120-1800, y 340-780 | 1680 x 440 | `0 0 1680 440` |
| Two equal columns, gap 80 | each 800 wide, y 340-900 | 800 x 560 | `0 0 800 560` |
| 60/40 split, text left, illustration right (or mirrored), gap 80 | illustration 960 wide, y 320-920 | 960 x 600 | `0 0 960 600` |
| Illustration above a 4-6 step strip (the strip keeps y 760-950) | x 120-1800, y 340-740 | 1680 x 400 | `0 0 1680 400` |
| Narrow portrait column beside text | 560 wide, y 320-940 | 560 x 620 | `0 0 560 620` |

A two-line title pushes the body top down by about 60 px (to about 400) in every layout; a
title-less slide gains about 200 px of height.

## Other stage sizes

- **1280x720 and 1600x900** are also 16:9: multiply every number in the table by 2/3 or 5/6.
  Keep the viewBox unchanged and only change the rendered size; the text scale `s` then drops by
  the same factor, so check text against the contract minimum at the new rendered width.
- **reveal.js default 960x700** is not 16:9 and has a 4 % margin. Halve the widths of the table
  (content width about 880) and re-derive heights from the measured box; typical values:
  title + body 880 x 460, two columns 420 x 420, 60/40 split 520 x 440.
- The 18 px floor in the contract is in stage pixels on a 1920-wide stage. When a deck scales a
  smaller stage up to the same screen, the equivalent floor is `18 * stage_width / 1920`
  (12 px at 1280, 15 px at 1600, 10 px at 960, since the floor never goes below 10). Pass the stage with
  `check_fragment.py --stage-width W` (it derives the floor), or the floor with `--min-text`.
- A 4:3 source (`aspect: "4:3"` in `outline.json`, stage 1920 x 1440) rebuilt on a 16:9 deck
  gets new slots: measure the target deck's layout, not the source's.

## Rules of thumb

- Keep the deck's own margins; a fragment never extends into the side margin or the title area.
- Leave at least 30 px between the fragment's box and any footer, page number or source line.
- In grid columns, centre the fragment vertically (`align-self: center` on its wrapper) so a short
  illustration does not stick to the column top.
- Inside the viewBox, keep 16-24 px of padding so strokes and glows are not cut at the edge.
- The fragment fills its box with `width: 100%; height: 100%` and never exceeds it. Use
  `overflow: visible` only when an element must deliberately break out of the box, and then check
  the overflow in the rendered PNGs.
- Prefer one wide illustration over two small ones; text scale drops fastest in split layouts.
