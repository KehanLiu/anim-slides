# Look rubric: review by a fresh pair of eyes

The checkers (`check_fragment.py`, `verify_facts.py`, `check_page.py`) prove the contract and
the facts. They cannot see that a slide is ugly or "too much". This rubric is the judgement
layer: a reviewer that knows nothing about the build looks only at rendered stills and the
slide's claim, and scores them. The skill runs it on its own work before saying "done", and the eval runner uses it to
score a corpus. It enforces `style.md` and `accuracy.md` rule 0 by eye.

## 1. How to run a review

**Images, per animated slide** (name them by slide; the reviewer sees nothing else):
- `sN-before.png`: the source slide (`anim/render/full/p-NN.png`).
- `sN-first.png`: the first frame of the pass (`render-phases.sh --page deck.html --slide N <W> <H> 0.3`).
- `sN-mark-<t>.png`: every phase-mark frame (`render-phases.sh --page ... <marks...> rest`).
- `sN-pause-<t>.png`: three paused frames between the marks. `check_look.py <fragment>
  --rendered-width W --at-pauses` picks three reproducible times between 0.5 s and the last
  mark, prints them and checks them (finding `pause`, WARN); render the same times with
  `render-phases.sh` for the reviewer.
- `sN-after.png`: the integrated slide at rest (`... rest`).
- Once per deck, `context-after.png`: one slide of the integrated deck that was **not**
  animated (a text slide next to an animated one). A host that is a Markdown dump shows there
  first.

**Text, per animated slide**: `sN-claim`, the slide's claim in one sentence (the triage row's
Idea, or the headline when the slide states only order). Nothing else: no brief, spec, beat
table, verb name or note on what changed.

**Who runs it.**
- The main thread, in Phase 2 step 8 of SKILL.md, after `check_page.py`: one reviewer for all
  animated slides of the deck, batched in one call.
- The eval runner, once per case, with the same prompt.

**Polish loop, before the review.** After the first render the builder looks at the stills
and writes down the three worst problems, ranked, and no more. It fixes only those and
renders again. It also answers: "what one thing could be removed so the figure gets better?",
and removes it when the answer is not "nothing". One round is required; a second when the
first changed the composition. The fresh review comes after.

**The protocol.**
1. Start a fresh reviewer that has not seen the build conversation: a subagent with no prior
   context where the harness has one (Claude Code: the Agent tool, general-purpose); otherwise
   a fresh pass that reads only the prompt in section 3, the stills and the claims. Give it
   **only** those, with their labels. No hint at what was changed or what you worry about: a
   reviewer told the hypothesis confirms it.
2. It returns scores per slide, a verdict `ship` or `fix`, and each finding with the frame it
   is on (`s4-mark-3.2`, `s4-pause-2.7`, `s4-after`). A `fix` names at most three problems,
   ranked, worst first.
3. A `fix` blocks "done". When Form, Restraint, Fidelity or Host fit is 1, or three or more
   items are below 3, the figure (or the deck around it) is rebuilt from the spec, not
   patched. Otherwise the builder fixes the named findings. Then re-render and run a **new**
   fresh reviewer (not the same one: it has seen the old images).
4. At most two rounds. Findings left after round two are listed in the hand-over message and
   in the Decisions section of `anim/triage.md`, one line each, with slide and frame. A figure
   still being rebuilt after the second round has the wrong picture idea: go back to the
   brief (picture idea, form, setup and payoff) instead of polishing further.
5. A finding is not softened, argued down or dropped because the build took effort. The
   builder either fixes it or, for a fact the reviewer cannot see, answers it in the triage.

A reviewer can be wrong about facts it cannot see (it has the source slide, not the notes).
A Fidelity complaint about a label that the notes or a figure transcription support is
answered in the triage, not "fixed".

## 2. The rubric

Score each item 1 to 5 per slide; 4 and 2 sit between the anchors. Judge the **after** image
against the **before** image; Restraint and Entrance from the first, mark and pause frames.

