# Motion rules

A motion identity for slide illustrations and the audit an agent runs before shipping a
fragment. Hard limits (text size, pass length, motion and glow concurrency,
reduced-motion rule) are in [fragment-contract.md](fragment-contract.md) section 6; this file
explains how to meet them.

Personality: calm and precise. No bounce, no elastic; the only overshoot is the `land` curve's
about 3 % on a small mark (Easing). The viewer is listening to a
speaker; motion points at things, it does not perform. **It plays once:** when the slide becomes
current the story runs one pass and then rests on its finished state (control `once`, the
default). Repeating the same animation on one slide is noise, so nothing pulses, marches or
restarts while the slide is up. Under `step` (the deck's choice at intake) it is the same pass,
played in segments: the entrance draws on with the slide and each click lands the next phase.
A continuous `loop` is only for a kiosk, a gallery or a hero when the user asks for one.

## Durations

| Class | Duration | Use |
|---|---|---|
| micro | 150-250 ms | colour change, highlight on/off, a tick landing |
| element | 250-500 ms | a node landing (250-400 ms), a label entering, a short move, a cross-fade |
| scene | 600-900 ms | a group rearranging, a long move across the slot, a large draw-on (Techniques, Draw-on) |
| change | 0.9-1.8 s | the verb's own move: a level rising, units regrouping, a morph, a wipe, a zoom, a beam tilting |
| hop | 600-1200 ms | one traveller along one leg of its route (`travel` only) |
| hold | 0.8-1.5 s | end of the pass; the held state is the resting frame and stays (loop: 1-2 s before the reset) |

Anything slower than 900 ms that is not a change, a hop or a draw-on reads as lag. A change is
slow on purpose: it is the claim, and the audience has to see it happen.

## A once pass

One pass of 4 to 10 s (`data-anim-cycle`), shaped as one staggered reveal:

| Part | When | What |
|---|---|---|
| enter | 0 to ~1 s | the static frame and the first elements enter by kind (below), stagger 40 to 120 ms and not all equal, at most 600 ms per group |
| action | ~1 s to pass - hold | one phase per narrated step, about 1 to 2 s each, each a staged step of the fragment's verb (a level rising, units regrouping, the highlight moving on, ...); captions cross-fade per phase |
| stillness | 400 to 600 ms before the answer step | nothing moves, so the answer (the verb's last staged step) is seen to arrive |
| hold | last 0.8-1.5 s | nothing moves; the finished state (= 100 % keyframe = resting frame) is shown and stays, with the last caption |

**Setup, then payoff.** The first frame leaves a visible gap or question, and the pass closes
it: an empty jar that fills, a level short of its threshold line, two groups not yet joined, a
verdict line still blank. The resting frame is the payoff, and it differs from the first frame
in the place the claim is about. Not allowed: the "moving poster", where every part already
stands in its final place and only animates in. That pass has no story, however well each part
enters.

Phases keep their second marks from the spec; keyframe percentage = seconds / pass * 100.
The phase marks go on the wrapper as `data-anim-phases`: settled moments between narrated steps
(three to five per slide, six when the slide narrates six), ascending, the last at the hold start.
At most three things move at any moment, and no element moves twice unless the story needs it:
a packet that travels one path once is fine, a pulse that repeats is not. A highlight that moves
from step to step is one focus changing place, not repetition.

## What motion can mean

Every fragment has one **verb**: the motion that is the slide's claim. The twenty verbs, how
to pick one from the claim, what each puts on screen and how it is built are in
[motion-verbs.md](motion-verbs.md). The rules that hold for all of them:

- The verb's move is the hero of the pass: 40 to 60 % of the seconds, in two to four staged
  steps with a settled moment between them. Entrances are the set-up, not the story.
- A travelling marker belongs to the verb `travel` (a named thing changing place) and to the
  one trip of a `cycle`. A fragment whose verb is anything else has no packet, token or head
  dot riding its lines; the highlight moving on shows order.
- One kind of change per step: positions, then colours, then labels.
- What the hero touches follows 50 to 150 ms later; nothing else moves meanwhile.
- A slide explained by pointing at parts of one picture may stay still: `dim`, one `mark`
  per phase, no invented motion.
- Every move sits under the limits above: one calm pass, rest on the finished frame, no
  loops, at most three things moving at once, no overshoot beyond `land`, one glow.

## A step pass

`step` uses the `once` pass unchanged; the host stops it at the `data-anim-phases` marks
(contract section 7), so the fragment needs nothing extra. What makes segments work:

- **A phase is a narrated step:** one mark per thing the presenter says next, 3 to 5 per slide
  (six when the slide narrates six steps), the same phases as the brief and the spec. Do not add marks for motion that is not narrated.
- **Marks sit at settled moments:** at a mark nothing is mid-move, mid-fade or mid-hop, so the
  frame the presenter stops on reads as a still. End each phase's motion 0.1 to 0.2 s before
  the next mark.
- **Segment 1 is the entrance:** it plays when the slide appears, so it carries the static frame
  rising in plus the first phase; the presenter talks over it, then clicks.
- **The last mark is the hold start:** after it nothing moves, so the frame there equals the
  resting frame and a click past it goes to the next slide.

## Easing

These five are the only curves. Use the literal values; whitespace inside the brackets is
free.

| Name | Value | Use |
|---|---|---|
| enter | `cubic-bezier(0.16, 1, 0.3, 1)` | things arriving, draw-on, reveals |
| move | `cubic-bezier(0.2, 0, 0, 1)` | things on screen changing place or size; the verb's own move |
| exit | `cubic-bezier(0.3, 0, 1, 1)` | things leaving, about 65 % of the entrance time |
| land | `cubic-bezier(0.3, 1.3, 0.5, 1)` | a small mark arriving (dot, tick, ring marker, check; at most 48 px on its longer side); overshoots about 3 % |
| linear | `linear` | continuous motion only (see below); `steps()` for digit strips |

- `land` is only for small marks. Never on large shapes, groups, text or the verb's move.
- `ease`, `ease-in`, `ease-out`, `ease-in-out` and any other `cubic-bezier` are faults
  (checker `easing-set`, WARN). Any other curve with y1 or y2 outside 0 to 1 is a hard fault
  (`overshoot`, FAIL).
- Entrance/exit asymmetry: entrances decelerate, exits accelerate and take about 65 % of the
  entrance time (500 ms in, ~320 ms out).
- Emphasis (a pulse, a pop, an entrance) stays within +-5 % scale; prefer opacity or stroke
  colour for "attention". A size change that is the content (a level, a bar, a band) runs at
  its true proportion with the move curve.

## Entrance by kind

How a thing enters depends on what it is. A fade is not the default.

| What enters | How |
|---|---|
| line, wire, axis, outline, arc | draw-on (stroke-dashoffset), enter curve |
| node, marker, dot on a line | lands at the moment its line reaches it: scale 0.92 to 1 plus fade, 250 to 400 ms; land curve when small, enter curve otherwise |
| number | rolls or counts to its value (digit strip), or its bar or level grows and the number lands with it |
| area, band, fill, illustration, drawn object | mask or clip-path reveal in the direction of meaning (a level from below, a timeline from the left) |
| label | fade with an 8 to 12 px rise, 50 to 150 ms after the thing it names |
| caption | cross-fade |

Order inside a group: line first, the node lands, the label settles last, each smaller in
amplitude than the one before. A fragment where nearly every shape only fades in is a fault
(checker `fade-after-fade`, WARN).

## Choreography

- **Stagger:** 40 to 120 ms between items, and not all equal: later items closer together, or
  the led element first and what it pulls after. A group's total stagger is at most 600 ms.
  With more than six items, stagger rows, not items.
- **Stillness before the answer:** one deliberate pause of 400 to 600 ms where nothing moves,
  just before the answer step (the verb's last staged step), so the answer is seen to arrive
  (`check_fragment.py` accepts 380 ms or more).
  The end hold stays as well. Make room for it by ending the earlier motion sooner inside its
  phase, or by moving a phase mark or lengthening the pass (still 4 to 10 s). A figure whose
  verb is a continuous trace (a strip chart that never stops) is exempt. `check_fragment.py`
  reports a missing stillness as `stillness` (WARN).
- **Follow-through:** a part's label lands 50-150 ms after the part itself.
- **One focus at a time:** the highlighted element changes, the rest dims to `--anim-muted` or
  reduced opacity. At most three things moving at once.
- **Pass structure (once):** setup (elements enter) -> action (the story happens) -> stillness
  (400 to 600 ms) -> resolution (the outcome is shown) -> hold (0.8-1.5 s on the final state, which stays). The resting frame
  equals the end of resolution and the 100 % keyframe of every track. `loop` adds a quick reset
  after a 1-2 s hold.
- **Linear only for continuous motion:** a scrolling trace in a strip chart, a draw-on that
  tracks time. Never for a move with a start and an end. Marching dashes and spinners repeat, so
  they belong to `loop` only.

## Techniques

- **A traveller on its route** (`travel`): `offset-path: path('M ...')` plus animated
  `offset-distance` from 0 % to 100 %. The path string reuses the route's `d`. CSS-only,
  smooth, no JS.
- **Levels, bars, zoom:** `scaleX`/`scaleY`/`scale` on the shape or group with
  `transform-box: view-box` and a px `transform-origin` at the baseline or focus; a dashed
  ghost keeps the start. Move curve.
- **Units:** one element per unit, each with its own `translate` or opacity track; a row or
  a group moves as a staggered series and counts as one move.
- **Wipe, cutaway, area reveal:** `clip-path: inset(...)` animated on a `<g>`, opening in the
  direction of meaning.
- **A mark landing:** a dot, tick or ring marker (at most 48 px) scales 0.92 to 1 plus fade in
  250 to 400 ms with the land curve, timed to the moment its line reaches it.
- **Counting:** a digit strip (a column of `<text>` under a `<clipPath>`, moved by
  `translateY` in `steps()`) or stacked `<text>` cross-faded. Do not animate text content;
  CSS counters do not render in SVG text.
- **Morph:** stack both shapes and cross-fade them as the base; inside
  `@supports (d: path("M0 0"))` animate `d` between two paths with the same commands and
  keep the second shape hidden (Safari does not animate `d` and shows the cross-fade). The
  resting rule sets the final `d`, so the still matches the last frame.
- **Draw-on:** give the path `pathLength="100"`, set `stroke-dasharray: 100 120`, animate
  `stroke-dashoffset` from 101 to 0 with the enter curve: 500-800 ms per path, up to 900 ms
  for a large path across the slot (scene class). (A plain `100` dash at offset 100 still
  paints a dot at the start with `stroke-linecap: round`.) Same maths for every path regardless of
  length. Resting frame: `stroke-dashoffset: 0`.
- **Changing text:** stack one `<text>` per state at the same position and cross-fade their
  opacity (element duration). Do not animate text content.
- **Reveals inside a box:** animate a cover rect or a clip rect's `width`, not a `transform` on a
  `<clipPath>` child (see [lessons.md](lessons.md)).
- **Full-pass tracks:** give every animated element one keyframe track that spans the whole
  pass (`animation: <name>-x 8s linear 1 both`; `loop`: `12s linear infinite`) with the timing
  expressed as keyframe percentages, and end each track at 100 % on its resting value. Avoid
  `animation-delay` inside the fragment; render-phases.sh sets its own delays to freeze a frame.
- Percent of pass = seconds / pass * 100. Write the second mark in a comment next to each
  keyframe stop.

## Concurrency

The eye sees moving parts, not tracks. One track per element is the normal shape; what makes a
slide "too much" is many things changing in the same instant. The checker samples the pass
every 20 ms:

- **Motion:** an element moves while it is between two keyframe stops that differ. A staggered
  reveal counts as one: every element that is only appearing (opacity up from 0, maybe with a
  settling rise) counts once together. Every other move is an action and counts on its own;
  opacity-only swaps inside one group (a node's stacked status copies) count once, and a track
  on a `<g>` counts once. More than 3 at once warns, more than 6 fails ("N things move at once
  at t=X s; at most three, or a staggered series"). Typical culprits: a phase change that swaps
  the highlight, the caption, a status label, a wire draw-on and a packet at the same instant,
  or a second packet. Fix by staggering (40-120 ms), moving one of the
  changes 0.3-0.5 s later, or leaving secondary elements static (they are already right in the
  resting frame).
  A series of units that move while visible (the `sort` and `accumulate` verbs) counts as
  one move only when it is declared and really is one: put `data-anim-series="<id>"` on each
  unit or on their parent `<g>`. The checker counts the members moving at one instant as one
  move when the series has at most 100 animated members, every member animates the same set
  of properties, consecutive start times are at most 120 ms apart, and each staged step
  (members whose moves overlap) is over within 1.6 s. Otherwise it warns, names the series
  and the rule broken, and counts the members separately.
- **Variants:** rules inside `@supports (d: path("M0 0"))` are checked as their own variant
  next to the base (messages carry the condition as a prefix): the morph counts in that
  variant's concurrency, and a `d` track whose 100 % keyframe differs from the resting `d`
  fails.
- **Glow:** count the glow elements (blur/drop-shadow filter or a `glow` class) whose opacity,
  including their ancestors', is above 0 at the same instant. More than 1 warns, more than 2
  fails ("N glows visible at once at t=X s; one glowing element at most"). Keep the glow on the
  one active or outcome element and fade the previous glow out as the next comes in. Arrows,
  wires, lines, brackets and chart series never glow; a stroke-only glow element warns.

## Reduced motion and presenter control

- The contract's `prefers-reduced-motion` rule shows the resting frame; check that the still
  tells the story without motion.
- A once pass needs no pause key: it ends on its own and rests. A presenter who goes back to the
  slide sees it once more (the gate is removed and re-added).
- A step pass waits at each mark for the presenter's click; going back to the slide keeps the
  phase reached. Under reduced motion the host shows the resting frame and every key goes to
  the deck.
- `loop` longer than 5 s: the host deck should offer a pause key; if it cannot, use `once`
  (contract section 7).

## Audit checklist

Run before shipping each fragment. Every "no" is a fix.

1. Does it play once (no `infinite`, iteration count 1, fill `forwards`/`both`) in a 4-10 s pass
   with setup, action, resolution and a 0.8-1.5 s hold, and end exactly on the resting frame
   (render a time past the pass and `rest`: identical)? Are there no repeated pulses, marching
   dashes or second runs of the same move? (`loop` only when asked: 8-15 s, 1-2 s hold.)
2. Are at most three things moving at any second, and, mid-pass, about a third of the elements
   active (highlighted; not the accent share at rest)?
3. Is every curve one of the five literal values (enter, move, exit, land, linear, plus
   `steps()` for digit strips), with entrances on enter, exits on exit at ~65 % of the
   entrance time, on-screen moves and the verb's move on move, and `land` only on marks of at
   most 48 px? (`easing-set`; a curve with y1 or y2 outside 0 to 1 other than land:
   `overshoot`.)
4. Is `linear` used only for continuous motion?
5. Are all durations in the table's classes (micro, element, scene, change, hop)?
6. Does each thing enter by its kind (lines draw on, nodes land when their line reaches them,
   numbers count or land with their bar, areas reveal in the direction of meaning, labels
   settle last), rather than fade after fade? (`fade-after-fade`)
7. Is the stagger 40 to 120 ms and not all equal, each group's total at most 600 ms, and does
   a label follow its part by 50-150 ms?
8. Is there one stillness of 400 to 600 ms just before the answer step (`stillness`; a
   continuous trace exempt)? Does the first frame leave a gap that the resting frame closes,
   rather than every part already in its final place?
9. Does the wrapper name its verb (`data-anim-verb`), does that move take 40 to 60 % of the
   pass, and is there a traveller only under `travel` or `cycle`, named, on `offset-path`
   at 0.6-1.2 s per hop?
10. Do draw-on paths use `pathLength`, the enter curve and the draw-on duration (Techniques)?
11. Is changing text done by cross-fading stacked `<text>` elements?
12. Does nothing overshoot except a small mark on `land`, and does no emphasis pulse or pop
    exceed +-5 % (size that is the content excepted)?
13. Does every animated element have a full-pass track with no `animation-delay`, whose 100 %
    stop equals its resting value?
14. Is the resting frame the final state and readable as a still (also under reduced motion)?
15. Is all text at or above the contract minimum at rendered size, with no overlap at any
    rendered phase?
16. Concurrency: at most three things (or one staggered series) moving at any instant (the
    checker warns above 3 and fails above 6)? At most one glow visible at a time, and no glowing arrow, wire, line or series?
17. `step` only: does the wrapper carry `data-anim-phases` with one mark per narrated phase
    (3 to 5, six when the slide narrates six), each at a settled moment, the last at the hold start, and is the step-host
    snippet in the deck head? `loop` only: if longer than 5 s, does the host offer a pause key
    (or is `once` used)?
