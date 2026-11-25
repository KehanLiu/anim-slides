# Maintainer notes

History and calibration data moved out of references/ so agents do not read it. Nothing here is a rule.

## From references/lessons.md: host deck stories

The rules these stories led to stay in `references/lessons.md`, "Host decks".

- 2026-11-18, Codex, "Make five slides introducing this project": frontend-slides was on disk
  but not registered in Codex, so anim-slides built the whole deck on its own lean dark ground
  and the frontend-slides look was applied afterwards as a reskin.
- `host_theme.py` read `font: 400 39px/1.35 Nunito` as the family "39px/1.35 Nunito" (the
  weight came before the size), so fragments fell back to the default font; fixed 2026-11-18.
- A branded deck full of rounded panels tempted the builder to redraw the panels in SVG and
  animate the wires between them; the user then saw "almost no change".
- `render-phases.sh --page --no-script` showed blank frames on decks whose own script both adds
  the gate class and shows the slide. In frontend-slides decks `.visible` is both the fragment
  gate and the class that shows the slide; the `rest` render strips it, and the slide stayed up
  only because the deck's script also set `.active`.
- Step control: the owner of this skill found an unasked step deck annoying.
- A rebuilt figure can be accurate and still wrong: a staircase re-plotted as a glowing line
  chart with brackets and arrows was rejected as "too much".
- A 4-slide pptx was extracted to Markdown, run through `md_to_deck.py`, and two slides were
  animated. The user's verdict: "super ugly, only the charts on slide 4 are good". The
  fragments were fine; the host was a Markdown dump (full-width title, a bullet list, a row of
  raw image thumbnails), and the pptx's own designed layout was gone before anim-slides started.
- Deck first on a frontend-slides deck (the same 4 slides, pptx to frontend-slides to
  anim-slides, match look, step control). It worked: the fragments dropped into a 1680x610 and
  a 1680x700 slot without size changes, `verify_facts.py` passed, and the user, who had called
  the `md_to_deck.py` attempt "super ugly", judged the fragments fine. Notes from that run:
  - The deck's entrance animations showed `.reveal` text only under `.slide.visible`, so rest
    renders and print showed empty slides. The class name `.reveal` also matches reveal.js
    detection in `host_theme.py`'s slide selectors (harmless in this run).
  - Markers round the slot div, as first written, let `--replace-until` delete the sized div.
  - The deck's Google Fonts / Fontshare link failed `check_page.py`'s external check on the
    lean working deck at the time (now one WARN); `bundle_deck.py --fetch` inlined 9 fonts and
    the bundled deck passed with 0 fail.
  - On the white match ground a fade level of 0.35 in the light line colour vanished; 0.6 read.
  - `extract_slides.py` missed a cover photo placed on slide layout 4 and reported a picture
    that does not show on the rendered slide.

## From references/lessons.md: run logs

### Two bare-prompt runs (2026-11-08)

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

Rules that followed (0.10.0, modelled on frontend-slides' "show, don't tell"), now in SKILL.md:
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

A fallback deck in the folder is not a decision. A 12-slide corporate pptx run under 0.10.0
found a `deck.md` from an earlier try, built the host with `md_to_deck.py`, wrote "user's
earlier choice" into Decisions and asked at intake whether to "keep the md_to_deck host". The
three fragments were good; the nine text slides around them were a raw dump, and the owner
asked why frontend-slides was not the base. Rule since 0.11.0: with a deck skill installed the
fallback is never used or offered; the intake deck question is full deck or lighter path only.

### Deck-first run on a 12-slide corporate deck (2026-11-08)

Under 0.11.0: frontend-slides built the deck from the pptx, three fragments, blind review "ship".
- **Worked:** a frontend-slides preset recoloured to the source's palette gave a deck that read
  as the source; the three fragments from the earlier run were reused unchanged; the blind
  review's verdict was "ship".
- **Gaps, fixed after the run:** `check_page.py` failed on the deck skill's own Google Fonts
  link (now one WARN; any other external load still FAILs); `bundle_deck.py` left
  `<link rel="preconnect">` to font hosts after inlining (now dropped when the host is gone);
  frontend-slides' own density question and three style previews broke "ask once" (now folded
  into the intake message, the closest preset chosen and named); the deck skill knew nothing
  about slots (the main thread passes W x H and position in its brief; padding, not margin,
  because a child margin collapses through the slot and shifts `measure_slot.py`'s box); the
  review page's Deck column was empty for the nine un-animated slides (Mode A renders every
  slide into `anim/review/after/`); the default mint `--anim-theme-ok` added a second hue on a
  single-accent orange deck (map it to the line colour or accent); fragment-mode `check_look`
  font WARNs are expected on a deck-skill deck (the `--page` run is the font check); the blind
  review images had no named place (`anim/review/blind/`).

