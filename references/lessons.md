# Lessons

Gotchas found while building animated slide illustrations. Add to this file when a new one
bites. Rules derived from these are in [fragment-contract.md](fragment-contract.md) and
[motion-rules.md](motion-rules.md).

## SVG / CSS gotchas

- Chrome applies CSS `width` and `height` to SVG `<rect>`. A host rule like `.bar { height: 100% }`
  turns a fragment's `<rect class="bar">` into a 1000 px stripe. Prefix every class and id.
- `transform` on a `<clipPath>` child does not repaint reliably in Chrome. Animate a cover rect or
  the clip rect's `width` instead.
- Stacked `<text>` elements that cross-fade are the only robust way to "change" text without JS.
- A `<use>`d symbol cannot be styled from document CSS except through inherited properties
  (`fill`, `stroke`, `color`, custom properties).
- Host base rules such as `svg { max-width: 100% }` truncate a deliberately oversized SVG (e.g. a
  scrolling trace). Override with `max-width: none` inside the fragment's scope.
- `pathLength="100"` (or 1000) on a path normalises dasharray maths, so every draw-on uses the
  same numbers.
- `offset-path: path(...)` plus `offset-distance` moves packets along wires with no JS.
- Give every element its own full-cycle keyframe track instead of `animation-delay`. Delays break
  clean loop restarts and make negative-delay phase rendering wrong.
- When lines attach to a shape that later splits or moves in parts (a bar, a group), end each line
  inside the part it belongs to so the split needs no re-attachment.

## Chrome rendering

- Compositor animations (`transform`, `opacity`) and main-thread animations (`stroke-dashoffset`,
  stroke or fill colour) can sample at different times. Mixed tracks on one element may look
  desynchronised in a screenshot even when they are fine live.
- Linear easing is right for continuous loops (dashes, scrolling traces, spinners) and wrong for
  spatial moves with a start and an end.

## Headless verification

- Never use `--virtual-time-budget` for CSS animation frames: it desynchronises compositor and
  main-thread animations. Use a preview copy with
  `* { animation-delay: -Ns !important; animation-play-state: paused !important; }` to jump to
  second N. `scripts/render-phases.sh` does this.
- Load the same fonts in the preview as the deck uses; otherwise label widths differ and overlaps
  hide or appear falsely.
- Look at every phase PNG with your image viewing tool. Every fragment that was only code-reviewed had an
  overlap somewhere.
- A headless screenshot never proves smoothness. Check once in a real browser before shipping.
- Browser extensions often cannot open `file://` URLs. Serve the deck with
  `python3 -m http.server` and add a changing query string (`?v=N`) to force a reload; a hash
  change alone does not reload the page.

## Integration

- A fragment with generic classes (`.bar`, `.flow`, `.tag`, `.card`, `.node`, `.chip`) collides
  with the host's CSS. `scripts/integrate_fragment.py` re-prefixes mechanically as a safety net,
  but author with prefixes from the start.
- Gate animations on the active slide so ten slides do not animate at once; rewrite the gate per
  host with `integrate_fragment.py --gate`.
- Decks export to PDF from the resting frame. A fragment whose base state is the empty start
  prints as a blank box.
- Independent fragments can be built in parallel (one agent per fragment, shared brief);
  integrate them in one pass afterwards.
- Anything that loops longer than 5 s needs a way for the presenter to pause it.

## Legibility

- Compute text size at rendered size, not from the viewBox number:
  `viewBox_px * rendered_width / viewBox_width`. An 18 px label in a 1000-wide viewBox rendered
  at 900 px is 16.2 px. `check_fragment.py --rendered-width` catches this.
- Long single-line strings in monospace run out of room fast: at 21 px mono expect about
  105 characters across a 1680 px line.

- Transforms on SVG groups (translate a curve, rotate a clipped layer, scale a lens) need
  `transform-box: view-box` (or `fill-box`) plus a `transform-origin` in px; the CSS default
  resolves against the wrong box. Avoid CSS `d` path morphing: Safari does not animate it.
- Index suffixes collide with semantic ones: `<name>-mk0` written by hand and `<name>-mk{i}`
  generated for i = 0 select the same element. Use separators such as `<name>-mk-n0`.
  `check_fragment.py` warns (`index-collision`).
- Fragments start at t = 0 in a host that just revealed them; a gallery of many loops looks
  empty at first glance unless each starts at a negative offset.

## Content

- A chart, graph, table or scientific figure on the source slide is the slide. Redraw it from
  its data (exact scale, so points land on gridlines) and animate that; never swap it for a
  text summary.

- Numbers in illustrations are usually illustrative; say so on the slide or in the speaker notes.
- Keep the story plausible to a domain expert in the audience; put the explanation in the notes.

## Host decks

- A branded deck full of rounded panels tempts the builder to redraw the panels in SVG and
  animate the wires between them; the user then sees "almost no change". The host theme gives
  colours and fonts only; the boxes become rings and labels on lines (style.md, "Under a host
  theme"), and the brief names what the fragment replaces.
- `render-phases.sh --page --no-script` shows blank frames on decks whose own script both adds
  the gate class and fills images; render from a scratch copy that marks every slide current
  and disables animation (what print mode does), never from an edited deck.
- `.step` divs inside a `.slide` are build steps (stairs, reveals), not slides;
  `extract_slides.py` treats `.step` as a slide only at impress.js top level.
