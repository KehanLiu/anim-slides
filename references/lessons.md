# Lessons

Read when integrating into a deck built by a deck skill: "Integration" and "Host decks".
Read when a check or render fails in a way the other references do not explain: "Headless verification", "SVG / CSS gotchas", "Chrome rendering", "Legibility" and "Motion and review".

Gotchas found while building animated slide illustrations. Add to this file when a new one
bites. Rules derived from these are in [fragment-contract.md](fragment-contract.md) and
[motion-rules.md](motion-rules.md). History and run logs: docs/maintainer-notes.md (maintainers only).

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
- Give every element its own full-pass keyframe track instead of `animation-delay`, in every
  control: `render-phases.sh` overrides delays when it pauses frames, so delayed tracks render
  at the wrong time, and under `loop` delays also break clean restarts. Many tracks are fine;
  the checker measures how many things move at the same instant, not how many tracks exist.
- Merge and split: draw each part as its own `<g>` and end each line inside the part it belongs
  to, then translate the groups together or apart. A split starts with the parts stacked on the
  whole (the whole fades as they move off); a merge ends with the whole cross-faded in over them.

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
- A one-slide headless screenshot:
  `chrome --headless=new --hide-scrollbars --window-size=1920,1080 --timeout=3000 --screenshot=s4.png 'file:///abs/deck.html#/4'`
  (`#/4` is reveal.js, `md_to_deck.py` decks use `#4`). It shows t = 0; for the resting frame
  use `render-phases.sh --page deck.html --slide 4 1920 1080 rest`. Never pass
  `--user-data-dir` (Chrome hangs); export PDFs from the browser's print dialog, the CLI
  `--print-to-pdf` on `?print-pdf` is unreliable.
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
- Anything that loops needs a way for the presenter to pause it; the default is a single pass that ends on the resting frame, so nothing moves while the presenter talks.

## Legibility

- Compute text size at rendered size, not from the viewBox number:
  `viewBox_px * rendered_width / viewBox_width`. An 18 px label in a 1000-wide viewBox rendered
  at 900 px is 16.2 px. `check_fragment.py --rendered-width` catches this.
- Long single-line strings in monospace run out of room fast: at 21 px mono expect about
  105 characters across a 1680 px line.

- Transforms on SVG groups (translate a curve, rotate a clipped layer, scale a lens) need
  `transform-box: view-box` (or `fill-box`) plus a `transform-origin` in px; the CSS default
  resolves against the wrong box. CSS `d` path morphing does not animate in Safari. To turn one shape into another, stack
  both and cross-fade their opacity as the base, and add the `d` morph inside
  `@supports (d: path("M0 0"))` (motion-rules.md, Techniques).
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

- A deck skill counts when its SKILL.md is in any harness's skills folder. A topic with no deck
  goes to it first; anim-slides never builds the deck on its own ground and reskins it later.
- With a deck skill installed, a fallback deck already in the folder is never used or offered.
- Deck first: a source that is not an HTML deck yet goes through a deck skill (the user's own,
  else `frontend-slides`) before triage. `md_to_deck.py` is a last resort, named as a plain
  host to the user, and the pptx stays the triage source.
- To match the source, recolour the closest frontend-slides preset to the source's palette.
- Check the `font` row of `host_theme.py`'s table against the deck once.
- Compare `host_theme.py`'s derived block with the deck's variables once (it can map muted to
  a computed mix instead of the deck's `--text-secondary`) and correct by hand.
- On a single-accent deck map `--anim-theme-ok` to the line colour or the accent.
- Do not redraw a branded deck's rounded panels in SVG. The host theme gives colours and fonts
  only; the boxes become rings and labels on lines (style.md, "Under a host theme"), and the
  brief names what the fragment replaces.
- On a white match ground use a fade level of 0.6 in the light line colour; 0.35 vanishes
  (style.md, "Under a host theme").
- Use `render-phases.sh --page --no-script` for timed mark or phase frames, never for `rest`:
  in frontend-slides decks `.visible` is both the fragment gate and the class that shows the
  slide. If a deck still renders blank, render from a scratch copy that marks every slide
  current and disables animation (what print mode does), never from an edited deck.
- Key a deck's own entrance reveals (`.reveal` under `.slide.visible`) on `.slide.active` too
  and add a print rule. Check headings and body text without the deck script and in print.
- Ask the deck skill for a fixed-size `<div id="sN-slot">` with the `<!-- sN-body -->` markers
  inside it. Pass W x H and position in its brief; use padding, not margin, inside the slot (a
  child margin collapses through it and shifts `measure_slot.py`'s box). Without `--selector`,
  `measure_slot.py` returns junk on absolutely positioned layouts.
- Fold the deck skill's own questions (density, style previews) into the one intake message;
  choose the closest preset and name it.
- The deck skill's font link is one WARN in `check_page.py` on the working deck;
  `bundle_deck.py --fetch` inlines the fonts at hand-over.
- Fragment-mode `check_look` font WARNs are expected on a deck-skill deck; the `--page` run is
  the font check.
- `.step` divs inside a `.slide` are build steps (stairs, reveals), not slides;
  `extract_slides.py` treats `.step` as a slide only at impress.js top level and counts nested
  ones as `builds`.
- Control is `once` for the whole deck; `step` only when the user asks. When the source builds
  by click (`builds` in `outline.json`), mention in one line that step exists, nothing more.
  Keep it the same on every slide so the presenter always knows what a click does. Step mode
  lives in the host snippet, so the choice can change at integration without rebuilding
  fragments.
- Step listens to keys only; frontend-slides also navigates by wheel and swipe, so a scroll
  skips phases. Tell the presenter to use the keyboard or a clicker.
- Keep the slide's figure form and add one movement. An accurate rebuild in another form (a
  staircase as a line chart with brackets and arrows) is still "too much".
- A picture count that differs between `outline.json` and the render means: look at the slide
  layout's pictures (`extract_slides.py` can miss one placed on the layout, or report one that
  does not show).
- In Mode A render every slide into `anim/review/after/`, not only the animated ones.

## Motion and review

- One verb per fragment, chosen from the slide's claim ([motion-verbs.md](motion-verbs.md)).
  A moving dot only on the slide where a named thing travels.
- Units that move together as a series need `data-anim-series` on the group; otherwise 20 to
  100 units count one by one, and rigid blocks read as a reshape, not a sort.
- Build a morph's cross-fade base first, then the `d` morph; render a copy with the
  `@supports` block removed.
- A counter moves with what it counts: step the number per row or per landing, or show it once
  when the motion settles.
- Keep the accent for the outcome. Let each part arrive, open or change; do not light parts in
  turn over a finished drawing.
- Give a state change a shape, not only a colour and a word: a progress stroke that stops at a
  cross, a ring that breaks, a wire that splits open.
- A round trip rests on its start: keep the states it passed through on the resting frame
  (small fixed thumbnails).
- Blind review on contact sheets: tell the reviewer the real width of a frame. Put the images
  in `anim/review/blind/`.
- `check_look.py --page` scores slides that are invisible at rest on a deck whose reveal is
  keyed on its own class: run it on a copy with the deck's `active` class added to its CSS.
  `render_deck.py` output can be cropped; check its PNGs.
