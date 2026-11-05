# Changelog

All notable changes to this project. Versions match `metadata.version` in `SKILL.md`.

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