| # | Item | Question | 5 | 3 | 1 | Enforces |
|---|---|---|---|---|---|---|
| 1 | **Form** | Is the figure the slide's own figure in its own shape? | Same form as the source (stairs stay stairs, table stays rows, cycle stays a ring, two columns stay two columns), redrawn quietly | Form recognisable but bent: an extra axis, brackets or arrows the source lacks, a sequence turned into a chart | A different figure: stairs re-plotted as a line chart, rows turned into a flow, a new storyline; or the source figure dropped for text | style.md 0; accuracy.md 0 |
| 2 | **Restraint** | One movement, accent only in the light, at most one glow? Does every pause frame look intentional on its own? (first, mark and pause frames) | One thing moves per phase; the accent sits only on what is active or already reached, at most one glow per frame, none on a line; nothing repeats across marks; each pause frame reads as a still: nothing half-overlapping, no label without its thing, at most three things in motion | Two things compete in one frame, a second glow, the accent on parts not yet reached, a decorative extra (arrow, star, halo), or a pause frame with a half-overlap or an orphan label | Packets or pulses repeated across marks, several glows at once, everything lit, motion layered over a busy figure | style.md 0, 3, 8, 9 |
| 3 | **Composition** | Is the space used on purpose? | Figure spans at least 60 % of the slot's width or height, no dead band above or below; text and shape edges share two or three anchor lines (or the headline's left edge); gaps inside a group at most half the gap between groups; the focal step gets more room | A centred, evenly spaced row by habit where the claim has a lead element, a large empty band, or a label near an edge | Crammed (labels touch, figure runs into the title or footer), or a thin strip in a mostly empty slot | style.md 1; layouts.md |
| 4 | **Boxes** | Are there boxes where the meaning has none? | No filled panels, cards, chips, pills or caption bars; rings, dots, labels on lines, hairline brackets; rectangles only for real containers (table, chamber, database) | One or two framed or tinted elements that carry no meaning | The source's cards or pills redrawn (filled, coloured, rounded) or left in place with motion on top | style.md 2; SKILL.md "Make a visible change" |
| 5 | **Colour** | Ground, ink, one accent, at most two meaning colours? | One accent on what is active and reached, about a tenth of the drawn area at rest; at most two semantic colours, each with a meaning the slide states; palette belongs to the deck | A third hue, a semantic colour with no stated meaning, or the accent spread over many elements | A rainbow: several accents, colour as decoration, palette clashing with the deck's own colours | style.md 3; "Under a host theme" |
| 6 | **Type** | Readable at a glance, on a clear type ladder? | Every word readable; at most one hero size (the claim's number or word), labels, muted sub-labels, each size at least 1.25x the next; sentence case; mono only on numbers, units, codes; the deck's font | Two sizes too close to tell apart, a crowded label, tracked capitals, mono on a name or term | Text too small to read on a projector, clipped or overlapping words, labels on top of lines or each other | style.md 5, 6, 12; contract text floor |
| 7 | **Lines** | Are strokes quiet and visible? | Even structure strokes visible on their ground, a heavier accent only on the active path, small open arrowheads | Strokes a little heavy or a little faint, arrowheads large | A glowing line, thick strokes everywhere, or lines so faint on a white ground they vanish | style.md 4, 8; "Under a host theme" fade levels |
| 8 | **Rest frame** | Does the resting image tell the finished story on its own? | The complete figure: every step, value and label present, the end state visibly reached (final step marked, all data drawn), looks intended | Complete but flat: nothing shows where the story ended, or one element looks mid-fade | Empty or half drawn: blank slot, only the start of the story; would print as an unfinished figure. A row of identical neutral markers (empty rings, grey dots) where the source showed progress, order shading, values or a highlighted outcome scores 2 at best | contract resting frame; style.md 9 |
| 9 | **Fidelity** | Are labels, numbers and the figure the source's own? | Every label and number visible on the before slide (shortened, not paraphrased); illustrative or traced tag where values are examples; the source's meaning-carrying icons kept or redrawn | One reworded label, a missing tag, a dropped icon that labelled a column, a dropped callout or audience question the slide asks | Invented numbers, labels or categories; claims the source does not make; a meaningful figure or illustration dropped | accuracy.md 0 to 3, 7 |
| 10 | **Host fit** | Does the whole slide look designed, with the figure in place of the old content? | Title, figure, margins and footer form one composition in the deck's look; the figure replaced the cards or text block; the context slide looks designed too | The figure fits but the slide around it is plain (oversized title, default font, lost brand elements) | A dumped host (full-width wrapping title, raw bullet list, row of thumbnails) or the old boxes still there under the figure: the slide looks no different from the source | SKILL.md "Deck first", "Make a visible change"; style.md "Under a host theme" |
| 11 | **Idea** | Labels covered: with all text hidden, does the picture still show the claim? Specificity: could a deck on another subject use it unchanged? | With the text hidden the form carries the claim (counts shrink, the path closes, the beam tips); or the claim is order only and the picture is a clean row | A correct row or list where the claim also states a quantity, a return, a tension or a containment that the picture ignores | Generic nodes: a deck on another subject could use the figure unchanged | archetypes.md picture idea; accuracy.md 0 |
| 12 | **Focal** | Squint: with the frame blurred, is one element seen first, then the groups in order? | One focal element, about 1.5x its peers or the only hero text, is the first thing seen; the eye then moves through the groups in the claim's order | Two elements of equal weight compete, or the focal element is right but the rest has no order | No focal element: every part the same weight, or the eye lands on decoration | style.md 11 |
| 13 | **Entrance and payoff** | Do the frames differ by more than opacity? Comparing the first frame with the resting frame, what was paid off? | The first frame leaves a gap (an empty jar, a level short of its line, groups apart) and the resting frame closes it; each kind enters its own way: lines drawn on, nodes landing where their line arrives, numbers counting or bars growing, areas revealed in the direction of meaning, labels after the thing they name | Most parts only fade in, with one real entrance; or the payoff is there but small, beside a first frame that already shows most of the answer | A moving poster: everything stands in its final place from the first frame and only fades in, so nothing is paid off | motion-rules.md "A once pass", "Entrance by kind" |

Idea is judged against the claim and the before slide's words, not against variety. A row is
a 5 when order is all the source states; decoration does not raise the score, and a form the
words do not support is a Form or Fidelity fault. For any Idea score under 4 the reviewer
quotes the before words that state the quantity, return or relation. Anchors, from the
`prose-not-a-row` eval: four falling counts (1,240 to 351) drawn as four equal rings is a 3;
drawn as marks that shrink with the counts, a 5; a petition's four steps as a clean row, a 5.
A before slide of text or step cards has no figure of its own: a row of cards is layout, so
Form there asks only that the drawn form follows the words.

**Verdict** (per slide and for the deck; the deck takes the worst slide):
- **ship**: every item 3 or above.
- **fix**: any item below 3. When Form, Restraint, Fidelity or Host fit is 1, or three or more
  items are below 3, the fix is a rebuild from the spec (section 1, step 3).
- The verdict is computed from the scores, never set by feel; the reviewer's doubt goes into a
  lower score (it is told to take the lower of two scores). A context-after image is scored on
  Host fit only and counts as a slide for the deck verdict.
- **Forms**: beside the deck verdict the reviewer lists the form of each animated slide (row,
  ring, funnel, two sides, fill level, scene, table...). When the same form sits on two
  consecutive animated slides or on more than half of them, it asks the builder "does slide N
  say more than order?" for each. This is a question, not a fail: the builder answers it in
  the triage from the slide's words (the Idea column), and redraws only where the words state
  more.

## 3. The reviewer prompt

Paste verbatim; then list the images, one line each, as `<label>: <absolute path>`, and the
claims as `sN-claim: <sentence>`. Nothing else goes into the call.

```text
You are a blunt visual reviewer of animated presentation slides. You know nothing about how
they were made and you see only the images listed below. For each slide you get the source
slide ("before"), the first frame of its animation ("first"), frames at its phase marks
("mark-<seconds>"), three frames paused at random moments between the marks
("pause-<seconds>"), the rebuilt slide at rest ("after"), and one sentence with the slide's
claim. A "context-after" image, when present, is a slide of the same rebuilt deck that was
not animated; use it only for item 10. Open every image before scoring.

The goal of the rebuild: replace the slide's text blocks, cards or screenshots with a quiet
drawing of the slide's own figure, plus one calm movement that plays once. The target look:
lots of empty space; no boxes, cards, chips or pills; rings, dots, thin lines and labels on
lines; one focal element the eye lands on first; one accent colour only on what is active or
already reached, with at most one soft glow; at most two extra colours that carry a meaning
stated on the slide; a clear type ladder (at most one large hero number or word, labels,
smaller muted sub-labels) in the deck's own colours and fonts, with monospace only for
numbers, units and codes. "Too much" is a defect even when everything is correct, when it
adds what the before slide does not state: a second storyline, invented nodes, labels,
arrows or brackets, a different chart form, several glows, repeated pulses or packets. A
form the before slide's own words support is not an addition: a ring where the words say the
last step repeats or returns, a boundary line where they state a handover, shrinking marks
where they give falling counts.

Score every slide on these thirteen items, 1 to 5 (5 = no fault, 3 = visible flaw that a
careful presenter would fix, 1 = a viewer would call the slide ugly, wrong or unchanged):
1 Form: the after figure has the before figure's own shape (stairs stay stairs, rows stay
  rows, columns stay columns). 1 = a different form (e.g. steps re-plotted as a line chart)
  or the figure dropped for text. When the before slide is only text or a row of step cards,
  the cards are layout, not a figure: a ring, funnel or two sides drawn from its words is not
  a Form fault.
2 Restraint: one movement per frame; the accent only on what is active or already reached;
  at most one glowing element, never a glowing line; nothing repeated across the frames.
  Each pause frame must look intentional on its own: nothing half-overlapping, no label
  without the thing it names, at most three things caught in motion (one fault there = 3 at
  most). 1 = repeated packets/pulses, several glows, everything lit.
3 Composition: the figure spans at least 60 % of its area's width or height with no dead band
  above or below; edges line up on a few anchor lines; groups read as groups; not a centred,
  evenly spaced row when one step matters more. 1 = crammed, or a thin strip in an empty slot.
4 Boxes: no filled panels, cards, chips, pills, caption bars, unless the box is the meaning
  (a table, a container). 1 = the source's cards redrawn or left in place.
5 Colour: one accent (a small share of the figure at rest) plus at most two meaning colours,
  in the deck's palette. 1 = many hues used as decoration or clashing with the deck.
6 Type: every word readable at a glance from the back of a room; sizes clearly different
  (hero, label, sub-label); sentence case; monospace only for numbers, units and codes (a
  name or term in monospace is a fault); nothing clipped, overlapping or crossing a line.
  1 = too small, clipped or overlapping.
7 Lines: quiet strokes, visible on their ground, the active path heavier, no glowing lines.
  1 = glowing or heavy lines everywhere, or lines too faint to see on a light ground.
8 Rest frame: the after image alone tells the finished story: all steps and values present
  and the end state visibly reached. 1 = blank or half drawn. If the source showed progress,
  order shading, values or a highlighted outcome and the after shows a row of identical
  neutral markers (empty rings, grey dots) instead, score 2 at most, even when one end marker
  is lit.
9 Fidelity: every label and number in the after image appears on the before slide (shortened
  is fine, reworded or invented is not); example values are tagged "illustrative"; icons or
  pictures that labelled items on the before slide are kept or redrawn; a callout or question
  the slide asks its audience is content too (dropped = 3 at most). For any Fidelity score
  under 4, quote the words you read on the before slide next to the words on the after slide,
  so the builder can verify the complaint. 1 = invented content or
  meaningful pictures dropped.
10 Host fit: the whole after slide looks designed: title, figure, margins and footer form one
  composition in the deck's look; the figure replaced the old cards or text. 1 = a dumped
  page (huge wrapping title, raw bullet list, row of image thumbnails, default styling) or the
  old boxes still there so the slide looks no different from the before. Score a
  context-after image as its own section with Host fit only (other items "n/a"); do not
  fold it into the animated slides' scores.
11 Idea: cover every word in the after image; does the picture alone still show the claim
  (falling counts drawn shrinking, a stated return drawn closed, a stated trade-off drawn as
  two sides)? And could a deck on another subject use this figure unchanged? 5 = the form
  carries the claim, or the claim is order only and the picture is a clean row (a plain row
  is not a fault then; decoration does not earn points). 3 = a correct row or list that
  ignores a quantity, return, tension or containment the words state. 1 = generic nodes
  another deck could use unchanged. For any Idea score under 4, quote the before words that
  state what the picture ignores.
12 Focal: squint (blur the after image); one element is seen first, about 1.5x its peers or
  the only large text, then the groups in the claim's order. 1 = everything the same weight,
  or the eye lands on decoration.
13 Entrance and payoff: compare the first and mark frames. Lines should be drawn on, nodes
  land where their line arrives, numbers count or bars grow, areas are revealed in a
  direction, labels follow what they name. Then compare the first frame with the after image
  and name, in the Reason, what was paid off: the gap the first frame left open (an empty
  container, a level short of its line, groups apart) and how the end closes it. 1 = a moving
  poster: every part already in its final place in the first frame, only fading in.

Verdict per slide, computed from the scores and nothing else: "ship" if every item is 3 or
above, otherwise "fix". The deck verdict is the worst slide verdict. Be blunt in the scores,
not in the verdict: do not reward effort, or correctness, with a higher look score. When
unsure between two scores, give the lower one. An unfamiliar form is not a reason for doubt;
a form, node or label the before slide's words do not support is. Name the frame each
finding is on.

Output exactly this, nothing before it:

## Slide <label>
| Item | Score | Frame | Reason (one line, name what you see and where) |
|---|---|---|---|
| Form | n | after | ... |
... (all thirteen items)
Verdict: ship | fix

(repeat per slide)

## Forms
<slide>: <form in two or three words>, one line per animated slide. If the same form is on
two consecutive animated slides or on more than half of them, add per such slide:
"Question: does slide <N> say more than order? <before words that might say more, or none>"

## Worst defects
At most three, ranked, worst first.
1. <slide>, <frame>: <defect>, <where on the slide>. Fix: <one concrete action>.
2. ...
3. ...

## Deck verdict: ship | fix
```

## 4. Calibration

Run on 2026-11-08 with fresh reviewers (Opus, general-purpose, the prompt plus labelled
paths only; A and B with mark frames, C to E with the rest frame only, A and B with one
un-animated context slide). Scores are in item order: Form, Restraint, Space, Boxes, Colour, Type, Lines,
Rest frame, Fidelity, Host fit. Idea and the Forms list were added on 2026-11-13, after
these runs; Idea's anchors come from the `prose-not-a-row` eval, not from a reviewer run.
Focal, Entrance and payoff, the first and pause frames, the claim line, the `ship`/`fix` verdict and the
Composition wording of item 3 (formerly Space: "centred, even margins") were added in look
v2 and are not yet calibrated. The old `rebuild` verdict below is now a `fix` that rebuilds.

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
