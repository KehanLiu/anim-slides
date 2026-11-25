# Changelog

All notable changes to this project. Versions match `metadata.version` in `SKILL.md`.

## 0.15.0 - 2026-11-25

- **A short path for one named slide** (`references/quick.md`). "Animate slide N" no longer
  runs Phases 1 to 3: no brief, no previews, no review agents, no review page. One page names
  the commands, carries the fragment rules the checker enforces and a table of which drawing
  fits which content (parts of one total get one cut bar, never a bar per row; no line runs
  through text). On a held-out set of 8 slides against plain Claude Code with the same short
  prompt (one run per slide, same-model reviewers), cost went from about 5 times plain to 1.7
  times and time from 4.8 times to 1.4 times. This replaces the Mode C reading list described
  under "Animate slide N spelled out" below. Deck-wide runs are unchanged.
- **Every source label stays** (`scripts/check_labels.py BEFORE AFTER --slide N`). Fails when
  a text run of the source slide is missing from the animated one. All four label defects of
  the baseline run were shortened or dropped labels. `tests/test_check_labels.py` covers a
  wrapped label, a shortened label, a changed unit and a dropped table heading.

- **A slide the user names always gets a figure.** In a blind comparison the skill answered
  "animate slide 3" with a byte-identical deck: the slide was a table of four waiting times
  with no takeaway sentence, so the triage called it a lookup. For a single named slide the
  triage now only decides what to draw, from the slide's own labels and values; a doubt is
  one line in the hand-over after the figure. Only a slide with nothing to draw (a title, a
  quote, one picture) still ships unchanged. Deck-wide runs keep the old rule.

- **Duration race, computed from the values** (`scripts/race_figure.py`, `archetype: durations`
  in the spec). Until now `race` was hand-built: the scaffolder gave a row skeleton and the
  builder drew bars, timing and the takeaway number by hand, so a corrected value meant
  editing three places. The spec now holds each label, value and unit as the slide writes
  them and `scaffold_from_spec.py` writes the finished figure: one scale, one speed (a bar's
  run time is proportional to its value), the difference or ratio as the focal number.
  Mixed units convert exactly (months or years against days need `calendar:`), an extreme
  ratio stays to scale, and a `claim:` sentence whose numbers no longer follow from the
  values stops the build and leaves the old fragment in place. `pool/mediation-vs-trial` is
  now built from its `spec.yaml` (viewBox 1680x748, the answer below the bars).
  `tests/test_race_figure.py` covers each case.

Two gaps found on the project's own five-slide deck (a frontend-slides deck, before and after
figures).

- **PDF export, one slide per page, every label kept** (`scripts/export_pdf.py`). The deck's
  own print rule set a 1920 px page, so printing on Letter cut the right third of every slide
  ("Upper gates", "Easy to review" and "Verify" were gone). And a resting frame cannot show
  what is on screen only during the pass: the canal-lock slide lost three step captions and a
  state label. The script prints a temporary copy on Letter and A4 landscape, scales a fixed
  stage to the page, and then reads the PDF back: one page per slide, every text piece of the
  slide's HTML on its page, inside the page box and drawn with ink. Labels the resting frame
  does not show go into a strip under their slide, on the same page. With `--source` (the deck
  before figures) the static slide's own wording is checked too and printed in the strip where
  the figure shortened it. Tests in `tests/test_export_pdf.py`; CI installs poppler.
  - `--install` writes the print rule into the deck, so the browser's own Print gives the
    same pages. The rule names no paper: the zoom is computed in CSS from the page
    (`tan(atan2(100vw, 1920px))`), so one rule fits Letter and A4.
  - Presenter notes (`aside.notes`, `.notes`, `.speaker-notes`, `.presenter-notes`,
    `.presenter-only`, `[data-presenter-only]`) are hidden in print and are not labels.
    Before this, a hidden note counted as a label "seen only during the animation" and was
    printed in the strip of the audience handout.
  - Tables are verified cell by cell (rows top to bottom, columns left to right, each
    drawn value used for one cell), and a label a slide carries several times must be drawn
    that often. Before this, one visible "12" stood in for every other "12".
  - An existing PDF is replaced only by an export that passed; a failing one is kept as
    `NAME.rejected.pdf` and the old file stays.
