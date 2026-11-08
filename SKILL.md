---
name: anim-slides
description: Turn boring slides into animation-rich HTML. Builds self-contained animated SVG illustrations (CSS keyframes, optional click-driven step mode) that replace text blocks and screenshots in any HTML slide deck, and creates them directly from documentation of processes, dependencies, timelines or architectures. Use when the user wants to animate a PPT/PPTX or HTML deck, "make this slide less boring", draw a process/pipeline/dependency graph/timeline/comparison as an animation, or turn a Mermaid diagram or a written procedure into an animated illustration. Not for generating a whole deck from scratch (use a slides skill first) and not for video.
license: MIT
compatibility: Python 3.9+ for the scripts; a Chrome or Chromium binary for phase rendering; any harness that can run shell commands and view PNG files.
metadata:
  author: Kehan Liu
  version: "0.9.1"
  repository: https://github.com/KehanLiu/anim-slides
---

# anim-slides

Animated SVG illustrations for slide decks, from existing slides or from documentation.
Output is always a **fragment**: one HTML file with a `<style>` and one `<svg>`, no scripts,
no external files, themed by CSS variables, that drops into any deck.
`references/fragment-contract.md` is the contract. Read it before building anything.

## When to use
- A slide is a row of text cards, a bullet list or a screenshot, and the content is a process,
  a flow, a dependency structure, a timeline, a comparison, an architecture or a time series.
- A document (Markdown, Confluence export, README, Mermaid block) describes a process or
  dependencies and the user wants it shown as an animation on a slide or page.
- The host is an HTML deck (frontend-slides, reveal.js, impress.js, Slidev, hand-written) or a
  plain web page. A `.pptx` or Markdown source is converted to a designed HTML deck first by a
  deck skill (step 0); this skill then adds the illustrations.

## Workflow
`<skill-dir>` below is the folder that contains this SKILL.md (Claude Code exposes it as
`$CLAUDE_SKILL_DIR`; in other harnesses use the path you loaded this file from). Scripts need
Python 3.9+ and, for rendering, a Chrome or Chromium binary. `anim/<name>/` is a folder next to
the user's deck.

### 0. Intake
**Get an HTML deck first.** anim-slides adds figures to an HTML deck; it does not design one.
- The source is already an HTML deck (reveal.js, impress.js, any `<section>` or `.slide`
  deck): proceed.
- The source is a `.pptx`, Markdown, remark, a document or anything else that is not an HTML
  deck: a deck skill builds the HTML deck first, not anim-slides. In order of preference:
  (a) the user's own or organisation's deck skill, if one is installed; (b) `frontend-slides`,
  when installed (it converts pptx and Markdown into a designed HTML deck; when it offers
  aesthetic previews, pick the one closest to the source deck's brand unless the user wants a
  new look); (c) only when no deck skill is installed, `scripts/md_to_deck.py` as a fallback
  (see the fallback bullet below), and tell the user in one sentence that its output is a
  plain host, not a design, and will read like a document until a deck skill or a designer
  styles it. In cases (a) and (b) the original `.pptx` stays the source for
  `extract_slides.py` and `render_deck.py` triage (charts, figures, notes), but integration
  targets the deck the skill produced, and the match look comes from that deck's palette via
  `host_theme.py`. Ask the deck skill (or do it right after it) to wrap each candidate slide's
  body in a fixed-size slot `<div id="sN-slot">` between `<!-- sN-body -->` and
  `<!-- /sN-body -->` (the id and marker names `md_to_deck.py` uses, though there the slot is an
  empty sibling of the body): `measure_slot.py --selector '#sN-slot'`
  is then exact, and `integrate_fragment.py --anchor`/`--replace-until` targets the markers.
  A deck skill's own font link (Google Fonts, Fontshare) is the deck's load, not one
  anim-slides added; keep it, and inline it at hand-over with `bundle_deck.py --fetch`.

