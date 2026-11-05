# Motion rules

A motion identity for slide illustrations and the audit an agent runs before shipping a
fragment. Hard limits (text size, max moving elements, cycle range, reduced-motion rule) are in
[fragment-contract.md](fragment-contract.md) section 6; this file explains how to meet them.

Personality: calm and precise. No overshoot, no bounce, no elastic. The viewer is listening to a
speaker; motion points at things, it does not perform.

## Durations

| Class | Duration | Use |
|---|---|---|
| micro | 150-250 ms | chip pop, colour change, highlight on/off, tick |
| element | 300-500 ms | a box or label entering, a short move, a cross-fade |
| scene | 600-900 ms | a group rearranging, a long move across the slot, a large draw-on |
| hop | 600-1200 ms | one packet along one wire |
| hold | 1-2 s | end of the loop before the reset |

Anything slower than 900 ms that is not a hop or a continuous loop reads as lag.

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
- **Loop structure:** setup (elements enter) -> action (the story happens) -> resolution (the
  outcome is shown) -> hold (1-2 s on the final state) -> quick reset. The resting frame equals
  the end of resolution.
- **Linear only for continuous motion:** marching dashes on a wire, a scrolling trace in a strip
  chart, a spinner. Never for a move with a start and an end.

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
- **Full-cycle tracks:** give every animated element its own keyframe track that spans the whole
  cycle (`animation: <name>-x 12s infinite`) with the timing expressed as keyframe percentages.
  Avoid `animation-delay` inside the fragment; it breaks loop restarts and phase rendering.
- Percent of cycle = seconds / cycle * 100. Write the second mark in a comment next to each
  keyframe stop.

## Reduced motion and presenter control

- The contract's `prefers-reduced-motion` rule shows the resting frame; check that the still
  tells the story without motion.
- Loops longer than 5 s: the host deck should offer a pause key. If it cannot, consider
  `step` control (contract section 7).
- Ambient motion (glows, slow drifts) stays under 20 % of the visual energy of the primary story.

## Audit checklist

Run before shipping each fragment. Every "no" is a fix.

1. Does the loop have setup, action, resolution and a 1-2 s hold, within 8-15 s?
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
11. Does every animated element have a full-cycle track with no `animation-delay`?
12. Is the resting frame the final state and readable as a still (also under reduced motion)?
13. Is all text at or above the contract minimum at rendered size, with no overlap at any
    rendered phase?
14. If the loop is longer than 5 s, does the host offer a pause key (or is `step` used)?
