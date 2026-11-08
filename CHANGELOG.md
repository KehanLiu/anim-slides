# Changelog

All notable changes to this project. Versions match `metadata.version` in `SKILL.md`.

## 0.9.0 - 2026-11-08

- **Step mode is CSS only; GSAP is retired.** A `step` fragment is now the same file as a
  `once` fragment (CSS keyframes, full-pass tracks, iteration count 1, 100 % keyframe =
  resting frame, no script). New wrapper attribute `data-anim-phases="2,4.5,7"` lists the
  phase stop marks; the scaffolder always writes it and all 22 pool entries carry it.
  `scripts/snippets/step-host.html` is a small plain script in the deck head that drives the
  fragment's CSS animations through the Web Animations API: the entrance plays with the slide,
  each forward key lands the next phase, back snaps to the previous mark, keys pass to the deck
  at either end, the phase is kept on return, reduced motion and print show the resting frame.
  Breaking for anyone with a GSAP step fragment: rebuild it as a `once` fragment with
  `data-anim-phases` and integrate with `--control step`.
- **`integrate_fragment.py --control once|step`** sets the control on the wrapper and, for
  step, inserts the snippet once and sets its gate. The control is a deck-wide switch at
  integration, reversible without touching fragments; `check_page.py` requires the snippet when
  a step wrapper is present.
- **One control per deck, asked at intake.** Next to the match-or-lean look, intake asks once:
  play once, or step through phases by click, with a recommended default. Recorded in the
  `anim/triage.md` header and each brief's Control field; a slide that differs needs a reason.
- `extract_slides.py`: a per-slide `builds` count and a deck total: click effects in pptx
  timing, reveal.js `.fragment` and `data-fragment-index`, `.build`/`.build-item`, impress.js
  `.substep`, nested `.step` build steps, remark `--`. A deck that already builds by click gets
  `step` recommended.

## 0.8.0 - 2026-11-07

- **Plays once.** The default control is `once`: one pass of 4 to 10 s when the slide becomes
  current, iteration count 1 with fill forwards, the 100 % keyframe equal to the resting
  frame. `loop` stays for kiosks, galleries and the hero, on request. All 22 pool entries,
  the scaffolder and the checker follow (the checker fails on `infinite` under `once`). The
  gallery gets a replay control per card.
- **Less.** New style principle 0 and a hard rule: the fragment is the slide's own figure in
  its own form plus one movement; no invented chart forms, extra brackets, arrows or glows.
  The checker measures motion and glow concurrency (at most three things moving, one glow visible, never a glowing line).
  Driver: a rebuilt slide where a staircase became a glowing line chart; the user: "that kind
  of stuff is too much".

## 0.7.0 - 2026-11-06

- **One look per deck: match or lean.** Intake now settles whether fragments take the host's
  palette and fonts (match, the default for branded decks) or keep the lean palette on a dark
  ground (lean), and shows the first fragment both ways before building the rest. New
  `scripts/host_theme.py` derives the `--anim-theme-*` block from a deck's CSS (`--mode match`)
  or writes the lean block (`--mode lean`), with `--apply` into the deck head between markers.
  `render-phases.sh --theme FILE` renders a fragment under a theme file.
- **Visible change rule.** A fragment replaces the slide's cards, pills, bullet column or HTML
  diagram; motion laid over the existing drawing with the boxes left in place is not allowed
  without a stated reason. A host theme changes colours and fonts only; the shape rules of
  `references/style.md` hold under any palette ("Under a host theme" section).
- **Triage is written down.** `anim/triage.md` lists every slide with a decision, the element
  the fragment replaces and a reason; a skipped slide without a reason is a defect. On short
  decks the 3-to-8-per-30 budget is a floor. Driver: a 10-slide corporate deck came back with
  3 slides animated in place and the user saw "almost no change".
- `extract_slides.py`: a `.step` inside a `<section>` or `.slide` is a build step, not a slide
  (a 10-slide deck with stair `.step` divs came out as 16 entries); `.step` is a slide only at
  impress.js top level.

## 0.6.1 - 2026-11-05

- `scripts/render_deck.py`: contact sheets of the source deck (12 numbered slides per sheet,
  no ImageMagick needed) so triage reads a few images instead of one per slide; full-size
  pages only for the candidates. Intake step and hard rule updated.

## 0.6.0 - 2026-11-05

- **Lean style.** New `references/style.md`: rings and thin lines, no cards or chips, one
  accent with a soft glow, mono sub-labels, plain captions, more space. Every pool entry and
  the scaffolder follow it; the default token palette changed to match (`#0F1E27` ground,
  `#34D1BF` accent). Hosts that set `--anim-theme-*` are unaffected.
