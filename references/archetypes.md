# Archetypes

The seven archetypes below are build families: recipes for composition and timing, not the
menu of pictures and not the motion. The picture comes first: write the slide's picture idea,
read its form and verb off the table in "Picture idea and form", write the spec
([spec-format.md](spec-format.md)), then build with the family the table names. The family
gives the frame, the spacing and the phase timing; the motion comes from the verb and its
mechanism ([motion-verbs.md](motion-verbs.md)). A packet, token or head dot belongs to
`travel` (and to `cycle` or `trace` where the recipe says so), not to the family. Timing and easing values are in
[motion-rules.md](motion-rules.md); hard limits in [fragment-contract.md](fragment-contract.md)
section 6. Each **Pass** is for the default `once`
control: the motion story plays one time when the slide becomes current and its hold is the
resting frame. Under `step` (a per-deck choice at intake) the same pass is played in click
segments: put the `data-anim-phases` marks at the ends of the narrated phases each recipe lists,
3 to 5 per slide, where nothing is mid-move. A requested `loop` (kiosk, gallery, hero) stretches
the same story to 8 to 15 s.

## Picture idea and form

For each slide whose content is prose, bullets, cards or a text table, write one sentence before
choosing anything: what does this slide say beyond the order of its items? What changes,
shrinks, grows, returns, competes, contains, splits or crosses a boundary? That sentence is the
**picture idea** (triage column `Idea`, brief field `Picture idea:`); the **form** follows from
it, and the **verb** (triage column `Verb`) from the claim sentence
([motion-verbs.md](motion-verbs.md) section 1). Read the section's claim, not its formatting: a
numbered list is a cue about the layout of the text, not the shape of the idea. A slide that already has a figure, chart or
meaning-carrying illustration keeps that figure's form (stairs stay stairs, bars stay bars, a table of values stays rows);
this step does not apply to it.

| Picture idea | Form | Verb | Build family | Pool entry for craft |
|---|---|---|---|---|
| order only: A, then B, then C, nothing more | a row of rings on one line | `reveal` | `pipeline` | `roadmap`, `funding-options` (they build with no traveller) |
| it returns: the end feeds the start | a closed ring | `cycle` | `states` | `water-cycle` |
| it narrows: fewer pass each stage | a tapering funnel, dots at scale | `thin` | `pipeline` | `sales-funnel` |
| it accumulates or matures: each level rests on the one below | stairs or a stack built bottom-up | `stack`, `accumulate` | `layers` | `bloom-taxonomy` (stack), `petition-threshold` (accumulate) |
| a level or quantity changes | a fill level, a bar, a gauge | `grow`, `count` | `states` / `chart` | `canal-lock`, `compound-interest` |
| two things pull against each other | two sides, a balance | `balance`, `race` | `compare` | `energy-balance` (balance), `mediation-vs-trial`, `cache-compare` (race) |
| one thing contains another | rings inside rings | `nest`, `zoom` | `layers` | `number-sets`, `service-deps` (nest), `leaf-stomata` (zoom) |
| one splits into several, or several merge | fan-out, fan-in | `split`, `merge` | `graph` | `mitosis` (split), `coalition-majority` (merge), `loan-decision` (a branch) |
| actors exchange something | lanes, one token handed between them | `travel` (the thing exchanged) | `graph` | `hiring-lanes` |
| a handover across a boundary | a drawn boundary line the token crosses | `travel` (the thing handed over) | `timeline` / `graph` | `court-case` |
| the same thing before and after | the thing in place, the old state as a ghost | `transform`, `wipe`, `switch` | `states` / `compare` | `oxbow-lake` (transform), `street-redesign` (wipe), `contract-formation`, `job-states`, `phase-changes` (switch) |
| a physical mechanism the source describes | a scene: the thing itself, in cross-section | `drive`, `open` | `states` / `pipeline` | `breathing` (drive), `earth-layers` (open), `canal-lock` |
| a place or a route | a map or a path with stations | `travel`, `trace` | `pipeline` | `parcel-route` (travel), `forgetting-curve` (trace) |
| a hierarchy | a tree | `reveal` (root down), `nest` | `graph` | none; `service-deps` for rank spacing |
| a spectrum or scale | points on one axis | `sort`, `trace` | `timeline` | `blood-types` (sort), `roadmap` |

**Order only is a correct answer.** When the source says only order, draw the row, write
"order only" as the idea and `reveal` as the verb: the row builds in reading order and the
highlight moves on, with no traveller, since a list of steps is not a journey (the travel test,
[motion-verbs.md](motion-verbs.md) section 1). The form may come from structure the source
states; the content may not grow: no node, label, number, arrow direction or actor the source does not state. A funnel
needs the source's quantities or its stated narrowing; a cycle needs the source to say it
returns; a traveller needs the source to name it and its places; a scene needs the source to describe the physical thing ([accuracy.md](accuracy.md)).
Every form plays one calm pass and rests on the finished frame ([motion-rules.md](motion-rules.md)).

