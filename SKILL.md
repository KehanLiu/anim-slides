---
name: anim-slides
description: Turn boring slides into animation-rich HTML. Builds self-contained animated SVG illustrations (CSS keyframes, optional GSAP step-through) that replace text blocks and screenshots in any HTML slide deck, and creates them directly from documentation of processes, dependencies, timelines or architectures. Use when the user wants to animate a PPT/PPTX or HTML deck, "make this slide less boring", draw a process/pipeline/dependency graph/timeline/comparison as an animation, or turn a Mermaid diagram or a written procedure into an animated illustration. Not for generating a whole deck from scratch (use a slides skill first) and not for video.
license: MIT
compatibility: Python 3.9+ for the scripts; a Chrome or Chromium binary for phase rendering; any harness that can run shell commands and view PNG files.
metadata:
  author: Kehan Liu
  version: "0.8.0"
  repository: https://github.com/KehanLiu/anim-slides
---

# anim-slides

Animated SVG illustrations for slide decks, from existing slides or from documentation.
Output is always a **fragment**: one HTML file with a `<style>` and one `<svg>`, no scripts
(unless step mode), no external files, themed by CSS variables, that drops into any deck.
`references/fragment-contract.md` is the contract. Read it before building anything.

## When to use
- A slide is a row of text cards, a bullet list or a screenshot, and the content is a process,
  a flow, a dependency structure, a timeline, a comparison, an architecture or a time series.
- A document (Markdown, Confluence export, README, Mermaid block) describes a process or
  dependencies and the user wants it shown as an animation on a slide or page.
- The host is an HTML deck (frontend-slides, reveal.js, impress.js, Slidev, hand-written) or a
  plain web page. A `.pptx` is converted to HTML first by a slides skill; this skill then adds
  the illustrations.

## Workflow
`<skill-dir>` below is the folder that contains this SKILL.md (Claude Code exposes it as
`$CLAUDE_SKILL_DIR`; in other harnesses use the path you loaded this file from). Scripts need
Python 3.9+ and, for rendering, a Chrome or Chromium binary. `anim/<name>/` is a folder next to
the user's deck.

### 0. Intake
Decide which of the three entry points applies:
- **Existing deck**: run `python3 <skill-dir>/scripts/extract_slides.py deck.pptx|deck.html|doc.md -o anim/outline.json`
  and `python3 <skill-dir>/scripts/render_deck.py deck -o anim/render`, then look at the
  `sheet-NN.png` contact sheets (12 numbered slides each), not page by page; then
  triage with `references/input-stage.md` and write the table to `anim/triage.md`: every
  slide, a decision and a reason, no silent skips (3 to 8 illustrations per 30 slides is
  normal; on a short deck every process, structure, timeline, comparison or data slide gets one).
  Then settle the **look** once for the whole deck: **match** (fragments take the host's
  palette and fonts, the default for branded or corporate decks) or **lean** (fragments keep the
  lean palette on a dark ground, for talks and pitches). `python3 <skill-dir>/scripts/host_theme.py deck.html --mode match -o anim/host-theme.css`
  derives the match glue from the deck's CSS (`--mode lean` writes the lean glue); render the
  first fragment both ways (`render-phases.sh --theme anim/host-theme.css ...`) and show the
  two stills before building the rest, unless the user already named a look. Only colours and
  fonts change between the two: the shape rules of `references/style.md` hold in both.
- **Markdown or remark deck with no HTML yet**: `python3 <skill-dir>/scripts/md_to_deck.py deck.md -o deck.html`
  makes a self-contained HTML deck (one `<section>` per slide, `.visible` gating, print layout,
  `<!-- sN-body -->` markers round each slide's body); fetch the images the Markdown references
  (relative paths) into the same folder first, or the deck shows placeholders; then extract from
  either file.
- **Documentation**: read the source, pick the archetype with the table in
  `references/archetypes.md`, extract a spec (step 1).
- **Single slide request**: go straight to step 1 for that slide.
Ask the user only when the source is ambiguous about order, direction or grouping. Otherwise
state the assumption in the brief and continue.

### 1. Spec
Write `anim/<name>/spec.yaml` following `references/spec-format.md`: name, archetype, nodes,
edges, groups, phases with second marks, cycle (the pass length), control (`once` default: one
calm pass of 4 to 10 s when the slide becomes current, ending on the resting frame; `loop`
only when the user asks for a continuous loop; `step` only when the presenter must drive the
phases, the story has more, and the host can load GSAP). Reuse the
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
explains the manual way). Pick a viewBox with the same aspect
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
   CSS selector), and `--no-script` when the page's own script toggles the gate class. Open every PNG with your image
   viewing tool. Fix clipping, overlaps, unreadable text, empty panels. Iterate at least once.
3. The resting frame must read as a complete still (PDF export shows only that).
4. `python3 <skill-dir>/scripts/verify_facts.py anim/<name>/<name>.html --source anim/outline.json --slide <N>`
   (or `--source doc.md`) must pass: every number in the fragment comes from the source or is
   marked illustrative; read each WARN and replace untraceable wording with the source's own
   words or remove it. Rules in `references/accuracy.md`. A figure is not done until this passes.
