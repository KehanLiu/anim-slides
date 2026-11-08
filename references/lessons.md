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
- Give every element its own full-pass keyframe track instead of `animation-delay`, in every
  control: `render-phases.sh` overrides delays when it pauses frames, so delayed tracks render
  at the wrong time, and under `loop` delays also break clean restarts. Many tracks are fine;
  the checker measures how many things move at the same instant, not how many tracks exist.
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
  the gate class and shows the slide. In frontend-slides decks `.visible` is both the fragment
  gate and the class that shows the slide; the `rest` render strips it, and the slide stays up
  only because the deck's script also sets `.active`. Rule that held: `--no-script` for timed
  mark or phase frames, never for `rest`. If a deck still renders blank, render from a scratch
  copy that marks every slide current and disables animation (what print mode does), never
  from an edited deck.
- `.step` divs inside a `.slide` are build steps (stairs, reveals), not slides;
  `extract_slides.py` treats `.step` as a slide only at impress.js top level and counts nested
  ones as `builds`.
- Whether a click advances the figure is a presenter habit, not something the deck's content
  reveals. The default is `once` for the whole deck; `step` only when the user asks (when the
  source builds by click, `builds` in `outline.json`, mention in one line that step exists,
  nothing more: the owner of this skill found an unasked step deck annoying). Keep it the same
  on every slide so the presenter always knows what a click does. Step mode lives in the host snippet, so the
  choice can change at integration without rebuilding fragments.
- A rebuilt figure can be accurate and still wrong: a staircase re-plotted as a glowing line
  chart with brackets and arrows was rejected as "too much". Keep the slide's figure form and
  add one movement; the checker measures how many things move and glow at once and catches the rest.
- A 4-slide pptx was extracted to Markdown, run through `md_to_deck.py`, and two slides were
  animated. The user's verdict: "super ugly, only the charts on slide 4 are good". The
  fragments were fine; the host was a Markdown dump (full-width title, a bullet list, a row of
  raw image thumbnails), and the pptx's own designed layout was gone before anim-slides started.
  Deck first: a source that is not an HTML deck yet goes through a deck skill (the user's own,
  else `frontend-slides`) before triage; `md_to_deck.py` is a last resort, named as a plain host
  to the user, and the pptx stays the triage source.
- Deck first on a frontend-slides deck (the same 4 slides, pptx to frontend-slides to
  anim-slides, match look, step control). It worked: the fragments dropped into a 1680x610 and
  a 1680x700 slot without size changes, `verify_facts.py` passed, and the user, who had called
  the `md_to_deck.py` attempt "super ugly", judged the fragments fine. What it took:
  - `--no-script` for timed frames only, never for `rest` (see the blank-frames entry above).
  - The deck's entrance animations show `.reveal` text only under `.slide.visible`, so rest
    renders and print showed empty slides. Key the reveals also on `.slide.active` and add a
    print rule; check headings and body text without the deck script and in print. The class
    name `.reveal` also matches reveal.js detection in `host_theme.py`'s slide selectors
    (harmless in this run).
  - Without `--selector`, `measure_slot.py` returned junk on the absolutely positioned layout.
    A fixed-size `<div id="sN-slot">` with the `<!-- sN-body -->` markers inside it made
    measuring exact and `integrate_fragment.py --anchor`/`--replace-until` painless; ask the
    deck skill for it. (Markers round the div, as first written, let `--replace-until` delete
    the sized div; see the 2026-11-08 entry.)
  - The deck's Google Fonts / Fontshare link is the deck's load. The lean working deck fails
    `check_page.py`'s external check on it; `bundle_deck.py --fetch` inlined 9 fonts and the
    bundled deck passed with 0 fail.
  - Step listens to keys only; frontend-slides also navigates by wheel and swipe, so a scroll
    skips phases. Tell the presenter to use the keyboard or a clicker.
  - On the white match ground a fade level of 0.35 in the light line colour vanished; 0.6
    read (style.md, "Under a host theme").
  - `host_theme.py` mapped muted to a computed mix instead of the deck's `--text-secondary`;
    compare the derived block with the deck's variables once and correct by hand.
  - `extract_slides.py` missed a cover photo placed on slide layout 4 and reported a picture
    that does not show on the rendered slide. A picture count that differs between
    `outline.json` and the render means: look at the layout's pictures.

## Two bare-prompt runs (2026-11-08)

Two fresh-user tests, the agent alone with SKILL.md 0.9.1 and a bare prompt: "improve the
slides" on a 46-slide pptx and "add more animations to this deck" on a 43-slide pptx.

What went right: showcase-quality fragments, seven slides each, every check green
(`check_fragment.py`, `verify_facts.py`, `check_page.py`). Triage, contract and style rules held.

What went wrong:
- About 25 minutes and 1.1 M tokens per run; some 15 reference files read.
- Twelve decisions taken silently per run. The skill had five separate "ask the user" points
  (triage approval, look, control, ambiguity, hand-over) and no way to ask them at once, so an
  agent that could not wait asked none; one run invented a `DECISIONS.md` to record them.
- The deck rebuild by frontend-slides took most of the time, and the user was never told it
  would happen or offered a lighter path.
- The scaffolder's output was thrown away for most real shapes (triangle graph, 4+4 snake
  U-turn, timeline with event text, bar chart, donut).
- Small contradictions: the slot markers were written "round" the `#sN-slot` div, so
  `--replace-until` deleted the sized div; SKILL.md's `verify_facts.py` line omitted `--spec`
  that accuracy.md requires; `render_deck.py` skips hidden slides, so its numbering ran behind
  `outline.json`; the rest render hid the deck's own staggered text; `host_theme.py` picked an
  accent by usage count on a deck without variables; the checker's text floor assumed a 1920
  stage when `--stage-width` was left out; the phase-mark wording ("start of every phase after
  the first") did not fit hand-built fragments.

Rules that followed (0.10.0, modelled on frontend-slides' "show, don't tell"):
- Phase 0 reads the request into a mode (A deck first, B in place, C one slide, D from docs,
  E re-integrate). "Improve" and "add more animations" mean the same: figures replace text
  blocks and screenshots, nothing else changes; "more" is the upper end of the budget.
- Show first, ask once: build and render the first fragment (match and lean stills, both
  readings when there are two), then one intake message with proposal, stills, look, control,
  deck-first cost and lighter path, hand-over. Nothing is asked after it; defaults go into a
  Decisions section of `anim/triage.md`. An unreadable figure is traced and tagged, not asked.
- Mode A announces the deck rebuild and its cost and offers standalone animated slide pages.
- The scaffolder covers the plain archetype forms; other shapes are hand-built from the spec.
- Markers go inside the slot div. One phase-mark definition everywhere (settled moments).
- Delivery is a before/after review page (`review_page.py`) and a few lines.

- **A fallback deck in the folder is not a decision.** A 12-slide corporate pptx run under
  0.10.0 found a `deck.md` from an earlier try, built the host with `md_to_deck.py`, wrote
  "user's earlier choice" into Decisions and asked at intake whether to "keep the md_to_deck
  host". The three fragments were good; the nine text slides around them were a raw dump, and
  the owner asked why frontend-slides was not the base. Rule since 0.11.0: with a deck skill
  installed the fallback is never used or offered; the intake deck question is full deck or
  lighter path only.