The pool entry is the bar for craft (stroke weights, type sizes, spacing, technique), not a
picture to copy. A form the scaffolder does not emit is hand-built with the family's recipe
as its timing skeleton; that is the normal path, not an exception.

## Decision table

For an idea that is the structure itself (dependencies, dates, a data series), or to pick the
family for a form the table above leaves open.

| Content signal | Archetype |
|---|---|
| Order and nothing more (after the picture idea): numbered steps, "then", a chain with no branches | `pipeline` |
| "depends on", "calls", "uses", "talks to", branches, merges, many-to-many, architecture boxes | `graph` |
| Dates, quarters, versions, "phase 1/2/3", roadmap, history | `timeline` |
| "when X happens it goes to", statuses, lifecycle, retry loops, modes | `states` |
| "before / after", "old vs new", "us vs them", pros and cons, two columns | `compare` |
| Stack, tiers, "built on top of", OSI-like levels, request passing down and back up | `layers` |
| Numbers over time, a metric, a trend, a spike, a threshold, "load", "latency" | `chart` |

Ties: a chain with one feedback edge stays `pipeline`; a chain with a real branch is `graph`.
A roadmap with dependencies between items is `timeline` plus notes, not `graph`.

## Shared frame

The drawing follows `style.md`: nodes are rings (r 34 at 1920) with the text outside (label
24 px 600, sub 18 px mono muted), groups are hairline brackets with a mono label, the caption is
plain centred text with no strip, and the active element carries the accent with a soft glow.

All coordinates are viewBox units for the archetype's default `size`.

- Padding 24 on every side.
- Title row (only when `title` is set): y 0-64, text baseline y 42, 26 px, `--anim-fg`, weight 700.
- Caption (only when any phase has a `note`): y H-64 to H-8, plain text with no panel,
  baseline H-26, 22 px, `--anim-fg`; notes are stacked `<text>` cross-faded per phase.
- Content band: from y 64 (or 24) to H-72 (or H-24). Everything below is placed in this band.
- Labels 22 px, `sub` 18 px `--anim-muted`, edge labels 18 px `--anim-mono`.

## pipeline

**Fits:** 3-7 ordered steps, one direction, maybe one feedback / rollback edge.
**Default:** 1680 x 440.

**Composition.** Steps are labels on one horizontal line with a small ring marker each (r 34),
no boxes and no chips (`style.md`). Ring centres `x_i = 160 + i * 1360 / (n-1)` (5 steps: 160,
500, 840, 1180, 1520), inset so the outer labels stay inside the padding. With title and caption
the band is y 64-368: line along y 180, label baseline y 254, `sub` at y 282, a status word (mono
18 px) above the ring at y 128. Feedback edges arc below the labels:
`M x_from,300 C x_from,350 x_to,350 x_to,300`. With 7 steps keep labels short or alternate
them above and below the line.

**Motion story.**
- Setup (0-1 s): the line draws on; rings and labels fade in left to right, stagger 80 ms.
- Action: the highlight moves on ring to ring, about 0.8-1 s per step: the receiving ring
  turns active (`--anim-accent` with glow), the previous one settles to `--anim-ok`. Under
  `travel` only, the traveller the source names (a labelled chip or glyph, not a bare dot) hops
  with it (`offset-path` on the line's `d`). Other verbs (`thin` on a funnel, `grow` in a
  ring) use their own mechanism on this timing.
- Resolution: last ring `--anim-ok`, its status word shows the outcome; a rollback, if any,
  draws the dotted arc on in `--anim-danger` or `--anim-warn` (under `travel` the traveller
  takes it).
- Hold 0.8-1.5 s on all steps done; that end state is the resting frame.

**Techniques:** line draw-on with `pathLength="100"`; highlight by stroke token change; status
words as stacked `<text>` cross-fades; the traveller with `offset-path` (`travel` only).
**Pass:** 7-10 s (once).

**Mistakes.**
- A dot added to an order-only row: `reveal` has no traveller.
- Travellers on every segment at once: only the current hop moves.
- Spacing set by the longest label: keep the even spacing, shorten the label, use `sub` for detail.
- Feedback arc drawn through the labels or over the caption: keep it between y 296 and 360.

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
- Action: rank by rank, nodes enter and their incoming edges draw on; the node being discussed
  is active, everything else at 60 % opacity. Under `split` or `merge` the fan opens from, or
  closes on, its one node. Under `travel` only, one traveller per edge being explained, max 3
  at once.
- Resolution: whole graph visible, the critical node (most incoming edges, or the one the
  source stresses) stays active.
- Hold: everything at full opacity.

**Techniques:** draw-on per edge (`pathLength`), dimming via `opacity` on non-active nodes,
travellers on the edge path (`travel` only), arrowheads as small `<path>` (no `<marker>` with ids that
collide; if you use `<marker>`, prefix its id).
**Pass:** 8-10 s (once).

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
  This progress line is the family's own pass (`reveal` or `trace`); under `travel` (a
  handover the source names, `court-case`) the named traveller crosses the axis or boundary
  instead of a progress line.