- **First read before the claim** (`references/look-rubric.md`). The blind reviewer used to get
  the stills and the claim in one call, and a reviewer told the claim confirms it. It now
  answers the slide's audience question from the final frame alone; the answer is recorded
  verbatim before the claim, the source slide and the other frames are sent. New rubric item
  14, First read, scores that answer against the claim. The audience question is a new field
  of the brief. Not yet calibrated.

Pre-launch cleanup and consistency pass.

- **One number per rule.** The references, `SKILL.md` and the checkers now agree: more than
  three things moving warns and more than six fails; accent at rest at most about a fifth;
  a label follows its part by 50 to 150 ms; a travelling marker for `travel` and the token
  trip of a `cycle`; triage decisions are `illustrate` or `text`; match is the default look
  for every deck and lean is the optional dark ground. Checker floors that the docs left
  vague (text contrast, type ladder, stillness, hues, faint lines) are written down.
- **"Animate slide N" spelled out.** Mode C writes a one-row triage, asks nothing, ships the
  slide unchanged when it has no Insight, and names the reference sections one figure needs.
  `SKILL.md` gains a short Terms section; `gate` now means only the CSS class.
- **Fact check in the final review.** Step 8 reruns `verify_facts.py --strict`, so a value
  beside the wrong label fails before hand-over.
- **Valid frontmatter.** The `SKILL.md` description no longer breaks strict YAML parsers;
  `tests/test_skill_frontmatter.py` guards it and the version strings.
- **README restructured** for a first-time visitor (what it is, try it, gallery, install, use);
  the script commands moved to `docs/scripts.md`. `CONTRIBUTING.md` and the issue and pull
  request templates describe the checks and the pool-entry format as they are now.
- **Removed:** `docs/intro-deck/` (a copy of `base/example.html`), `docs/motion-before-after/`
  (stale), `docs/media/hero.png` and `social-preview.png`, duplicate benchmark screenshots,
  dead code (`under_arc`, `over_arc`, `--no-pptx-lib`). Run logs and rubric calibration moved
  from the references to `docs/maintainer-notes.md`. `build_hero.py` moved to
  `.github/scripts/` (maintainer only).

## 0.14.0 - 2026-11-24

Look v2. Driver: the owner still found the slides "too ugly" and had six outside sources read
for what they could teach: the design skills oil-ui, taste-skill, impeccable and huashu-design,
and the motion galleries designbookmark.com/motion and prompt-motion.com. A read of our own
rules found the causes: all text between 18 and 30 px with size contrast forbidden, structure
lines at 1.5:1, the same centred even row in most figures, fade after fade on one curve, four
different easing values across the files, and a teal glow with mono labels, which two of the
sources name as the default AI-generated look. Rules were adopted, no code or assets copied.

- **Release review of the duration figure and PDF export (2026-11-25), four findings fixed:**
  - *A corrected figure could keep a false caption.* `race_figure.py` accepted any number in the
    claim that equalled some bar (15 and 14 minutes, "saves 14 minutes"). Each number is now
    bound to what the sentence says: a multiple to a ratio, a percentage to a percentage, a
    duration beside a comparing word to a difference in the sentence's unit, any other duration
    to a bar's own length. What cannot be tied down prints a `REVIEW claim:` line.
  - *Parsing and rounding could change the data.* `.5 s` was read as 5 s, `-3 min` as 3 min,
    `1 min to 3 min` as 4 min. Values are read whole or refused; compound durations must fall
    in one family; ranges, signs and leftovers are errors. Labels keep source precision (1.04 s
    and 1.01 s no longer both print as "1 s").
  - *The PDF exporter could approve a missing table cell.* Printed words are now assigned to
    one table cell each across all tables of a slide, so a hidden "12" in a second table fails
    and the label count drops. A hidden presenter note that repeats a visible label no longer
    rejects the PDF.
  - *A failing layout check replaced the last good figure.* The build is checked in a
    temporary file and replaces the output only when it passes.
- **Strict fact check knows the duration renderer's own labels.** On a fragment built by
  `race_figure.py`, `verify_facts.py --strict` recognises the scale legend, the axis unit,
  "<unit> longer" / "as long" and the aria-label sentences as closed templates and checks only
  their unit; `min` and `minutes` count as one word; a ratio or difference across units (18 h
  against 90 min = 12×) is a derivation. Bar labels, notes, the claim sentence and every
  number are checked as before. Mode C: the "drop the figure" check no longer applies to a
  slide the user named.

