# Archetypes

Seven layouts cover almost every slide illustration. Pick one, write the spec
([spec-format.md](spec-format.md)), then use the section below for composition and motion.
Timing and easing values are in [motion-rules.md](motion-rules.md); hard limits in
[fragment-contract.md](fragment-contract.md) section 6.

## Decision table

| Content signal | Archetype |
|---|---|
| Numbered steps, "then", "after that", arrows in one direction, a chain with no branches | `pipeline` |
| "depends on", "calls", "uses", "talks to", branches, merges, many-to-many, architecture boxes | `graph` |
| Dates, quarters, versions, "phase 1/2/3", roadmap, history | `timeline` |
| "when X happens it goes to", statuses, lifecycle, retry loops, modes | `states` |
| "before / after", "old vs new", "us vs them", pros and cons, two columns | `compare` |
| Stack, tiers, "built on top of", OSI-like levels, request passing down and back up | `layers` |
| Numbers over time, a metric, a trend, a spike, a threshold, "load", "latency" | `chart` |

Ties: a chain with one feedback edge stays `pipeline`; a chain with a real branch is `graph`.
A roadmap with dependencies between items is `timeline` plus notes, not `graph`.

## Shared frame

All coordinates are viewBox units for the archetype's default `size`.

- Padding 24 on every side.
- Title row (only when `title` is set): y 0-64, text baseline y 42, 26 px, `--anim-fg`, weight 700.
- Caption strip (only when any phase has a `note`): y H-64 to H-8, panel rect `--anim-panel`,
  text baseline H-26, 22 px, `--anim-fg`; notes are stacked `<text>` cross-faded per phase.
- Content band: from y 64 (or 24) to H-72 (or H-24). Everything below is placed in this band.
- Labels 22 px, `sub` 18 px `--anim-muted`, edge labels 18 px `--anim-mono`.

## pipeline

**Fits:** 3-7 ordered steps, one direction, maybe one feedback / rollback edge.
**Default:** 1680 x 440.

**Composition.** One row of boxes, centred in the content band. Box 240 x 120, radius 8.
`gap = (1680 - 80 - n*240) / (n-1)` with 40 side margins, keep >= 80 (for 5 boxes: x 40, 380, 720, 1060, 1400,
gap 100). With title and caption the band is y 64-368: boxes at y 156-276, wire along y 216.
Label baseline at box y+54, `sub` at y+84. Status chip 64 x 28 above each box at y 116.
Feedback edges arc below the row: `M x_from,276 C x_from,340 x_to,340 x_to,276`. With 7 boxes
shrink to 200 x 110.