- **Illustrations stay.** Rule: pictures that label a column, lane, category or actor are
  content; embed them beside the fragment (licence permitting) or redraw them as glyphs.

## 0.5.1 - 2026-11-05

Accuracy and hand-over, from two fresh-user runs and independent audits of every pool entry
and demo slide.

- **Provenance gate:** `scripts/verify_facts.py` checks a fragment's text and numbers against
  the source slide (invented numbers fail; untraceable wording and cross-slide facts are
  listed); `references/accuracy.md` holds the rules; both are part of "done" in SKILL.md and
  the contract.
- **Pool:** 22 entries across 16 fields (new: er-patient-flow, loan-decision, water-cycle,
  hiring-lanes, court-case, photosynth-respiration, funding-options, canal-lock, parcel-route,
  sales-funnel, comms-timeline, bloom-taxonomy, phase-changes); every entry fact-checked and
  rendered in the light theme.
- **Hand-over:** the working deck stays lean; `scripts/bundle_deck.py` makes one self-contained
  file when the deck is shared and `scripts/check_page.py` verifies it (no external loads, paired
  markers, gated fragments, print guard). `integrate_fragment.py` adds a print guard so
  reveal.js PDF export shows resting frames, and strips scaffold comments.
- **Markdown decks:** `scripts/md_to_deck.py` turns a Markdown or remark deck into a
  self-contained HTML deck to integrate into; `extract_slides.py` understands remark notes and
  directives; `render-phases.sh --page` takes `--slide` and `--no-script`.
- **Scaffold:** nothing is written outside the viewBox (it stops with the size needed),
  barycenter ordering with spec-order tie-break, edges routed around nodes, one path definition
  per edge, hold phase keeps the final highlights.
- **Slot measuring:** `scripts/measure_slot.py` prints a slide's free box, viewBox and checker
  flags, so no devtools step is needed.
- **Project:** `plugin.json`, CI matrix fixed (3.9 on ubuntu-22.04), README accuracy section.

## 0.5.0 - 2026-11-05

Tested on six real, openly licensed decks (civics, public health, research publishing,
economics, earth science, operations); every fix below came from those runs.

- **Hard rule:** charts, graphs, tables and scientific figures on a source slide are redrawn
  from their data and animated, never replaced by text.
- **Pool:** 18 fragments across 12 fields (health, finance, biology, law, earth science,
  engineering, HR, logistics, business, product, AI, software); `domain` field in
  `pool/index.yaml` and specs.
- **check_fragment.py:** `--stage-width` derives the text floor (12 px at 1280); resting-frame
  check no longer warns on elements without a base opacity (96 false warnings down to 1 on the
  test decks); new `index-collision` warning.
- **scaffold_from_spec.py:** two-row snake for long pipelines; N-column compare; `lanes: true`
  swimlanes for graphs; real decision diamonds; timeline groups as brackets; `--stage-width`;
  draw-on without the start dot; 0.8 s phase-gap rounding bug fixed; clearer YAML errors.
- **extract_slides.py:** reads table cells (`tables`), connectors and arrows, decision wording;
  keeps line breaks as spaces; skips slide-number placeholders; guesses titles on converted
  `.ppt` (`title_guessed`); reports `aspect`; ignores years in citations.
- **render-phases.sh:** writes to a temp folder (`--out DIR` to choose); accepts a file path;
  `--page` mode renders a finished host page, including its resting frame.
- **Docs:** loop vs step guidance, speaker notes as structure, parallel-builder hygiene
  (own scratch folders, own LibreOffice profile), transform-box and draw-on lessons.
- **Project:** live gallery (`scripts/build_gallery.py`, GitHub Pages), CI, issue and PR
  templates, CONTRIBUTING, README hero GIF and social preview.

## 0.4.0 - 2026-11-05

- Pool of nine checked fragments covering all seven archetypes (pipeline, graph, timeline,
  states, compare, layers, chart), each with a resting-frame thumbnail and, where scaffolded,
  its `spec.yaml`.
- Workflow step 1b: check the pool (and `$ANIM_POOL` for private pools) before building, and
  adapt a close match instead of scaffolding.

## 0.3.0 - 2026-11-05

- Initial public release: `SKILL.md` workflow (intake, spec, brief, build, verify, integrate,
  audit), fragment contract and references, and the scripts `extract_slides.py`,
  `scaffold_from_spec.py`, `check_fragment.py`, `render-phases.sh` and `integrate_fragment.py`.
- Agent Skills format for all mainstream harnesses, plus a Claude Code plugin marketplace.
