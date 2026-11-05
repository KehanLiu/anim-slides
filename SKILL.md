---
name: anim-slides
description: Turn boring slides into animation-rich HTML. Builds self-contained animated SVG illustrations (CSS keyframes, optional GSAP step-through) that replace text blocks and screenshots in any HTML slide deck, and creates them directly from documentation of processes, dependencies, timelines or architectures. Use when the user wants to animate a PPT/PPTX or HTML deck, "make this slide less boring", draw a process/pipeline/dependency graph/timeline/comparison as an animation, or turn a Mermaid diagram or a written procedure into an animated illustration. Not for generating a whole deck from scratch (use a slides skill first) and not for video.
license: MIT
compatibility: Python 3.9+ for the scripts; a Chrome or Chromium binary for phase rendering; any harness that can run shell commands and view PNG files.
metadata:
  author: Kehan Liu
  version: "0.4.0"
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
- **Existing deck**: run `python3 <skill-dir>/scripts/extract_slides.py deck.pptx|deck.html|doc.md -o outline.json`, then
  triage with `references/input-stage.md` (3 to 8 illustrations per 30 slides is normal).
- **Documentation**: read the source, pick the archetype with the table in
  `references/archetypes.md`, extract a spec (step 1).
- **Single slide request**: go straight to step 1 for that slide.
Ask the user only when the source is ambiguous about order, direction or grouping. Otherwise
state the assumption in the brief and continue.

### 1. Spec
Write `anim/<name>/spec.yaml` following `references/spec-format.md`: name, archetype, nodes,
edges, groups, phases with second marks, cycle, control (`loop` default, `step` only when the
presenter must drive phases or the story has four or more narrated phases). Reuse the
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
Measure the free box on the slide (`references/layouts.md`), pick a viewBox with the same aspect
ratio, and fill `anim/<name>/brief.md` from `references/brief-template.md`. The brief fixes
viewBox and rendered size, composition, phases, resting frame, theme tokens and min text size.
The quality of the fragment tracks the quality of the brief.

### 3. Build
`python3 <skill-dir>/scripts/scaffold_from_spec.py anim/<name>/spec.yaml -o anim/<name>/<name>.html --rendered-width <px>`
validates the spec and writes a contract-compliant skeleton (layout, phases, packets, notes,
resting frame; font sizes raised to the floor at the rendered width), then runs the checker on
it. The comment at the top of the output lists what to refine by hand. Refine it into the
illustration the brief describes, using `references/archetypes.md` for composition and motion
and `references/motion-rules.md` for timing and easing. For several illustrations, build one
fragment at a time from the shared briefs, or one parallel subagent per fragment if the harness
has them; integration always stays in the main thread.

### 4. Verify by looking
1. `python3 <skill-dir>/scripts/check_fragment.py anim/<name>/<name>.html --name <name> --rendered-width <px>`
   must pass (prefixes, tokens, gating, text size, forbidden content).
2. `<skill-dir>/scripts/render-phases.sh anim/<name> <W> <H> 1.5 4 7 10 rest` renders phase PNGs and a
   contact sheet with the paused plus negative-delay method. Open every PNG with your image
   viewing tool. Fix clipping, overlaps, unreadable text, empty panels. Iterate at least once.
3. The resting frame must read as a complete still (PDF export shows only that).
Never trust `--virtual-time-budget`, and never trust reading the source instead of the PNG.

### 5. Integrate
`python3 <skill-dir>/scripts/integrate_fragment.py deck.html anim/<name>/<name>.html --name <name> --anchor '<unique string in the slide>' [--replace-until '<string>'] [--gate 'section.present'] --backup`
hoists the style into the head, inserts the fragment between `<!-- anim:<name>:start -->` and `<!-- anim:<name>:end -->`
markers (the style between `anim-style` markers; re-running replaces both copies), rewrites the gate for the host deck, and prefixes any
class that slipped through. For plain pages copy `<skill-dir>/scripts/snippets/observer.html` into the page; for
step mode copy `scripts/snippets/step-host.html` into the head after a single GSAP script tag.
Then open the deck in a real browser and watch the slide once. Headless frames never prove
smoothness.

### 6. Audit
Run the checklist at the end of `references/motion-rules.md` before shipping.

## Hard rules
- Prefix every class, id and keyframe with `<name>-`. Host CSS has global `.bar .card .node
  .flow` rules and Chrome applies CSS width/height to SVG rects.
- No hard-coded colours or fonts: use `var(--anim-*)` tokens with the fallback block from the
  contract. Hosts retheme with `--anim-theme-*`.
- Animate only under the gate (`.visible` when authoring). The ungated state is the finished
  state.
- No `<script>`, `<link>`, `<image>`, `@import`, `@font-face` inside a fragment (step mode adds
  exactly one module script).
- Text at or above 18 px at rendered size, titles 22 px and up.
- At most three things moving at once, cycle 8 to 15 s with a hold, `linear` only for
  continuous loops, exits about 65 % of entrance length, reduced-motion block present.

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
- `scripts/scaffold_from_spec.py` — spec validation and spec to skeleton fragment (loop or step); YAML or JSON, PyYAML optional
- `scripts/check_fragment.py` — static contract checks
- `scripts/render-phases.sh` — phase PNGs and contact sheet with headless Chrome
- `scripts/integrate_fragment.py` — idempotent inlining into a deck, gate rewrite, prefix safety net
- `scripts/snippets/observer.html`, `scripts/snippets/step-host.html` — host-side helpers
- `pool/` — finished, checked fragments, at least one per archetype, with thumbnails and specs; `pool/index.yaml` lists them (step 1b)

## Related skills (use them when your harness has them; none is required)
- A motion-design skill for deeper timing and easing guidance.
- GSAP timeline and plugin skills when building a step-mode fragment.
- A slides skill (frontend-slides, reveal.js, Slidev or similar) to produce the deck itself; a
  pptx skill to read PowerPoint sources beyond what `scripts/extract_slides.py` extracts.