Never trust `--virtual-time-budget`, and never trust reading the source instead of the PNG.

### 5. Integrate
`python3 <skill-dir>/scripts/integrate_fragment.py deck.html anim/<name>/<name>.html --name <name> --anchor '<unique string in the slide>' [--replace-until '<string>'] [--gate 'section.present'] --backup`
hoists the style into the head, inserts the fragment between `<!-- anim:<name>:start -->` and `<!-- anim:<name>:end -->`
markers (the style between `anim-style` markers; re-running replaces both copies), rewrites the gate for the host deck, and prefixes any
class that slipped through. For plain pages copy `<skill-dir>/scripts/snippets/observer.html` into the page; for
step mode copy `scripts/snippets/step-host.html` into the head after a single GSAP script tag.
The anchor and the until-string are kept; what lies between them is replaced. The gate is the
host's "current slide" marker: `section.present` for reveal.js, `.visible` for plain pages
(`scripts/snippets/observer.html`) and for decks from `md_to_deck.py`. In `md_to_deck.py` decks
the fragment replaces the bullet block: `--anchor '<!-- sN-body -->' --replace-until '<!-- /sN-body -->'`.
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
every local stylesheet, script, font and image as data: URIs (GSAP for `step` mode included) so
one file opens offline; then `python3 <skill-dir>/scripts/check_page.py deck.bundled.html --gate section.present`
confirms no external loads, paired markers, gated fragments and the print guard per fragment
(it detects the host's gate, `section.present` or `.visible`; `--gate` overrides). Do not read the bundled file; verify it with the checker and
one `render-phases.sh --page deck.bundled.html --slide N 1920 1080 rest` render. Never add a CDN `<script>` or `<link>`
yourself; keep ones the user's deck already had and say so.

### 6. Audit
Run the checklist at the end of `references/motion-rules.md` before shipping.

## Hard rules
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
  `extract_slides.py` cannot see inside pictures.
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
- No `<script>`, `<link>`, `<image>`, `@import`, `@font-face` inside a fragment (step mode adds
  exactly one module script).
- Text at or above 18 px at rendered size, titles 22 px and up.
- Never add CDN or network loads. Work on a lean deck; bundle to one self-contained file only
  at hand-over when the user wants to share (`bundle_deck.py`, then `check_page.py`).
- The look follows `references/style.md`: no filled cards, chips or caption bars; rings and
  thin lines; one accent with glow; at most two semantic colours, each meaning something on
  the slide.
- Less. The fragment is the slide's own figure in its own form (stairs stay stairs, a table
  stays rows) plus one movement; no invented chart forms, no extra brackets, arrows or
  storylines, one glowing element at most and never a glowing line. When in doubt, leave it
  out (`references/style.md`, principle 0).
- Plays once. One pass of 4 to 10 s when the slide becomes current, iteration count 1 with
  fill forwards, the 100 % keyframe equal to the resting frame, nothing looping or pulsing
  while the slide is up. At most three things moving at once, `linear` only for continuous
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
- `scripts/extract_slides.py` — pptx/html/md to outline JSON with archetype suggestions
- `scripts/render_deck.py` — source deck to contact sheets (12 slides each) plus full-size pages for candidates
- `scripts/host_theme.py` — host glue: `--anim-theme-*` block derived from the deck's CSS (match) or the lean palette (lean)
- `scripts/md_to_deck.py` — Markdown or remark deck to a self-contained HTML deck to integrate into
- `scripts/scaffold_from_spec.py` — spec validation and spec to skeleton fragment (once, loop or step); YAML or JSON, PyYAML optional
- `scripts/check_fragment.py` — static contract checks
- `scripts/verify_facts.py` — provenance gate: fragment text and numbers against the source slide
- `references/style.md` — the visual style: lean, quiet, one accent, no boxes; checklist before shipping
- `references/accuracy.md` — accuracy rules: numbers from the source, labels in its words, figures redrawn at scale
- `scripts/render-phases.sh` — phase PNGs and contact sheet with headless Chrome
- `scripts/measure_slot.py` — free box of a slide in stage pixels, with viewBox and checker flags
- `scripts/check_page.py` — page-level checks: no external loads, paired markers, gated fragments, print guard
- `scripts/bundle_deck.py` — inline local (and with `--fetch`, remote) assets into one self-contained file
- `scripts/integrate_fragment.py` — idempotent inlining into a deck, gate rewrite, prefix safety net
- `scripts/snippets/observer.html`, `scripts/snippets/step-host.html` — host-side helpers
- `pool/` — finished, checked fragments, at least one per archetype, with thumbnails and specs; `pool/index.yaml` lists them (step 1b)

## Related skills (use them when your harness has them; none is required)
- A motion-design skill for deeper timing and easing guidance.
- GSAP timeline and plugin skills when building a step-mode fragment.
- A slides skill (frontend-slides, reveal.js, Slidev or similar) to produce the deck itself; a
  pptx skill to read PowerPoint sources beyond what `scripts/extract_slides.py` extracts.
