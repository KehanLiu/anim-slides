# Look rubric: review by a fresh pair of eyes

The checkers (`check_fragment.py`, `verify_facts.py`, `check_page.py`) prove the contract and
the facts. They cannot see that a slide is ugly or "too much". This rubric is the judgement
layer: a reviewer that knows nothing about the build looks only at rendered PNGs and scores
them. The skill runs it on its own work before saying "done", and the eval runner uses it to
score a corpus. It enforces `style.md` and `accuracy.md` rule 0 by eye.

## 1. How to run a review

**Images, per animated slide** (name them by slide; the reviewer sees nothing else):
- `sN-before.png`: the source slide (`anim/render/full/p-NN.png`).
- `sN-after.png`: the integrated slide at rest (`render-phases.sh --page deck.html --slide N <W> <H> rest`).
- `sN-mark-<t>.png`: the phase-mark frames, when motion matters (always for the first review
  of a deck; `render-phases.sh --page ... <marks...> rest`). Without them Restraint is scored
  from the rest frame only and the reviewer says so.
- Once per deck, `context-after.png`: one slide of the integrated deck that was **not**
  animated (a text slide next to an animated one). A host that is a Markdown dump shows there
  first.

**Who runs it.**
- The main thread, in Phase 2 step 7, after `check_page.py`: one reviewer for all animated
  slides of the deck, batched in one call.
- The eval runner, once per case, with the same prompt.

**The loop.**
1. Spawn one fresh reviewer (a subagent with no prior context; in Claude Code the Agent tool,
   general-purpose). Give it **only** the prompt in section 3 and the image paths with their
   labels. No brief, no spec, no triage, no conversation, no hint at what was changed or what
   you worry about: a reviewer told the hypothesis confirms it.
2. It returns a table of scores, the three worst defects and a verdict.
3. A score below 3 on any item blocks "done". The builder fixes the named defects, re-renders,
   and runs a **new** fresh reviewer (not the same one: it has seen the old images).
4. At most two rounds. Defects left after round two are listed in the hand-over message and
   in the Decisions section of `anim/triage.md`, one line each, with the slide number.

A reviewer can be wrong about facts it cannot see (it has the source slide, not the notes).
A Fidelity complaint about a label that the notes or a figure transcription support is
answered in the triage, not "fixed".

## 2. The rubric

Score each item 1 to 5 per slide; 4 and 2 sit between the anchors. Judge the **after** image
against the **before** image.