### Motion vocabulary rebuild and two trap-deck runs (2026-11-16)

- **What was wrong:** 17 of 22 pool entries, six of seven archetypes and the spec's only
  motion word (`flow`) were a point advancing along a line, so every slide came out as a
  process diagram with a moving dot. Naming the motion before the form fixed it: one verb per
  fragment, chosen from the slide's claim (`references/motion-verbs.md`).
- **Two runs after the change:** `verbs-not-dots` (seven list slides) came out as accumulate,
  balance, sort, transform, nest, travel (the blood sample) and reveal; `arrows-are-not-travel`
  (cards joined by arrows) as grow, race, split, travel (the wallet) and reveal. One marker
  per deck, on the slide where a named thing travels; `check_verbs.py` passed on both.
- **Units:** without `data-anim-series`, builders moved rigid blocks, which read as a reshape,
  not a sort.
- **Morph:** a 100 % `d` that differed from the resting `d` used to pass every check and show
  only in a render, because `@supports` is a variant.
- **Counters:** values that ticked after the bar, the column or the units had landed were the
  most repeated review defect.
- **Accent:** lighting each part in turn over a finished drawing read as a highlight stepping
  along, the dot's cousin.
- **State changes:** with labels covered, a ticket whose border changes colour showed nothing.
- **Blind review on contact sheets:** at a 480 px thumbnail every 20 px label looked too small
  and that finding drowned the real ones.