**Motion story.**
- Setup (0-1 s): boxes fade in left to right, stagger 80 ms; wires draw on.
- Action: one packet hops box to box (`offset-path` on the wire's `d`, 0.8-1 s per hop); the
  receiving box turns active (stroke `--anim-accent`), the previous one settles to `--anim-ok`.
- Resolution: last box `--anim-ok`, chip shows the outcome; a rollback, if any, sends a packet
  along the dotted arc in `--anim-danger` or `--anim-warn`.
- Hold 1.5-2 s on all boxes done.

**Techniques:** packets with `offset-path`; wire draw-on with `pathLength="100"`; status chips
as stacked `<text>` cross-fades; highlight by stroke token change.
**Cycle:** 10-13 s.

**Mistakes.**
- Packets on every wire at once: only the current hop moves.
- Boxes sized to the longest label: fix the box, shorten the label, use `sub` for detail.
- Feedback arc drawn through the boxes or over the caption strip: keep it between y 280 and 360.

## graph

**Fits:** dependencies, call graphs, service maps, anything with branches or merges. 4-12 nodes.
**Default:** 1680 x 600.

**Composition.** Layered left to right by rank (longest path from a source; sources rank 0).
Up to 5 columns at x 40, 380, 720, 1060, 1400 (node 220 x 84, radius 8); up to 4 rows per
column, row pitch 120, column centred in the content band (band y 24-528 with caption: rows at
y 116, 236, 356, 476 for four). Edges as cubic curves from the right edge mid-point to the left
edge mid-point: `M x1,y1 C x1+80,y1 x2-80,y2 x2,y2`. `depends` edges get an arrowhead at the
dependency. Groups: rect around members with 20 padding and 32 extra on top for the label
(18 px, `--anim-muted`, at group x+16, y+24), fill `color-mix(in srgb, var(--anim-accent) 6%, transparent)`.

**Motion story.**
- Setup: groups fade in first (element duration), then rank 0 nodes.
- Action: rank by rank, nodes enter and their incoming edges draw on; one packet per edge being
  explained, max 3 at once. The node being discussed is active, everything else at 60 % opacity.
- Resolution: whole graph visible, the critical node (most incoming edges, or the one the
  source stresses) stays active.
- Hold: everything at full opacity.

**Techniques:** draw-on per edge (`pathLength`), packets on the edge path, dimming via
`opacity` on non-active nodes, arrowheads as small `<path>` (no `<marker>` with ids that
collide; if you use `<marker>`, prefix its id).
**Cycle:** 12-15 s.

**Mistakes.**
- Edge crossings from list order: sort each column by the mean row of its parents.
- Too many nodes: more than 12 means split by group.
- Arrow direction inconsistent: `depends` always points at the thing depended on.

## timeline

**Fits:** roadmaps, history, release trains, project phases. 3-8 milestones.
**Default:** 1680 x 440.

**Composition.** Horizontal axis at y 220, x 160 to 1520, stroke `--anim-line` 3 px, inset so
the first and last label boxes (260 wide, centred on their markers) stay inside the 24 px padding.
Milestones evenly spaced: `x_i = 160 + i * 1360 / (n-1)` (5 milestones: 160, 500, 840, 1180,
1520). Marker circle r 14 on the axis. `at` label (mono, 18 px, `--anim-muted`) below the axis
at y 262. Labels alternate above (box 260 x 72, bottom at y 186) and below (top at y 284) so
neighbours never collide; for 5 or fewer, all above is fine. Connector tick 1.5 px from marker
to label box.

**Motion story.**
- Setup: axis draws on left to right (0.8 s).
- Action: a progress line (`--anim-accent`) grows along the axis; as it reaches each marker,
  the marker fills and its label pops in (scale 0.92 to 1, enter curve). Past milestones settle
  to `--anim-ok`, the "now" milestone stays `--anim-accent`, future ones stay outlined.
- Resolution: progress stops at "now" or at the last milestone.
- Hold: all labels visible.

**Techniques:** progress line as the axis path with `pathLength="100"` and dashoffset tied to
the phase times; labels via opacity + scale; `at` labels never move.
**Cycle:** 10-12 s.

**Mistakes.**
- Spacing by real dates when gaps vary 10x: space evenly, put the date in `at`.
- Progress line `linear` across the whole cycle: it is a move with stops, use the move curve
  per segment.
- Every milestone highlighted at the end: only "now" or the last stays accent.

## states

**Fits:** lifecycles, status machines, retry / error loops, modes. 3-6 states.
**Default:** 1200 x 600.

**Composition.** States as pills 200 x 72 (radius 36) on an ellipse centred at (600, 290),
rx 400, ry 190, first state at the left (angle 180 deg), clockwise in list order. For 3-4 states
a single row (pipeline coordinates scaled) with return arcs above and below also works.
Transitions as arcs bulging outward from the centre, arrowhead at the target, label (18 px mono)
at the arc midpoint offset 20 away from the centre. A token (circle r 12, `--anim-accent`)
marks the current state.

**Motion story.**
- Setup: all states visible but dimmed; the initial state active.
- Action: the token travels along each transition (`offset-path`, 0.8-1.2 s); on arrival the
  target lights up and the transition label flashes to `--anim-accent`, the previous state dims.
  Error transitions in `--anim-danger`.
- Resolution: token at the terminal or "healthy" state.
- Hold.

**Techniques:** token with `offset-path` per transition (one element per hop, each with its own
full-cycle track); highlight by fill/stroke token change; labels as stacked `<text>`.
**Cycle:** 10-14 s.

**Mistakes.**
- Showing every transition in one loop: show the story path, leave rare ones static.
- Self-loops drawn as tiny circles that clip the label: use a 60-wide loop above the pill.
- Two tokens at once: there is exactly one current state.

## compare

**Fits:** before/after, old vs new, option A vs B. Up to 5 rows per side.
**Default:** 1680 x 600.

**Composition.** Two panels: left x 24-828, right x 852-1656, both y 24 to H-72 (or H-24),
panel rect `--anim-panel`, radius 8. Header in each panel at y+48, 26 px (the label of a group
whose members are all on that side, else "Before" / "After"). Rows inside a panel:
item box (panel width - 48) x 64 at panel x+24, first row y 104, pitch 84. Rows with the same
index on both sides correspond: draw a faint connector or align them exactly. Verdict goes in
the caption strip, not in a panel.

**Motion story.**
- Setup: both panels and headers in; left items appear (stagger 80 ms).
- Action: right side items appear row by row, each row highlighting the pair it replaces
  (left dims to `--anim-muted`, right turns `--anim-ok`). A metric can count via stacked text.
- Resolution: right panel outlined `--anim-ok` (or the winning side), left at 60 % opacity.
- Hold.

**Techniques:** cross-fading `<text>` stacks for changing numbers; highlight by stroke and
fill token change; side-by-side slide-in (`translateX(30px)` to 0, enter curve).
**Cycle:** 9-12 s.

**Mistakes.**
- Unequal rows: give both sides the same row count, pad with an empty row.
- Red/green as the only difference: also change weight, icon or label (colour blindness).
- Animating both sides at once: the eye can follow one side at a time.

## layers

**Fits:** stacks, tiers, protocol layers, platform diagrams; request down, response up.
2-5 layers, 1-4 nodes per layer.
**Default:** 1200 x 600.

**Composition.** Horizontal bands, layer 0 at the bottom. Band height
`(band_h - (L-1)*12) / L` (4 layers, band y 24-528: 117 each, tops at 411, 282, 153, 24).
Band rect x 24-1176, `--anim-panel`, radius 8; layer name at x 48, 18 px `--anim-muted` (the
label of a group whose members all share that layer, else "Layer N").
Nodes as chips 220 x 64 inside the band, centred vertically, spread evenly from x 260 to 1152.
Edges between layers are vertical (chip centre to chip centre), slightly offset (+-12 x) so a
down and an up edge do not overlap.

**Motion story.**
- Setup: bands build bottom-up (stagger 100 ms, rise 12 px), chips land 80 ms after their band.
- Action: a request packet travels top to bottom through the named chips; each chip flashes
  active on arrival. Then a response packet travels back up in `--anim-ok`.
- Resolution: top chip active with the result.
- Hold.

**Techniques:** packets with `offset-path` on vertical paths; band entrance by `translateY` +
opacity; highlight by stroke token change.
**Cycle:** 10-13 s.

**Mistakes.**
- Bands entering top-down: stacks build from the bottom.
- Labels inside thin bands below 18 px: with 5 layers use 1200 x 680 or drop `sub`.
- Request and response on the same path: offset them so both remain visible.

## chart

**Fits:** a metric over time, a spike and recovery, a threshold crossing. 1-3 series.
**Default:** 1680 x 600.

**Composition.** Plot area x 120-1620, y 40 to H-140 (with caption: y 40-460). Y axis at x 120
with 3-5 gridlines (`--anim-line`, 1.5 px, 60 % opacity), tick labels 18 px mono right-aligned at
x 108. X axis at the plot bottom, tick labels at y+30. Series as polylines 3 px: first
`--anim-accent`, second `--anim-accent-2`, third `--anim-ok`; label at the line end (x+12).
Event: vertical dashed line `--anim-muted` from plot top to bottom at the event's x, tag
(panel chip, 18 px) at the top. Threshold, if any, as a horizontal dashed line with a label.

**Motion story.**
- Setup: axes and gridlines in (element duration).
- Action: series draw on left to right in step with the cycle (the x range maps to the action
  window); a dot rides the head of the line; each event's line and tag appear as the trace
  reaches it.
- Resolution: full trace, events tagged, the key value as a readout.
- Hold.

**Techniques:** draw-on with `pathLength="100"` (the head dot uses `offset-path` with the same
`d`), cross-fading `<text>` readouts, for live-looking signals a scrolling trace group with
`translateX` (`linear`, see `pool/latency-trace/latency-trace.html`).
**Cycle:** 10-14 s.

**Mistakes.**
- Raw data with 1000 points: downsample to <= 200; the path should stay small.
- Y axis not starting at a sensible baseline, making a 2 % change look like 200 %.
- Draw-on and event tags out of sync: compute tag times from the x mapping, not by eye.