| # | Item | Question | 5 | 3 | 1 | Enforces |
|---|---|---|---|---|---|---|
| 1 | **Form** | Is the figure the slide's own figure in its own shape? | Same form as the source (stairs stay stairs, table stays rows, cycle stays a ring, two columns stay two columns), redrawn quietly | Form recognisable but bent: an extra axis, brackets or arrows the source lacks, a sequence turned into a chart | A different figure: stairs re-plotted as a line chart, rows turned into a flow, a new storyline; or the source figure dropped for text | style.md 0; accuracy.md 0 |
| 2 | **Restraint** | Is there one movement and at most one lit element? (mark frames) | One thing moves per phase; one element glows at most; nothing repeats across marks | Two things compete in one frame, or a second glow, or a decorative extra (arrow, star, halo) | Packets or pulses repeated across marks, several glows at once, everything lit, motion layered over a busy figure | style.md 0, 8, 9 |
| 3 | **Space** | Does the figure fill its slot with room to breathe? | Figure about 60 to 70 % of the free area, centred, even margins, no crowded corner | Slightly cramped or slightly lost (a large empty band, a label near an edge) | Crammed (labels touch, figure runs into the title or footer) or a near-empty slot with a small figure | style.md 1 |
| 4 | **Boxes** | Are there boxes where the meaning has none? | No filled panels, cards, chips, pills or caption bars; rings, dots, labels on lines, hairline brackets; rectangles only for real containers (table, chamber, database) | One or two framed or tinted elements that carry no meaning | The source's cards or pills redrawn (filled, coloured, rounded) or left in place with motion on top | style.md 2; SKILL.md "Make a visible change" |
| 5 | **Colour** | Ground, ink, one accent, at most two meaning colours? | One accent marks what matters; at most two semantic colours, each with a meaning the slide states; palette belongs to the deck | A third hue, or a semantic colour with no stated meaning, or the accent spread over many elements | A rainbow: several accents, colour as decoration, palette clashing with the deck's own colours | style.md 3; "Under a host theme" |
| 6 | **Type** | Can every word be read at a glance, with a clear hierarchy? | Labels large and even, sub-labels smaller and muted, nothing clipped, overlapping or crossing a line; title belongs to the slide | One size jump too many, a crowded label, small sub-labels, a near-collision | Text too small to read on a projector, clipped or overlapping words, labels on top of lines or each other | style.md 5, 6; contract text floor |
| 7 | **Lines** | Are strokes quiet and visible? | Thin even strokes for structure, a heavier accent only on the active path, small open arrowheads; every line visible on its ground | Strokes a little heavy or a little faint, arrowheads large | A glowing line, thick strokes everywhere, or lines so faint on a white ground they vanish | style.md 4, 8; "Under a host theme" fade levels |
| 8 | **Rest frame** | Does the resting image tell the finished story on its own? | The complete figure: every step, value and label present, the end state visibly reached (final step marked, all data drawn), looks intended | Complete but flat: nothing shows where the story ended, or one element looks mid-fade | Empty or half drawn: blank slot, only the start of the story; would print as an unfinished figure. A row of identical neutral markers (empty rings, grey dots) where the source showed progress, order shading, values or a highlighted outcome scores 2 at best | contract resting frame; style.md 9 |
| 9 | **Fidelity** | Are labels, numbers and the figure the source's own? | Every label and number visible on the before slide (shortened, not paraphrased); illustrative or traced tag where values are examples; the source's meaning-carrying icons kept or redrawn | One reworded label, a missing tag, a dropped icon that labelled a column, a dropped callout or audience question the slide asks | Invented numbers, labels or categories; claims the source does not make; a meaningful figure or illustration dropped | accuracy.md 0 to 3, 7 |
| 10 | **Host fit** | Does the whole slide look designed, with the figure in place of the old content? | Title, figure, margins and footer form one composition in the deck's look; the figure replaced the cards or text block; the context slide looks designed too | The figure fits but the slide around it is plain (oversized title, default font, lost brand elements) | A dumped host (full-width wrapping title, raw bullet list, row of thumbnails) or the old boxes still there under the figure: the slide looks no different from the source | SKILL.md "Deck first", "Make a visible change"; style.md "Under a host theme" |

**Verdict** (per slide and for the deck; the deck takes the worst slide):
- **ship**: every item 3 or above.
- **fix**: any item at 2, or a single 1 on Space, Boxes, Colour, Type, Lines or Rest frame.
  Patch the named defects and review again.
- **rebuild**: a 1 on Form, Restraint, Fidelity or Host fit, or three or more items below 3.
  The figure (or, for Host fit, the deck around it) is redone from the spec, not patched.
- The verdict is computed from the scores, never set by feel; the reviewer's doubt goes into a
  lower score (it is told to take the lower of two scores). A context-after image is scored on
  Host fit only and counts as a slide for the deck verdict.

## 3. The reviewer prompt

Paste verbatim; then list the images, one line each, as `<label>: <absolute path>`. Nothing
else goes into the call.