- **Gaps seen in the runs, not yet fixed:** `check_look.py --page` scored slides that are
  invisible at rest on a deck whose reveal is keyed on its own class (the runs re-ran it on a
  copy, and one added the deck's `active` class to its CSS); `render_deck.py` output was
  cropped on both decks.

## From references/look-rubric.md: rationale

The checkers (`check_fragment.py`, `verify_facts.py`, `check_page.py`) prove the contract and
the facts. They cannot see that a slide is ugly or "too much". This rubric is the judgement
layer: a reviewer that knows nothing about the build first says what it reads from the
resting slide alone, and only then sees the other stills and the slide's claim and scores
them. A reviewer told the claim first confirms it. The skill runs it on its own work before
saying "done", and the eval runner uses it to score a corpus. It enforces `style.md` and
`accuracy.md` rule 0 by eye.

## From references/look-rubric.md: calibration

Run on 2026-11-08 with fresh reviewers (Opus, general-purpose, the prompt plus labelled
paths only; A and B with mark frames, C to E with the resting frame only, A and B with one
un-animated context slide). Scores are in item order: Form, Restraint, Space, Boxes, Colour, Type, Lines,
Rest frame (now Resting frame), Fidelity, Host fit. Idea and the Forms list were added on 2026-11-13, after
these runs; Idea's anchors come from the `prose-not-a-row` eval, not from a reviewer run.
Focal, Entrance and payoff, the first and pause frames, the claim line, the `ship`/`fix` verdict and the
Composition wording of item 3 (formerly Space: "centred, even margins") were added in look
v2 and are not yet calibrated. Item 14 (First read), the audience question and the two-step
order (first read recorded before the claim is shown, then scoring) were added on 2026-11-25
and are not yet calibrated either; the runs below had no first read.
The old `rebuild` verdict below is now a `fix` that rebuilds. The Colour anchor said "about a
tenth" of the drawn area at the time; it now says at most about a fifth, as style.md does.

| Baseline | What it is | Slide | Scores | Verdict |
|---|---|---|---|---|
| A | Markdown-dump host (`md_to_deck.py`), lean fragments | s3 | 5 4 3 5 4 3 4 5 3 **2** | fix |
| | | s4 | 5 4 4 5 5 3 3 4 4 4 | fix |
| | | context (un-animated s2: bullets + thumbnail row) | Host fit **1** | rebuild |
| | | **deck** | | **rebuild** |
| B | Same fragments in a designed deck (frontend-slides, match look, white ground) | s3 | 5 3 4 5 4 3 **2** 4 3 3 | fix |
| | | s4 | 5 4 4 5 5 3 **2** 4 4 3 | fix |
| | | **deck** | | **fix** |
| C | Public TB deck, bare-prompt run | s14 (table) | 5 4 4 5 4 4 4 4 5 4 | ship |
| | | s16 (iceberg) | 5 4 4 5 5 4 4 4 4 4 | ship |
| | | s27 (test flow) | 4 5 4 5 4 4 4 5 5 3 | ship (reviewer said fix) |
| D, round 1 | Public civics deck, resting frames of two process snakes | s23 | 5 4 4 5 4 4 4 4 **2** 4 | fix |
| | | s27 | 4 4 3 5 3 4 3 4 **2** 3 | fix |
| D, round 2 | Same images, revised wording | s23 | 5 4 4 5 4 4 5 **2** 4 4 | fix |
| | | s27 | 4 4 3 5 4 4 3 **2** 4 3 | fix |
| E | The "too much" case: stairs re-plotted as a line chart with an arrow and brackets, banner kept | s5 | **1** 4 3 **2** 4 3 3 **2** **2** **2** | rebuild |

What a 5 and a 2 look like, from these runs:
- **Form 5**: the TB comparison table kept as six rows in two columns; the iceberg kept as an
  iceberg. **Form 1**: E's four-step staircase redrawn as a level-over-time line chart.
- **Host fit 1**: A's un-animated slide, a raw two-level bullet list over a row of bright
  page thumbnails. **Host fit 2**: A's s3, a 64 px title wrapping onto three lines over the
  figure, with no footer. Same fragment in B: 3.
- **Lines 2**: B's dimmed "FROM" path at rest, light grey on white (style.md "Under a host
  theme" fade levels). The same fragment on A's dark ground scored 3.
- **Resting frame 2**: D's snakes, rows of identical empty rings or grey dots with one lit end
  node, where the source shaded the steps in order (round 2 only).
- **Boxes 2**: E's filled banner kept from the source.

What changed after round 1:
- D's empty-ring resting frames scored 4 with the first wording (the reviewer saw the
  identical rings and called it acceptable). Item 8 now caps that case at 2; round 2 flagged
  both slides.
- The C reviewer set "fix" with every item at 3 or above, following "when unsure, say fix".
  The verdict is now computed from the scores only; doubt goes into a lower score.
- The B reviewer folded the context slide into the animated slides' Host fit. The context
  image is now its own section, Host fit only.
- After round 2: D's dropped audience questions (yellow pills) scored Fidelity 2 in round 1
  and 4 in round 2. Item 9 now says a dropped callout or question is 3 at most. This clause
  is not yet calibrated.

Separation: A (rebuild) vs B (fix), driven by Host fit on the un-animated slide and the
title; E rebuild with Form 1; C ship on the scores. B's "fix" is a true finding (faint
dimmed lines on white), not noise. Expect a spread of about one point per item between two
reviewers on the same images (D, Fidelity 2 vs 4); the verdict is stable when a defect is
named in the rubric's anchors, so name a recurring defect there rather than trusting the
reviewer to weigh it.

Baselines A and B are a confidential deck and E is confidential; images stay outside the repo
and are referenced here by description only.

## From references/input-stage.md

- Fallback deck taken as the user's decision (section 1, "Deck first"): a 12-slide run read a
  `deck.md` already in the folder as the user's choice and delivered three good figures inside
  nine raw text slides.
- Default mint on a single-accent deck (section 3, "Look: match or lean"): the default `--anim-theme-ok`
  mint adds a second hue, and a blind reviewer flagged it on an orange deck.