- **Question first:** a paired review (plain agent, one sentence of guidance, full skill) showed
  the skill building a figure for every source it was handed, a lookup table included. Each
  slide now starts from the question its audience should be able to answer. A base that
  answers it (a lookup table, a list, a statement) ships complete and at once, with no figure,
  intake or review page. A figure needs an Insight sentence ("by seeing X unfold, the audience
  understands Y better than from the still"), and its resting frame must show that insight and
  answer the question without the motion. Triage gains Question and Insight columns, the brief
  the same fields; the short-deck budget floor is gone (the budget is a cap, zero is valid).

- **Type ladder:** hero 56 to 96 px (one per figure, only a number or word the source states),
  label 24 to 30, sub-label 18 to 20; any two sizes at least 1.25x apart, at most four sizes,
  tabular numerals, sentence case. "No size jumps" is gone.
- **One focal element:** `data-anim-focal` on the one thing the eye lands on at rest.
- **Accent only in the light:** structure in `--anim-line` at 2 px and at least 3:1 (fallback
  `#56707F` on dark, `#768A95` on light, was 1.5:1), active path 4 px accent, reached parts
  stay accent without glow, one glow at most, accent at most about a fifth of the ink at rest;
  when every part ends up reached, the reached parts settle to the foreground colour.
- **Mono is for data:** numbers, units, codes, formulas. Names and terms use the text font.
- **Fonts:** a figure takes the deck's font in match and lean; better standalone fallback
  stacks; still no embedded or web fonts.
- **One easing set:** enter, move, exit, land (about 3 % overshoot, small marks only), linear.
  These literal curves are the only ones allowed, in every file.
- **Entrance by kind:** lines draw on, nodes land when their line arrives, areas reveal by
  clip, labels rise just after what they name. Stagger 40 to 120 ms and uneven, 600 ms per
  group at most; 400 to 600 ms of stillness before the answer step.
- **Composition:** not a centred even row by habit; the focal step gets room; anchor lines;
  at least 60 % of the slot; at most 12 nodes and 8 spokes.
- **Setup, then payoff:** the first frame leaves a visible gap (an empty jar, a level short
  of its line, two groups apart) that the pass closes; a "moving poster", where everything
  already stands in place and only animates in, is a fault. The brief names the gap and the
  beat that closes it; rubric item 13 is now Entrance and payoff.
- **Form from the data relationship:** a share becomes a scaled object or a split whole, a
  change over time one curve or level, a composition one split whole, a scale one large thing
  beside a familiar reference, before and after two pictures that differ in one place. No row
  of big numbers beside a bar chart, no number cards. A slide's own figure keeps its form.
- **Brief:** a beat table (time, on screen, what moves, end state, why) and the focal element
  are written before any SVG.
- **Review:** `look-rubric.md` has 13 items with a squint test, a labels-covered test and a
  specificity test; a fresh reviewer sees stills only and answers `ship` or `fix` (at most
  three problems, ranked), two rounds at most; a figure still being rebuilt after round two
  goes back to its brief.
- **Polish loop:** after the first render the builder writes the three worst problems, ranked,
  fixes only those and renders again, and names the one thing whose removal improves the
  figure. One round always, a second when the first changed the composition.
- **Random-pause check:** the stills include three paused frames between the marks; each must
  look intentional on its own (no half-overlap, no orphan label, at most three things moving).
- **`check_fragment.py`:** new findings `easing-set`, `fade-after-fade`, `mono-costume`,
  `type-ladder`, `focal` (WARN; two focal elements FAIL), `overshoot` (FAIL), `node-count`
  (scaffolded output only), `stillness` (WARN: no 400 to 600 ms stillness before the answer
  step; a continuous trace is exempt). Draw-ons, lands and clip reveals of things appearing for the first
  time now count as one staggered reveal, as fades did.
- **`check_look.py`:** new WARN findings `line-contrast`, `accent-area` (measured from
  rendered pixels; warns above 25 %), `focal`, and a 60 % extent warning under `density`.
  `--at-pauses` picks three reproducible times between 0.5 s and the last mark, prints them
  and checks each frame on its own (finding `pause`, WARN); the reviewer gets the same three
  frames.
- **`host_theme.py`:** the line token is moved to 3:1 in match mode; lean keeps the deck's
  font; the mono fallback is a real mono stack.
- **`scaffold_from_spec.py`:** output follows all of the above; new optional spec key `focal`.
  When a story ends with every part reached, the reached marks settle to the foreground colour
  and the focal element alone keeps the accent. Loop control passes the concurrency check (the
  figure fades as one group at the reset); step control ends all motion before the last mark;
  hairlines and brackets draw on. A one-row figure filling under 40 % of its viewBox gets the
  viewBox height cropped to the strip, with a note in the log.
- **`host_theme.py` on a light ground:** rules on `:root[...]` or `html.class` that match the
  deck's `<html>` tag are now applied, and the deck's own status colours are read, so the base
  deck's light ground no longer hands figures the dark palette's green and yellow.
- **Pool:** all 37 fragments reworked to the new rules with new thumbs; facts, verbs, pass
  lengths and viewBoxes unchanged, four fragments have later phase marks. Most gained a hero
  number or word. Every fragment passes both checkers with no warning, on the dark ground and
  on the base deck's light ground, at rest, at every phase mark and at three paused frames.
- **CI:** `check-pool.sh` runs `check_look.py` with `--at-marks --at-pauses`.
- **Base deck:** new line tokens, mono stack, one true contrast rule; its example figure
  follows the rules.
- **`references/archetypes.md`:** now describes what the scaffolder draws (rings, not rects
  and pills).

**Launch readiness**, in the same release: a demo a visitor can trust, replay and reproduce on
one slide.

- **README demo traced to its source:** the parcel figure no longer shows invented details
  ("Van 7 · 32 stops", timestamps, "tracked live"); every label comes from
  `examples/first-slide/source.html`, which is also the GIF's "before" frame.
  `scripts/build_hero.py` rebuilds the GIF from a source slide and a fragment;
  `tests/test_readme_demo.py` runs `verify_facts.py --strict` on the pair.
- **Values stay with their labels:** `verify_facts.py` gains a `pairing` check. A value shown
  next to the wrong label (Checkout 80 ms when the source says 200 ms) fails `--strict` and
  warns otherwise; correct pairs pass in any row order; undecidable cases are a `review:`
  warning in both modes.
- **Gallery:** opens on the `service-deps` figure under one question, with Replay, a copyable
  prompt and a direct link (`#featured`); the searchable gallery follows. Every entry has
  "Download playable demo" (`<name>-demo.html`: opens from disk, no network loads, plays once,
  Replay, finished figure in reduced motion and print) and "Copy embeddable HTML" (the
  unchanged script-free fragment). `build_gallery.py --demo FRAGMENT -o OUT` wraps any fragment.
- **First example:** `examples/first-slide/` (source slide, prompt, unedited result) near the
  top of the README, with the output format and the PowerPoint rendering dependencies.
  `docs/benchmark/first-slide/` records one run with and one without the skill.
- **Tests:** `tests/` (stdlib `unittest`, 38 tests, rendered checks through headless Chrome),
  run by `.github/scripts/check-pool.sh`.

## 0.13.0 - 2026-11-24

Figures inside a deck skill's draft. Driver: the owner wants "Make five slides introducing
this project" to work as a chain: the deck skill builds a finished draft with figure slots,
anim-slides fills the slots without changing the layout, and the figures look native and stay
readable through the whole pass, not only at rest. A Codex test the same day showed the chain
breaking: frontend-slides was installed on disk but not registered in Codex, so anim-slides
drew the deck itself on its lean dark ground and the deck's look came afterwards as a reskin.

- **Deck from a topic:** a new Mode A row for "make N slides about X" with no deck. A deck
  skill builds the base first, with slots; anim-slides never designs the deck's look and never
  reskins afterwards. A deck skill counts when its SKILL.md is on disk in any harness's skills
  folder (`~/.claude`, `~/.agents`, `~/.codex`, `~/.config/opencode`, `~/.cursor`, `~/.gemini`,
  and the project's), not only when this harness lists it; `md_to_deck.py` stays the labelled
  fallback when none is found.
- **Short prompt:** no intake message; the defaults (the deck skill's recommended style, match,
  once, not bundled) are taken, recorded and reported. Match is the stated default for any deck
  a deck skill built.
- **Stay in the layout, match the deck:** new hard rule. The figure fills the slot at its
  measured size; slide layout, headlines and deck CSS stay. Labels take 0.7 to 1x the deck's
  body size in its family and weight.
- **`check_look.py --at-marks`:** contrast and the text floor run at every phase mark too (clip
  and overlap already did), with one `marks` line per mark. A caption that is only on screen
  mid-pass is now checked; on `canal-lock` over a white ground the rest-only run missed three
  such captions. New `gap` check in `--page` mode: fragment ink covering the slide's own text
  or pictures fails, nearer than `--min-gap` (24 px at a 1920 window) warns.
- **`review_page.py` shows the motion:** the owner opened a review page and said "but that has
  no animation effect": it held PNG stills only. Each animated slide's after column now shows
  the fragment live, taken from `--deck` (between its markers, or by its `div.anim.anim-NAME`
  wrapper and `.anim-NAME` rules), on the slide's ground with the deck's `--anim-theme-*`
  values resolved (`anim/host-theme.css` fills gaps); a deck gate such as `section.present` is
  rewritten to `.visible`. It plays one pass when scrolled into view, Replay plays it again
  (the gallery's technique), reduced motion shows the resting frame, print shows the still,
  which stays below at a smaller size. A fragment that cannot be extracted keeps the still with
  a WARN naming the slide; `--no-live` gives the stills-only page.
- **`measure_slot.py`:** a fourth output line, `type body PX WEIGHT "FAMILY"; title ...`, the
  slide's own type as rendered, for sizing the fragment's labels.
- **`host_theme.py`:** a `font` shorthand with a leading weight (`400 39px/1.35 Nunito`) gave
  the size as part of the family; the family is now read after the sized token.
- **Built-in base deck (`base/`):** for a topic with no deck when no deck skill is found
  anywhere. `base/deck.html` is a template: 16:9 stage, keyboard and swipe navigation, the
  `.visible` gate, progress bar, print and reduced-motion rules, the five slide types (cover,
  live demo, benefits, workflow, call to action) with named slots, all colours and fonts as
  variables with every `--anim-theme-*` mapped to them. One look, two grounds via
  `data-ground="dark|light"` on `<html>`; the light ground is designed for contrast (text
  14.9:1, muted 6.5:1, accent 5.0:1, ok/warn/danger 5:1 or more), so `canal-lock` passes
  `check_look.py --at-marks` on it unedited. `base/example.html` is the finished five-slide
  intro deck on the base (copied to `docs/intro-deck/index.html`); `base/README.md` gives the
  ground rule and the composition rules with sizes. Order stays base first, figures on top;
  the hand-over says in one line that the built-in base was used and that a deck skill such
  as frontend-slides offers more looks. Nothing is installed automatically.
- **`md_to_deck.py`:** takes its colours and fonts from the base deck's token block and its
  ground from `--ground dark|light` (`--theme` still accepted); the layout stays a document
  flow.
- **`references/reference-case.md`:** the five-slide intro deck (cover still of `canal-lock`,
  the full `canal-lock` pass, benefits, workflow row, call to action), with what anim-slides
  adds on each slide and the rule it shows, with a deck skill or on the built-in base.

## 0.12.0 - 2026-11-18

Motion that carries the meaning. Driver: the owner's review, "we basically just build process
diagrams and have a moving point from start to end". An audit found 17 of 22 pool entries
were a point advancing along a line, six of seven archetypes were nodes, connectors and a
marker, the spec could only say `show`, `active` and `flow`, and the style rules named the
traveller "a glowing dot". Other agent skills for video and slides (Remotion, HyperFrames,
Manim skills, frontend-slides, visual-explainer) and the research on explanatory animation
(Tversky, Heer and Robertson, Bostock) point the same way: pick the motion from the claim.

- **Motion verbs:** new `references/motion-verbs.md`: twenty verbs (grow, count, accumulate,
  thin, race, split, merge, sort, stack, nest, transform, wipe, switch, balance, drive, zoom,
  open, travel, trace, cycle) and three support moves (reveal, mark, dim), a table from the
  grammar of the slide's claim to a verb, what each puts on screen, and the CSS/SVG
  mechanism. One verb per fragment; the verb's move takes 40 to 60 % of the pass.
- **The travel test:** a travelling marker belongs to `travel` (a thing the source names,
  between places it names) and to the one trip of a `cycle`. Order-only slides build with
  `reveal` and have no traveller.
- **Spec, scaffolder, contract:** top-level `verb:` and `traveller:`; phase keys `dim`, `mark`
  and `switch`; `flow` draws a packet only under `travel`; verbs the scaffolder cannot draw get
  the static frame, the timing and a hand-build note, never a dot. Fragments carry
  `data-anim-verb`. The triage has a `Verb` column, the brief `Verb:`, `Traveller:` and
  `Mechanism:`; the brief's worked example is a savings jar that fills.
- **Extractor:** `suggested_verb` and `verb_cues` per slide from the claim's wording;
  connectors, numbering and "step" no longer make a confident pipeline (capped at 0.3 with
  `reveal`); title slides get no suggestion.
- **Rules:** `style.md` and `motion-rules.md` no longer prescribe the dot: the subject's own
  object before a ring, one hero move with follow-through, a `change` duration class of 0.9
  to 1.8 s, a `d` morph inside `@supports` over a cross-fade base, techniques for units, a
  digit strip, a wipe and a cutaway.
- **Pool, 22 to 37 entries:** fifteen new entries, one verb each, outside IT
  (`compound-interest`, `petition-threshold`, `mediation-vs-trial`, `mitosis`,
  `coalition-majority`, `blood-types`, `number-sets`, `oxbow-lake`, `street-redesign`,
  `contract-formation`, `energy-balance`, `breathing`, `leaf-stomata`, `earth-layers`,
  `forgetting-curve`); five dot entries reworked (`bloom-taxonomy` stacks, `job-states` and
  `phase-changes` switch in place, `service-deps` closes a boundary around an outage,
  `cache-compare` is a race of bars). Seven entries use a travelling marker, each with a
  named traveller. Every entry has `verb` in `index.yaml`; the gallery filters by verb.
- **Checks:** `scripts/check_verbs.py` (a verb on every fragment, a reason on each repeat over
  a third of a deck, markers only under `travel` or `cycle`; `--pool` holds the pool to a
  third, in CI). `check_fragment.py`: `verb` check, a declared staggered series of units
  counts as one move (`data-anim-series`), `@supports` blocks are checked as a variant and a
  morph must end on its resting `d`. `check_look.py` reads `inset()` and `polygon()` clips
  from the browser.
- **Evals:** `verbs-not-dots` and `arrows-are-not-travel`: lists and arrow-joined cards whose
  claims are an accumulation, a balance, shares, a race, a split, with one real journey and
  one order-only control each. Each was run once by a fresh agent: seven verbs on seven
  slides and five on five, one marker per deck, `check_verbs.py` passing on both.
- **Review and page:** two blind reviews of the new and reworked pool entries from contact
  sheets, with the fixes applied; `docs/motion-before-after/` shows the five reworked entries
  next to their old versions. `data-anim-verb` may name up to two supporting verbs after the
  main one. Lessons from the work are in `references/lessons.md`.

Picture first. Driver: on long documents and card decks the skill drew nearly every slide as
a row "step 1, step 2, step 3". Selection went keyword, archetype, nearest pool entry; nothing
asked what the idea looks like, and the review loop treated any other form as "too much".

- **Picture idea and form:** `references/archetypes.md` opens with a step before the
  archetype: one sentence on what the slide says beyond the order of its items, and a table
  from that idea to a form (ring, funnel, fill level, two sides, lanes, scene, row for order
  only). The seven archetypes become build families. Triage gains `Idea` and `Form` columns,
  the brief `Picture idea:` and `Form:`, and "Forms across the deck" re-reads slides when one
  form repeats.
- **Scope of "keep the form":** `style.md` 0 and `accuracy.md` 0 separate a slide with its own
  figure (form kept, as before) from a slide of prose, bullets, cards or a text table (form
  from the structure the source states). Nothing the source does not state is drawn in either.
- **What motion can mean:** new section in `motion-rules.md` (level, count, dots at scale,
  trajectory, merge and split, ghost of the old state, rotation, clip reveal), all under the
  one-pass limits. The 5 % scale limit covers emphasis only.
- **Rubric item 11, Idea,** and a Forms list per deck in `look-rubric.md`; "too much" is
  limited to things the source does not state. Not yet calibrated.
- **Eval `prose-not-a-row`:** falling counts, a cycle and a trade-off written as numbered
  steps, plus an order-only control that must stay a row.
- `extract_slides.py`: `idea_cues` (evidence for the picture idea) and `order_only` on
  pipeline suggestions; confidence capped at 0.3 when a cue contradicts the row.
- Pool: `form` and `moves` on every entry; lookup goes by form first. `check_look.py` treats
  shapes marked `data-anim-scene` as scene ground; canal-lock and water-cycle use it instead
  of the per-file opt-out. `spec-format.md` corrected to what the scaffolder draws.

## 0.11.0 - 2026-11-08

Self-test: "no ugly slides, no matter the input". Driver: the owner asked how the skill can
test itself, and pointed at frontend-slides' quality floor (design recipes, a banned list,
screenshots).

- **Rendered-look lint:** `scripts/check_look.py` opens a fragment (or `--page DECK --slide N`)
  in headless Chrome at rest and at every phase mark and fails on clipped or overlapping
  labels, text under its contrast floor against the real ground, text-holding boxes, too many
  hues, text under the size floor; warns on faint lines, labels on fills, missing fonts, a rest
  frame that differs from the last mark, empty or crammed slots. Runs on every pool entry in
  CI. First findings: an unfilled tag in cache-compare (fixed); the light-theme status colours
  under 4.5:1 on white (README example and `host_theme.py` defaults darkened).
- **Blind review:** `references/look-rubric.md`: ten scored items with 5/3/1 anchors, a verdict
  rule and a verbatim prompt for a fresh reviewer that sees only before/after PNGs; calibrated
  on the Markdown-dump deck (rebuild), the glowing line chart (rebuild), two bare-prompt runs
  and a frontend-slides rebuild. Phase 2 step 8 and the hard rule "Reviewed blind".
- **Eval corpus:** `evals/` with twelve trap cases in the `claude plugin eval` format (twelve
  unrelated bullets, dense table, chart as picture, long German words, CJK labels, faint light
  theme, 4:3 stage, 15-event timeline, 20-node graph, icon columns, switch an animated deck to
  step), each with verifiable graders; `evals/README.md`.
- **Pool first:** Phase 2 starts from the pool entry of the matching archetype and adapts it;
  scratch builds only when no entry has the shape (frontend-slides' template floor).
- `extract_slides.py`: HTML stage read from the deck's CSS, viewport meta or reveal.js config
  (`stage_source`), so a 4:3 deck is no longer reported as 16:9; Chinese and Japanese cue words
  and dates for archetype suggestions.
- **Follow-up** (deck-first run on a 12-slide corporate deck): `check_page.py` reports a link to
  a web-font host (Google Fonts, Fontshare, Typekit, Bunny) as one WARN, not FAIL; other
  external loads still FAIL. `bundle_deck.py` drops preconnect/dns-prefetch links to hosts no
  longer referenced. SKILL.md and input-stage.md: Mode A folds the deck skill's own questions
  (density, style) into the one intake message; the main thread passes slots to the deck skill
  (padding, not margin); Mode A renders every slide for the review page, `--title` passed;
  `--anim-theme-ok` mapped to line or accent on a single-accent match deck; fragment-mode font
  WARNs on a deck-skill deck are expected; blind-review files under `anim/review/blind/`.

## 0.10.0 - 2026-11-08

- **"Show, don't tell" restructure** of SKILL.md, modelled on frontend-slides: Phase 0 reads the
  request into a mode (A deck first, B animate in place, C single slide, D illustrate from
  docs, E re-integrate with `--control` / `--mode`, no rebuild); Phase 1 shows first and asks
  once; Phase 2 builds silently; Phase 3 delivers by showing. "Improve the slides" and "add
  more animations" mean the same: figures replace text blocks and screenshots, nothing else
  changes; "more" reads as the upper end of the 3-8 per 30 budget. Workflow text cut where a
  reference already holds the rule.
- **One intake message.** The five separate "ask the user" points (triage approval, look,
  control, ambiguity, hand-over) become one message, via the harness's structured-question UI
  when there is one. Nothing is asked after it; defaults taken go into a Decisions section of
  `anim/triage.md`. Ambiguous order, direction or grouping becomes a stated assumption; an
  unreadable figure is traced and tagged "traced from <source> figure".
- **First fragment rendered before asking**: integrated into its slide at rest under match and
  under lean, plus both readings when a slide has two plausible figure forms.
- **Lighter path** for Mode A: the intake message announces the deck rebuild and its cost and
  offers standalone animated slide pages for the chosen slides only.
- **`review_page.py` at delivery**: a before/after page of every animated slide is the report;
  the closing message is a few lines with the two later switches.
- **Mark definition unified** (SKILL.md, contract, brief template, input-stage): a phase mark is
  a settled moment between narrated steps, three to five per slide (six for six narrated
  steps), the last at the hold start.
- **Slot markers inside the slot**: `<div id="sN-slot"><!-- sN-body -->...<!-- /sN-body --></div>`;
  markers round the div let `--replace-until` delete the sized div.
- **Scaffolder scope stated**: plain forms of the seven archetypes; triangles, donuts, bars,
  timelines with event text are hand-built from the spec.
- Fixes folded in: SKILL.md's `verify_facts.py` command gains `--spec`; number slides by
  `outline.json` (`render_deck.py` skips hidden slides); take the final screenshot from the
  running deck when the rest render hides the deck's own staggered text; compare a
  usage-count accent from `host_theme.py` with the deck's CSS; pass `--stage-width` to the
  checker. New lesson "Two bare-prompt runs (2026-11-08)".

## 0.9.1 - 2026-11-08

- **Deck first.** Intake now starts with "Get an HTML deck first": an HTML deck proceeds; a
  pptx, Markdown, remark deck or document goes through a deck skill before triage (the user's
  own, else `frontend-slides`, picking the preview closest to the source's brand). The pptx
  stays the source for `extract_slides.py` and `render_deck.py`; integration and the match look
  target the deck the skill produced. New hard rule: anim-slides styles fragments, never the
  deck. Driver: a pptx extracted to Markdown and run through `md_to_deck.py` came out "super
  ugly, only the charts on slide 4 are good"; the fragments were fine, the host was a plain dump.
- `md_to_deck.py` is documented as a fallback host for when no deck skill is installed, not a
  designed deck (docstring, `--help`, SKILL.md, `references/input-stage.md`, README); the agent
  says so to the user in one sentence. No behaviour change.
- `references/input-stage.md`: new "Deck first" section on the division of labour (deck skill
  owns layout, typography and slide design; anim-slides owns the animated figures). New lesson
  in `references/lessons.md`.
- **Rules from a real deck-first run** (pptx to frontend-slides to anim-slides, 4 slides, match
  look, step): ask the deck skill for a fixed-size `#sN-slot` between `<!-- sN-body -->`
  markers (exact `measure_slot.py --selector`, clean `--anchor`/`--replace-until`);
  `render-phases.sh --page --no-script` only for timed frames, never `rest` (`.visible` both
  gates and shows the slide in frontend-slides decks); check slide text shows without the deck
  script and in print, keying `.reveal` entrances also on the active class; a deck skill's
  web-font link is the deck's load and `bundle_deck.py --fetch` inlines it; step listens to
  keys only, so present with the keyboard or a clicker; on white match grounds raise faded
  opacities to 0.55 to 0.65; compare the `host_theme.py` block with the deck's own variables
  once; a picture count that differs between `outline.json` and the render points at layout
  pictures. SKILL.md, `references/` (input-stage, style, fragment-contract, brief-template,
  lessons).
- Scripts: `extract_slides.py` reports pictures placed on the slide layout; `host_theme.py`
  reads frontend-slides' variable names (`--bg-primary`, `--text-primary`, `--text-secondary`,
  `--accent-glow`, `--slide-bg`).

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
- **One control per deck.** `once` by default for the whole deck; `step` only when the user
  asks for click-through (a source that builds by click earns a one-line mention, not a
  recommendation). Recorded in the `anim/triage.md` header and each brief's Control field; a
  slide that differs needs a reason.
- `extract_slides.py`: a per-slide `builds` count and a deck total: click effects in pptx
  timing, reveal.js `.fragment` and `data-fragment-index`, `.build`/`.build-item`, impress.js
  `.substep`, nested `.step` build steps, remark `--`; the signal for mentioning `step`.

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