- Resolution: progress stops at "now" or at the last milestone.
- Hold: all labels visible.

**Techniques:** progress line as the axis path with `pathLength="100"` and dashoffset tied to
the phase times; labels via opacity + scale; `at` labels never move.
**Pass:** 6-9 s (once).

**Mistakes.**
- Spacing by real dates when gaps vary 10x: space evenly, put the date in `at`.
- Progress line `linear` across the whole pass: it is a move with stops, use the move curve
  per segment.
- Every milestone highlighted at the end: only "now" or the last stays accent.

## states

**Fits:** lifecycles, status machines, retry / error loops, modes. 3-6 states.
**Default:** 1200 x 600.

**Composition.** States as pills 200 x 72 (radius 36) on an ellipse centred at (600, 290),
rx 400, ry 190, first state at the left (angle 180 deg), clockwise in list order. For 3-4 states
a single row (pipeline coordinates scaled) with return arcs above and below also works.
Transitions as arcs bulging outward from the centre, arrowhead at the target, label (18 px mono)
at the arc midpoint offset 20 away from the centre. The current state carries the accent; a
token (circle r 12, `--anim-accent`) marks it only under `travel` or `cycle` (a thing the
source names that goes round).

**Motion story.**
- Setup: all states visible but dimmed; the initial state active.
- Action: the highlight moves along the story path: each transition draws on (0.8-1.2 s),
  then the target lights up and the transition label turns `--anim-accent`, the previous state
  dims. Error transitions in `--anim-danger`. Under `cycle` the arc draws once around and
  closes on its start; under `travel` or `cycle` with a named token, the token rides each
  transition (`offset-path`) instead of the draw-on. Under `switch` the state changes in place.
- Resolution: token at the terminal or "healthy" state.
- Hold.

**Techniques:** draw-on per transition; highlight by fill/stroke token change; labels as
stacked `<text>`; the token with `offset-path` per transition (`travel`/`cycle` only, one
element per hop, each with its own full-pass track).
**Pass:** 7-10 s (once).

**Mistakes.**
- Showing every transition in one pass: show the story path, leave rare ones static.
- Self-loops drawn as tiny circles that clip the label: use a 60-wide loop above the pill.
- Two current states (or two tokens) at once: there is exactly one current state.

## compare

**Fits:** before/after, old vs new, option A vs B. Up to 5 rows per side.
**Default:** 1680 x 600.

**Composition.** Two panels: left x 24-828, right x 852-1656, both y 24 to H-72 (or H-24),
panel rect `--anim-panel`, radius 8. Header in each panel at y+48, 26 px (the label of a group
whose members are all on that side, else "Before" / "After"). Rows inside a panel:
item box (panel width - 48) x 64 at panel x+24, first row y 104, pitch 84. Rows with the same
index on both sides correspond: draw a faint connector or align them exactly. Verdict goes in
the caption, not in a panel.

**Motion story.**
- Setup: both panels and headers in; left items appear (stagger 80 ms).
- Action: right side items appear row by row, each row highlighting the pair it replaces
  (left dims to `--anim-muted`, right turns `--anim-ok`). A metric can count via stacked text.
  Under `race`, `balance`, `wipe` or `transform` the verb's mechanism is the action and the
  row-by-row reveal shrinks to the set.
- Resolution: right panel outlined `--anim-ok` (or the winning side), left at 60 % opacity.
- Hold.

**Techniques:** cross-fading `<text>` stacks for changing numbers; highlight by stroke and
fill token change; side-by-side slide-in (`translateX(30px)` to 0, enter curve).
**Pass:** 6-9 s (once).

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
- Action: the highlight moves down through the named chips, each turning active in turn, then
  back up in `--anim-ok`. Under `travel` only (the source names the request and its path) a
  request traveller rides top to bottom and a response travels back up. Under `nest`, `zoom`
  or `open` the verb's mechanism replaces the down-and-up pass.
- Resolution: top chip active with the result.
- Hold.

**Techniques:** band entrance by `translateY` + opacity; highlight by stroke token change;
travellers with `offset-path` on vertical paths (`travel` only).
**Pass:** 7-10 s (once).

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
- Action: series draw on left to right in step with the pass (the x range maps to the action
  window); each event's line and tag appear as the trace reaches it. This is `trace`; under it
  a small dot may ride the head of the line. Bars and levels use `grow` instead.
- Resolution: full trace, events tagged, the key value as a readout.
- Hold.

**Techniques:** draw-on with `pathLength="100"` (a head dot, under `trace`, uses `offset-path`
with the same `d`), cross-fading `<text>` readouts, for live-looking signals a scrolling trace group with
`translateX` (`linear`, see `pool/latency-trace/latency-trace.html`).
**Pass:** 7-10 s (once).

**Mistakes.**
- Raw data with 1000 points: downsample to <= 200; the path should stay small.
- Y axis not starting at a sensible baseline, making a 2 % change look like 200 %.
- Draw-on and event tags out of sync: compute tag times from the x mapping, not by eye.
