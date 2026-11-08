# Motion rules

A motion identity for slide illustrations and the audit an agent runs before shipping a
fragment. Hard limits (text size, pass length, motion and glow concurrency,
reduced-motion rule) are in [fragment-contract.md](fragment-contract.md) section 6; this file
explains how to meet them.

Personality: calm and precise. No overshoot, no bounce, no elastic. The viewer is listening to a
speaker; motion points at things, it does not perform. **It plays once:** when the slide becomes
current the story runs one pass and then rests on its finished state (control `once`, the
default). Repeating the same animation on one slide is noise, so nothing pulses, marches or
restarts while the slide is up. Under `step` (the deck's choice at intake) it is the same pass,
played in segments: the entrance draws on with the slide and each click lands the next phase.
A continuous `loop` is only for a kiosk, a gallery or a hero when the user asks for one.

## Durations

| Class | Duration | Use |
|---|---|---|
| micro | 150-250 ms | chip pop, colour change, highlight on/off, tick |
| element | 300-500 ms | a box or label entering, a short move, a cross-fade |
| scene | 600-900 ms | a group rearranging, a long move across the slot, a large draw-on |
| hop | 600-1200 ms | one packet along one wire |
| hold | 0.8-1.5 s | end of the pass; the held state is the resting frame and stays (loop: 1-2 s before the reset) |

Anything slower than 900 ms that is not a hop or a draw-on reads as lag.

## A once pass

One pass of 4 to 10 s (`data-anim-cycle`), shaped as one staggered reveal:

| Part | When | What |
|---|---|---|
| enter | 0 to ~1 s | the static frame and the first elements rise in, stagger 60-120 ms, under 500 ms per group |
| action | ~1 s to pass - hold | one phase per narrated step, about 1 to 2 s each: an entrance, one highlight moving on, at most one packet hop along its path; captions cross-fade per phase |
| hold | last 0.8-1.5 s | nothing moves; the finished state (= 100 % keyframe = resting frame) is shown and stays, with the last caption |

Phases keep their second marks from the spec; keyframe percentage = seconds / pass * 100.
The phase marks go on the wrapper as `data-anim-phases`: settled moments between narrated steps
(three to five per slide, six when the slide narrates six), ascending, the last at the hold start.
At most three things move at any moment, and no element moves twice unless the story needs it:
a packet that travels one path once is fine, a pulse that repeats is not. A highlight that moves
from step to step is one focus changing place, not repetition.

## A step pass

`step` uses the `once` pass unchanged; the host stops it at the `data-anim-phases` marks
(contract section 7), so the fragment needs nothing extra. What makes segments work:

- **A phase is a narrated step:** one mark per thing the presenter says next, 3 to 5 per slide,
  the same phases as the brief and the spec. Do not add marks for motion that is not narrated.
- **Marks sit at settled moments:** at a mark nothing is mid-move, mid-fade or mid-hop, so the
  frame the presenter stops on reads as a still. End each phase's motion 0.1 to 0.2 s before
  the next mark.
- **Segment 1 is the entrance:** it plays when the slide appears, so it carries the static frame
  rising in plus the first phase; the presenter talks over it, then clicks.
- **The last mark is the hold start:** after it nothing moves, so the frame there equals the
  resting frame and a click past it goes to the next slide.

## Easing

| Name | Value | Use |
|---|---|---|
| enter | `cubic-bezier(0.16, 1, 0.3, 1)` (expo-out) | things arriving |
| move | `cubic-bezier(0.2, 0, 0, 1)` or `ease-in-out` | things already on screen moving |
| exit | `cubic-bezier(0.3, 0, 1, 1)` (accelerate) | things leaving |
| linear | `linear` | continuous motion only (see below) |

- Entrance/exit asymmetry: entrances decelerate, exits accelerate and take about 65 % of the
  entrance time (500 ms in, ~320 ms out).
- Pops scale 0.92 to 1 with the enter curve. Never overshoot past 1.
- Nothing pulses more than +-5 % scale; prefer opacity or stroke colour for "attention".

## Choreography

- **Stagger budget:** total stagger of a group under 500 ms; 60-120 ms between items. With more
  than six items, stagger rows, not items.
- **Follow-through:** a card's content lands 50-150 ms after the card itself.
- **One focus at a time:** the highlighted element changes, the rest dims to `--anim-muted` or
  reduced opacity. At most three things moving at once.
- **Pass structure (once):** setup (elements enter) -> action (the story happens) -> resolution
  (the outcome is shown) -> hold (0.8-1.5 s on the final state, which stays). The resting frame
  equals the end of resolution and the 100 % keyframe of every track. `loop` adds a quick reset
  after a 1-2 s hold.
- **Linear only for continuous motion:** a scrolling trace in a strip chart, a draw-on that
  tracks time. Never for a move with a start and an end. Marching dashes and spinners repeat, so
  they belong to `loop` only.

## Techniques

- **Packets along wires:** `offset-path: path('M ...')` plus animated `offset-distance` from 0 %
  to 100 %. The path string reuses the wire's `d`. CSS-only, smooth, no JS.
- **Draw-on:** give the path `pathLength="100"`, set `stroke-dasharray: 100 120`, animate
  `stroke-dashoffset` from 101 to 0 over 500-800 ms. (A plain `100` dash at offset 100 still
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
  or a second packet. Fix by staggering (60-120 ms), moving one of the
  changes 0.3-0.5 s later, or leaving secondary elements static (they are already right in the
  resting frame).
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
- Ambient motion (glows, slow drifts) stays under 20 % of the visual energy of the primary story.

## Audit checklist

Run before shipping each fragment. Every "no" is a fix.

1. Does it play once (no `infinite`, iteration count 1, fill `forwards`/`both`) in a 4-10 s pass
   with setup, action, resolution and a 0.8-1.5 s hold, and end exactly on the resting frame
   (render a time past the pass and `rest`: identical)? Are there no repeated pulses, marching
   dashes or second runs of the same move? (`loop` only when asked: 8-15 s, 1-2 s hold.)
2. Are at most three things moving at any second, and about a third of the elements active?
3. Do entrances use the enter curve, exits the exit curve at ~65 % of the entrance time, and
   on-screen moves the move curve?
4. Is `linear` used only for continuous motion?
5. Are all durations in the table's classes (micro, element, scene, hop)?
6. Is every group's stagger under 500 ms, and does card content follow the card by 50-150 ms?
7. Do packets use `offset-path`, at 0.6-1.2 s per hop?
8. Do draw-on paths use `pathLength` and 0.5-0.8 s per path?
9. Is changing text done by cross-fading stacked `<text>` elements?
10. Does nothing overshoot or pulse more than +-5 %?
11. Does every animated element have a full-pass track with no `animation-delay`, whose 100 %
    stop equals its resting value?
12. Is the resting frame the final state and readable as a still (also under reduced motion)?
13. Is all text at or above the contract minimum at rendered size, with no overlap at any
    rendered phase?
14. Concurrency: at most three things (or one staggered series) moving at any instant, never
    more than 8? At most one glow visible at a time, and no glowing arrow, wire, line or series?
15. `step` only: does the wrapper carry `data-anim-phases` with one mark per narrated phase
    (3 to 5), each at a settled moment, the last at the hold start, and is the step-host
    snippet in the deck head? `loop` only: if longer than 5 s, does the host offer a pause key
    (or is `once` used)?