```text
You are a blunt visual reviewer of animated presentation slides. You know nothing about how
they were made and you see only the images listed below. For each slide you get the source
slide ("before"), the rebuilt slide at rest ("after"), and sometimes frames from its animation
("mark-<seconds>"). A "context-after" image, when present, is a slide of the same rebuilt deck
that was not animated; use it only for item 10. Open every image before scoring.

The goal of the rebuild: replace the slide's text blocks, cards or screenshots with a quiet
drawing of the slide's own figure, plus one calm movement that plays once. The target look:
lots of empty space; no boxes, cards, chips or pills; rings, dots, thin lines and labels on
lines; one accent colour lighting what matters with at most one soft glow; at most two extra
colours that carry a meaning stated on the slide; large readable labels with smaller muted
sub-labels; the deck's own colours and fonts. "Too much" is a defect even when everything is
correct: a second storyline, invented arrows or brackets, a different chart form, several
glows, repeated pulses or packets.

Score every slide on these ten items, 1 to 5 (5 = no fault, 3 = visible flaw that a careful
presenter would fix, 1 = a viewer would call the slide ugly, wrong or unchanged):
1 Form: the after figure has the before figure's own shape (stairs stay stairs, rows stay
  rows, columns stay columns). 1 = a different form (e.g. steps re-plotted as a line chart)
  or the figure dropped for text.
2 Restraint: one movement, at most one glowing element, nothing repeated across the frames.
  1 = repeated packets/pulses, several glows, everything lit. Judge from the mark frames;
  without them judge glow count on the rest frame and write "rest only".
3 Space: figure fills about 60-70 % of its area, centred, room around labels. 1 = crammed or
  a mostly empty slot.
4 Boxes: no filled panels, cards, chips, pills, caption bars, unless the box is the meaning
  (a table, a container). 1 = the source's cards redrawn or left in place.
5 Colour: one accent plus at most two meaning colours, in the deck's palette. 1 = many hues
  used as decoration or clashing with the deck.
6 Type: every word readable at a glance from the back of a room, clear hierarchy, nothing
  clipped, overlapping or crossing a line. 1 = too small, clipped or overlapping.
7 Lines: thin quiet strokes, visible on their ground, no glowing lines. 1 = glowing or heavy
  lines everywhere, or lines too faint to see on a light ground.
8 Rest frame: the after image alone tells the finished story: all steps and values present
  and the end state visibly reached. 1 = blank or half drawn. If the source showed progress,
  order shading, values or a highlighted outcome and the after shows a row of identical
  neutral markers (empty rings, grey dots) instead, score 2 at most, even when one end marker
  is lit.
9 Fidelity: every label and number in the after image appears on the before slide (shortened
  is fine, reworded or invented is not); example values are tagged "illustrative"; icons or
  pictures that labelled items on the before slide are kept or redrawn; a callout or question
  the slide asks its audience is content too (dropped = 3 at most). 1 = invented content or
  meaningful pictures dropped.
10 Host fit: the whole after slide looks designed: title, figure, margins and footer form one
  composition in the deck's look; the figure replaced the old cards or text. 1 = a dumped
  page (huge wrapping title, raw bullet list, row of image thumbnails, default styling) or the
  old boxes still there so the slide looks no different from the before. Score a
  context-after image as its own section with Host fit only (other items "n/a"); do not
  fold it into the animated slides' scores.

Verdict per slide, computed from the scores and nothing else: "ship" if every item is 3 or
above; "rebuild" if Form, Restraint, Fidelity or Host fit is 1, or three or more items are
below 3; otherwise "fix". The deck verdict is the worst slide verdict. Be blunt in the
scores, not in the verdict: do not reward effort, or correctness, with a higher look score.
When unsure between two scores, give the lower one.

Output exactly this, nothing before it:

## Slide <label>
| Item | Score | Reason (one line, name what you see and where) |
|---|---|---|
| Form | n | ... |
... (all ten items)
Verdict: ship | fix | rebuild

(repeat per slide)

## Worst defects
1. <slide>: <defect>, <where on the slide>. Fix: <one concrete action>.
2. ...
3. ...

## Deck verdict: ship | fix | rebuild
```

## 4. Calibration

Run on 2026-11-08 with fresh reviewers (Opus, general-purpose, the prompt plus labelled
paths only; A and B with mark frames, C to E with the rest frame only, A and B with one
un-animated context slide). Scores are in item order: Form, Restraint, Space, Boxes, Colour, Type, Lines,
Rest frame, Fidelity, Host fit.

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
| D, round 1 | Public civics deck, rest frames of two process snakes | s23 | 5 4 4 5 4 4 4 4 **2** 4 | fix |
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
- **Rest frame 2**: D's snakes, rows of identical empty rings or grey dots with one lit end
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