Then decide which entry point applies:
- **Existing deck**: run `python3 <skill-dir>/scripts/extract_slides.py deck.pptx|deck.html|doc.md -o anim/outline.json`
  and `python3 <skill-dir>/scripts/render_deck.py deck -o anim/render`, then look at the
  `sheet-NN.png` contact sheets (12 numbered slides each), not page by page (when a slide's
  picture count in `outline.json` differs from the pictures in its render, look at the slide
  layout's pictures: a cover photo on the layout is easy to miss); then
  triage with `references/input-stage.md` and write the table to `anim/triage.md`: every
  slide, a decision and a reason, no silent skips (3 to 8 illustrations per 30 slides is
  normal; on a short deck every process, structure, timeline, comparison or data slide gets one).
  Then settle the **look** once for the whole deck: **match** (fragments take the host's
  palette and fonts, the default for branded or corporate decks) or **lean** (fragments keep the
  lean palette on a dark ground, for talks and pitches). `python3 <skill-dir>/scripts/host_theme.py deck.html --mode match -o anim/host-theme.css`
  derives the match glue from the deck's CSS (`--mode lean` writes the lean glue); compare
  the derived block once against the deck's own variables (a muted text colour, a secondary
  background) and correct by hand where the derivation picked a computed mix; render the
  first fragment both ways (`render-phases.sh --theme anim/host-theme.css ...`) and show the
  two stills before building the rest, unless the user already named a look. Only colours and
  fonts change between the two: the shape rules of `references/style.md` hold in both.
  The **control** is `once` for the whole deck unless the user asks for click-through: each
  slide's figure plays one calm pass when the slide appears, then rests. Do not recommend
  `step` on your own. Mention it in one line only when `outline.json` reports `builds` above 0
  (the source already builds by click: reveal.js fragments, PowerPoint click animations,
  impress.js substeps, the deck's own build steps): "your deck builds by click; the figures can
  do the same (step), say so if you want it". Under `step` the entrance draws on and each click
  lands the next phase; the phases are the brief's narrated phases (3 to 5 per slide), the
  fragment file is the same, and the click rides on the deck's own navigation. Step listens to
  keys only, so a step deck is presented with the keyboard or a clicker (a deck that also
  navigates by wheel or swipe, as frontend-slides does, skips the phases on a scroll). Write
  Look and Control in the header of `anim/triage.md`.
- **Fallback, no deck skill installed (Markdown, remark, or a pptx extracted to Markdown)**:
  `python3 <skill-dir>/scripts/md_to_deck.py deck.md -o deck.html` makes a plain, self-contained
  host to integrate into (one `<section>` per slide, `.visible` gating, print layout,
  `<!-- sN-body -->` markers round each slide's body). It is not a designed deck: say so to the
  user in one sentence. Fetch the images the Markdown references (relative paths) into the same
  folder first, or the deck shows placeholders; then extract from the original source (the
  `.pptx` if there was one) or the Markdown.
- **Documentation**: read the source, pick the archetype with the table in
  `references/archetypes.md`, extract a spec (step 1).
- **Single slide request**: go straight to step 1 for that slide.
Ask the user only when the source is ambiguous about order, direction or grouping. Otherwise
state the assumption in the brief and continue.

### 1. Spec
Write `anim/<name>/spec.yaml` following `references/spec-format.md`: name, archetype, nodes,
edges, groups, phases with second marks, cycle (the pass length), control (the deck's choice
from intake: `once`, one calm pass of 4 to 10 s when the slide becomes current, ending on the
resting frame; `step`, the same pass cut at the phase marks so each click lands the next
phase; `loop` only when the user asks for a continuous loop). The fragment file is the same
under `once` and `step`; the phase marks become `data-anim-phases`. Reuse the
source's own words as labels. Keep a spec under about 12 nodes; split otherwise.

### 1b. Check the pool
Read `<skill-dir>/pool/index.yaml`, then `$ANIM_POOL/index.yaml` (or list `$ANIM_POOL/*/`) if
that variable is set, and look for an entry with the same archetype and a similar story or tags.
- **Close match**: copy the folder to `anim/<name>/`, rename the fragment and every prefix to
  `<name>`, then adapt labels, data, timing and viewBox to the spec in step 3 instead of
  scaffolding. Its `spec.yaml`, if present, is a starting point for yours.
- **Same archetype only**: scaffold as usual, and open the pool fragment as the quality bar for
  density, motion and resting frame.
- **Nothing fits**: build from the spec; the closest pool entry is still worth one look.
Never copy a pool fragment unchanged into a deck: its story is an example, not the user's.

### 2. Slot and brief
Measure the free box on the slide: `python3 <skill-dir>/scripts/measure_slot.py deck.html --slide N [--selector SEL] [--ignore .body]`
prints the box in stage pixels, a matching viewBox and the checker flags (`references/layouts.md`
explains the manual way). On an absolutely positioned layout measure without `--selector`
returns junk; measure the slot div (`--selector '#sN-slot'`, step 0). Pick a viewBox with the same aspect
ratio, and fill `anim/<name>/brief.md` from `references/brief-template.md`. The brief fixes
viewBox and rendered size, composition, phases, resting frame, theme tokens and min text size,
and names what on the slide the fragment replaces (the pills, the box diagram, the bullet column).
The quality of the fragment tracks the quality of the brief.

### 3. Build
`python3 <skill-dir>/scripts/scaffold_from_spec.py anim/<name>/spec.yaml -o anim/<name>/<name>.html --rendered-width <px>`
validates the spec and writes a contract-compliant skeleton (layout, phases, packets, notes,
resting frame; font sizes raised to the floor at the rendered width), then runs the checker on
it. The comment at the top of the output lists what to refine by hand. Refine it into the
illustration the brief describes, using `references/archetypes.md` for composition and motion,
`references/motion-rules.md` for timing and easing, and `references/style.md` for the look
(lean: rings and thin lines, no boxes, one glowing accent, mono sub-labels, plain captions). For several illustrations, build one
fragment at a time from the shared briefs, or one parallel subagent per fragment if the harness
has them; integration always stays in the main thread.

### 4. Verify by looking
1. `python3 <skill-dir>/scripts/check_fragment.py anim/<name>/<name>.html --name <name> --rendered-width <px> --stage-width <deck stage width>`
   must pass (prefixes, tokens, gating, text size, forbidden content). `--stage-width` sets the
   text floor (18 px at 1920, 12 px at 1280); `outline.json` reports the stage.
2. `<skill-dir>/scripts/render-phases.sh anim/<name> <W> <H> 1.5 4 7 10 rest` renders phase PNGs and a
   contact sheet with the paused plus negative-delay method, into a temp folder it prints (pass
   `--out DIR` to choose). After integration, `render-phases.sh --page deck.html 1920 1080 rest`
   checks the host page's resting frame; on a multi-slide page add `--slide N` (or `#hash`, or a
   CSS selector). Use `--no-script` for timed mark or phase frames when the page's own script
   toggles the gate class, never for `rest`: in frontend-slides decks `.visible` is both the
   gate and the class that shows the slide, the rest render strips it, and the slide stays up
   only because the deck's script also sets `.active`; without the script the rest frame is
   blank. Open every PNG with your image viewing tool. Fix clipping, overlaps, unreadable text, empty panels. Iterate at least once.
3. The resting frame must read as a complete still (PDF export shows only that).
4. `python3 <skill-dir>/scripts/verify_facts.py anim/<name>/<name>.html --source anim/outline.json --slide <N>`
   (or `--source doc.md`) must pass: every number in the fragment comes from the source or is
   marked illustrative; read each WARN and replace untraceable wording with the source's own
   words or remove it. Rules in `references/accuracy.md`. A figure is not done until this passes.
Never trust `--virtual-time-budget`, and never trust reading the source instead of the PNG.

### 5. Integrate
`python3 <skill-dir>/scripts/integrate_fragment.py deck.html anim/<name>/<name>.html --name <name> --anchor '<unique string in the slide>' [--replace-until '<string>'] [--gate 'section.present'] [--control once|step] --backup`
hoists the style into the head, inserts the fragment between `<!-- anim:<name>:start -->` and `<!-- anim:<name>:end -->`
markers (the style between `anim-style` markers; re-running replaces both copies), rewrites the gate for the host deck, and prefixes any
class that slipped through. For plain pages copy `<skill-dir>/scripts/snippets/observer.html` into the page.
`--control` sets the deck's control on the wrapper; `--control step` also puts
`scripts/snippets/step-host.html` (a small plain script, no library) into the head once and
sets its gate from `--gate`. The control is a deck-wide switch at integration: re-run with
the other value to change it, the fragments stay as they are.
The anchor and the until-string are kept; what lies between them is replaced. The gate is the
host's "current slide" marker: `section.present` for reveal.js, `.visible` for plain pages
(`scripts/snippets/observer.html`) and for decks from `md_to_deck.py`. In `md_to_deck.py` decks,
and in deck-skill decks with the slot markers from step 0, the fragment replaces the body:
`--anchor '<!-- sN-body -->' --replace-until '<!-- /sN-body -->'`.
Check that the slide's headings and body text show without the deck script and in print.
Deck skills' entrance animations often key their reveals on the current-slide class only
(frontend-slides shows `.reveal` elements only under `.slide.visible`), so rest renders and
PDF show empty slides; key those reveals also on the deck's active class (`.slide.active`)
and add a print rule that shows them. (The class name `.reveal` also matches reveal.js
detection in `host_theme.py`'s slide selectors; harmless so far, but check which slides it
found.)
It also adds a print guard so PDF export (reveal's `?print-pdf` marks every slide present) shows
resting frames.
Keep the working deck **lean**: fragments are small SVG text and go in by markers, but do not
inline fonts, images, libraries or stylesheets while you work, and never read the whole deck
into context; read slices around the anchor (`grep -n`, `sed -n`) and let the scripts edit it.
Then open the deck in a real browser and watch the slide once. Headless frames never prove
smoothness. For a headless check of one slide:
`chrome --headless=new --hide-scrollbars --window-size=1920,1080 --timeout=3000 --screenshot=s4.png 'file:///abs/deck.html#/4'`
(`#/4` is reveal.js; `md_to_deck.py` decks use `#4`; for the resting frame use
`render-phases.sh --page deck.html --slide 4 1920 1080 rest`, a raw screenshot shows t = 0)
(never pass `--user-data-dir`, Chrome then hangs; export PDFs from the browser's print dialog,
the CLI `--print-to-pdf` on `?print-pdf` is unreliable).

### 5b. Hand-over
Ask the user whether the deck will be shared or presented from another machine. If yes, bundle
it last: `python3 <skill-dir>/scripts/bundle_deck.py deck.html -o deck.bundled.html --fetch` inlines
every local stylesheet, script, font and image as data: URIs so
one file opens offline; then `python3 <skill-dir>/scripts/check_page.py deck.bundled.html --gate section.present`
confirms no external loads, paired markers, gated fragments and the print guard per fragment
(it detects the host's gate, `section.present` or `.visible`; `--gate` overrides). Do not read the bundled file; verify it with the checker and
one `render-phases.sh --page deck.bundled.html --slide N 1920 1080 rest` render. Never add a CDN `<script>` or `<link>`
yourself; keep ones the user's deck already had and say so. A deck skill's web-font link is
such a load: the lean working deck fails `check_page.py`'s external check on it, and
`--fetch` inlines the fonts (in one run 9 fonts, bundled deck 0 fail).

### 6. Audit
Run the checklist at the end of `references/motion-rules.md` before shipping.

## Hard rules
- Deck first. anim-slides styles fragments, never the deck. A deck that is not HTML yet goes
  through a deck skill before triage; `md_to_deck.py` is a last resort and is named as such to
  the user.
- Keep the slide's visuals. A chart, graph, table, map, flowchart or scientific figure on the
  source slide is its core content: redraw it as SVG from its data (axes, scales, curves, labels)
  and animate that, never replace it with a text summary. Illustrations that carry meaning stay
  too: an icon or picture that labels a column, a lane, a category or an actor (a mascot per
  option, a figure per role, an organ or object the slide is about) is content. Keep it by
  embedding the source image in the host slide next to the fragment when the licence allows, or
  by redrawing it as a simple SVG glyph in the same colours inside the fragment. Only a slide
  background, a logo or a photo unrelated to the content may be left out; when unsure, keep it
  and say so. Render the source slides with `render_deck.py`, look at the contact sheets, and before
  writing a spec re-run with `--pages N,...` and open `full/p-NN.png` for each candidate;
  `extract_slides.py` cannot see inside pictures. A picture count in `outline.json` that
  differs from the render is a signal to look at the slide layout's pictures.
- Prefix every class, id and keyframe with `<name>-`. Host CSS has global `.bar .card .node
  .flow` rules and Chrome applies CSS width/height to SVG rects.
- No hard-coded colours or fonts: use `var(--anim-*)` tokens with the fallback block from the
  contract. Hosts retheme with `--anim-theme-*` (`scripts/host_theme.py` writes the block).
  A host theme changes colours and fonts only; it never brings the deck's cards, pills or
  panels back into the fragment.
- Make a visible change. A fragment replaces the slide's cards, pills, bullet columns or HTML
  diagram with an illustration. Motion laid over the slide's existing drawing, with the boxes
  left in place, is not an illustration; if nothing else is possible, the brief says why.
- Animate only under the gate (`.visible` when authoring). The ungated state is the finished
  state.
- No `<script>`, `<link>`, `<image>`, `@import`, `@font-face` inside a fragment, in any
  control. Step mode lives in the host snippet, not in the fragment.
- Text at or above 18 px at rendered size, titles 22 px and up.
- Never add CDN or network loads: none in fragments, no new ones in the deck. Loads the deck
  already has (a deck skill's web-font link) stay. Work on a lean deck; bundle to one
  self-contained file only at hand-over when the user wants to share (`bundle_deck.py --fetch`,
  which also inlines those fonts, then `check_page.py`).
- The look follows `references/style.md`: no filled cards, chips or caption bars; rings and
  thin lines; one accent with glow; at most two semantic colours, each meaning something on
  the slide.
- Less. The fragment is the slide's own figure in its own form (stairs stay stairs, a table
  stays rows) plus one movement; no invented chart forms, no extra brackets, arrows or
  storylines, one glowing element at most and never a glowing line. When in doubt, leave it
  out (`references/style.md`, principle 0).
- One control per deck. `once` unless the user asks for `step`; never recommend `step`
  unprompted, only mention it when the source builds by click. The same on every slide, so
  the presenter always knows what a click does. A slide that differs needs a reason in
  `anim/triage.md`.
- Plays once. One pass of 4 to 10 s when the slide becomes current, iteration count 1 with
  fill forwards, the 100 % keyframe equal to the resting frame, nothing looping or pulsing
  while the slide is up (under `step` the same pass plays in click segments). At most three
  things moving at once, `linear` only for continuous
  loops, exits about 65 % of entrance length, reduced-motion block present.

## Files
- `references/fragment-contract.md` — the output contract (shape, prefixes, tokens, gate, resting frame, control variants)
- `references/spec-format.md` — the intermediate spec extracted from docs or slides; Mermaid mapping; worked examples
- `references/archetypes.md` — pipeline, graph, timeline, states, compare, layers, chart: composition and motion recipes
- `references/input-stage.md` — from a deck or document to a list of briefs; triage rules
- `references/brief-template.md` — the brief every fragment starts from
- `references/layouts.md` — measuring a slot; generic 16:9 layouts and viewBoxes
- `references/motion-rules.md` — timing, easing, choreography, audit checklist
- `references/lessons.md` — gotchas collected while building fragments
- `scripts/extract_slides.py` — pptx/html/md to outline JSON with archetype suggestions and click `builds` per slide
- `scripts/render_deck.py` — source deck to contact sheets (12 slides each) plus full-size pages for candidates
- `scripts/host_theme.py` — host glue: `--anim-theme-*` block derived from the deck's CSS (match) or the lean palette (lean)
- `scripts/md_to_deck.py` — fallback only (no deck skill installed): Markdown or remark deck to a plain, self-contained HTML host to integrate into; not a designed deck
- `scripts/scaffold_from_spec.py` — spec validation and spec to skeleton fragment (once, loop or step); YAML or JSON, PyYAML optional
- `scripts/check_fragment.py` — static contract checks
- `scripts/verify_facts.py` — provenance gate: fragment text and numbers against the source slide
- `references/style.md` — the visual style: lean, quiet, one accent, no boxes; checklist before shipping
- `references/accuracy.md` — accuracy rules: numbers from the source, labels in its words, figures redrawn at scale
- `scripts/render-phases.sh` — phase PNGs and contact sheet with headless Chrome
- `scripts/measure_slot.py` — free box of a slide in stage pixels, with viewBox and checker flags
- `scripts/check_page.py` — page-level checks: no external loads, paired markers, gated fragments, print guard, step snippet present when a step wrapper is
- `scripts/bundle_deck.py` — inline local (and with `--fetch`, remote) assets into one self-contained file
- `scripts/integrate_fragment.py` — idempotent inlining into a deck, gate rewrite, prefix safety net, `--control once|step`
- `scripts/snippets/observer.html`, `scripts/snippets/step-host.html` — host-side helpers (scroll gate; step mode, plain script, no library)
- `pool/` — finished, checked fragments, at least one per archetype, with thumbnails and specs; `pool/index.yaml` lists them (step 1b)

## Related skills (use them when your harness has them; none is required)
- A motion-design skill for deeper timing and easing guidance.
- A deck skill (the user's own, frontend-slides, reveal.js, Slidev or similar) to produce the
  deck itself before triage (step 0, "Get an HTML deck first"); a pptx skill to read PowerPoint sources beyond what `scripts/extract_slides.py` extracts.
