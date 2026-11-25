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
| a handover across a boundary | a drawn boundary line the token crosses | `travel` (the thing handed over) | `pipeline` / `timeline` / `graph` | `er-patient-flow` |
| the same thing before and after | the thing in place, the old state as a ghost | `transform`, `wipe`, `switch` | `states` / `compare` | `oxbow-lake` (transform), `street-redesign` (wipe), `contract-formation`, `job-states`, `phase-changes` (switch) |
| a physical mechanism the source describes | a scene: the thing itself, in cross-section | `drive`, `open` | `states` / `pipeline` | `breathing` (drive), `earth-layers` (open), `canal-lock` |
| a place or a route | a map or a path with stations | `travel`, `trace` | `pipeline` | `parcel-route` (travel), `forgetting-curve` (trace) |
| a hierarchy | a tree | `reveal` (root down), `nest` | `graph` | none; `service-deps` for rank spacing |
| a spectrum or scale | points on one axis | `sort`, `trace` | `timeline` | `blood-types` (sort), `roadmap` |

**Form from the data relationship.** When the slide's point is a number, the form follows
what the number does, not how it was printed:

| The numbers state | Form |
|---|---|
| a ratio or share ("one in four adults", "62 % of seats") | a scaled real object (a glass filled to the share) or one whole split at the share |
| a change over time (a debt growing, a glacier retreating) | one curve, or one level that grows or falls |
| a composition (a household budget, the gases in air) | one whole split into its parts, each at its stated size |
| a scale ("the size of 40 football pitches") | one large thing beside a familiar reference at true proportion |
| before and after (a court backlog before and after reform) | two pictures built the same way that differ in one place only |

Not allowed: a row of big numbers with a bar chart beside it, or number cards. This table
only picks a form for prose or bullets that state numbers: a slide with its own figure keeps
that form (stairs stay stairs), and nothing appears that the source does not state.

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

The drawing follows `style.md`: nodes are rings (r 34 at 1920) or glyphs with the text outside
(label 24 px 600 in `--anim-font`, sub-label 18 px muted in `--anim-font`, mono only when the
sub is data), groups are hairline brackets (1.5 px) with a label in `--anim-font`, the caption
is plain centred text with no strip. Structure is 2 px in `--anim-line`, the active path 4 px in
the accent. What the story has reached stays in the accent without glow; one glow at a time,
on what is active now. One element carries `data-anim-focal`.

All coordinates are viewBox units for the archetype's default `size`. The scaffolder
(`scripts/scaffold_from_spec.py`) computes the positions below from the spec; a hand build
starts from the same frame.

- Padding 24 on every side.
- Title row (only when `title` is set): y 0-64, the title at least 1.25x the label size.
- Caption (only when any phase has a `note`): a strip of about 56 at the bottom, plain text with
  no panel, the label size or 1.25x above it; notes are stacked `<text>` cross-faded per phase.
- Content band: from y 64 (or 24) to the caption strip (or H-24). Everything below is placed in
  this band.
- Edge labels 18 px, in mono only when they are data (a rate, a code, a time).

**Spacing and the focal step.** Even spacing is the default for equal peers. When the source
stresses one step (the outcome, the bottleneck, the one that changed), that step is the focal
element: give it about 1.3x the pitch of its neighbours (take the room evenly from the others)
and a mark about 1.5x a peer (ring r 50 instead of 34), or put the hero number beside it.
The scaffolder keeps the spacing even when the extra pitch would squeeze the peers' labels;
the larger ring still marks the step.
Keep gaps inside a group at most half the gap between groups.

**Limits.** At most 12 nodes in a figure and at most 8 spokes on one hub; more means split the
slide or keep a list.

## pipeline

**Fits:** 3-7 ordered steps, one direction, maybe one feedback / rollback edge.
**Default:** 1680 x 440.

**Composition.** Steps are labels on one horizontal line with a small ring marker each (r 34),
no boxes and no chips (`style.md`). Equal peers sit at a pitch of `min(380, (W - 80) / n)`,
centred: `x_i = W/2 - (n-1) * pitch / 2 + i * pitch` (5 steps at 1680: 1600/5 = 320, so 200,
520, 840, 1160, 1480). Labels hang below the ring; skip and back edges arc over the top. When
the labels need more room than one row gives, the scaffolder wraps the row in two (a snake).
A focal step gets the extra pitch and the larger ring described above; with a short row the
figure may start on the headline's left anchor instead of centring.

**Motion story.**
- Setup (0-1 s): the line draws on left to right; each ring lands as the line reaches it, its
  label settles 60 to 120 ms later.
- Action: the highlight moves on ring to ring, about 0.8-1 s per step: the receiving ring
  turns active (`--anim-accent` with the glow), the previous one stays in the accent, solid,
  without glow. Under `travel` only, the traveller the source names (a labelled chip or glyph,
  not a bare dot) hops with it (`offset-path` on the line's `d`). Other verbs (`thin` on a
  funnel, `grow` in a ring) use their own mechanism on this timing.
- Resolution: the last ring is the focal element; `--anim-ok` only when the slide states
  success. A rollback, if any, draws the dotted arc on in `--anim-danger` or `--anim-warn`
  (under `travel` the traveller takes it).
- Hold 0.8-1.5 s on all steps reached; that end state is the resting frame.

**Techniques:** line draw-on with `pathLength="100"`; highlight by stroke token change; status
words as stacked `<text>` cross-fades; the traveller with `offset-path` (`travel` only).
**Pass:** 7-10 s (once).

**Mistakes.**
- A dot added to an order-only row: `reveal` has no traveller.
- Travellers on every segment at once: only the current hop moves.
- Spacing set by the longest label: keep the pitch, shorten the label, use `sub` for detail.
- Every step the same when the source stresses one: give the focal step room and weight.

## graph

**Fits:** dependencies, call graphs, service maps, anything with branches or merges. 4-12 nodes.
**Default:** 1680 x 600.

**Composition.** Layered left to right by rank (longest path from a source; sources rank 0).
Each node is a ring (r 34) or glyph with its label below; when the height runs out the label
moves beside the ring, and as a last resort the rings shrink. Columns sit at equal gaps (60,
then 44, then 32 when tight) inside a 40 margin; rows in a column are ordered by the mean row
of their parents. Edges are cubic curves between ring ports:
`M x1,y1 C x1+k,y1 x2-k,y2 x2,y2` with k half the horizontal gap, clamped to 40-120.
`depends` edges get a small open arrowhead at the dependency. Groups are hairline brackets
(1.5 px, `--anim-line`) over their members with the label in `--anim-font`, muted, never a
tinted rect. Rectangles only when the source shows containers. The critical node (most
incoming edges, or the one the source stresses) is the focal element: larger ring, more room
around it. A hub has at most 8 spokes.

**Motion story.**
- Setup: brackets draw on first, then rank 0 rings land.
- Action: rank by rank, incoming edges draw on and their rings land as each edge arrives; the
  node being discussed is active, everything else at 60 % opacity. Under `split` or `merge`
  the fan opens from, or closes on, its one node. Under `travel` only, one traveller per edge
  being explained, max 3 at once.
- Resolution: whole graph visible, the focal node keeps the accent.
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

**Composition.** One horizontal axis, 2 px `--anim-line`, inset by a margin m (at least 80,
wide enough that the end labels stay inside the 24 padding). Milestones evenly spaced:
`x_i = m + i * (W - 2m) / (n-1)`. Marker dot r 10 on the axis. The `at` label (a date, so mono,
18 px, `--anim-muted`) sits on the other side of the dot from the label. With 4 or more
milestones labels alternate above and below on thin 1.5 px leaders so neighbours never collide.
Eras are hairline brackets under everything. The "now" milestone (or the one the source
stresses) is the focal element: a larger dot, and the hero date or number when the source
states one.

**Motion story.**
- Setup: axis draws on left to right (0.8 s).
- Action: a progress line (`--anim-accent`, 4 px) grows along the axis; as it reaches each
  marker, the marker lands (scale 0.92 to 1, land curve) and its label settles after it.
  Reached milestones stay in the accent without glow, the "now" milestone carries the glow,
  future ones stay in line colour. `--anim-ok` only where the slide states a milestone was
  met. This progress line is the family's own pass (`reveal` or `trace`); under `travel` (a
  handover the source names, `court-case`) the named traveller crosses the axis or boundary
  instead of a progress line.
- Resolution: progress stops at "now" or at the last milestone.
- Hold: all labels visible.

**Techniques:** progress line as the axis path with `pathLength="100"` and dashoffset tied to
the phase times; labels via opacity and a small rise; `at` labels never move.
**Pass:** 6-9 s (once).

**Mistakes.**
- Spacing by real dates when gaps vary 10x: space evenly, put the date in `at`.
- Progress line `linear` across the whole pass: it is a move with stops, use the move curve
  per segment.
- The glow on every milestone at the end: reached ones are solid accent, only "now" (or the
  last) is focal.

## states

**Fits:** lifecycles, status machines, retry / error loops, modes. 3-6 states.
**Default:** 1200 x 600.

**Composition.** States as rings (r 34) on an ellipse centred in the content band, first state
at the left (angle 180 deg), clockwise in list order; each label sits outside its ring,
radially. The ellipse is as wide as the labels allow. For 3-4 states a single row (pipeline
coordinates) with return arcs above and below also works. Transitions as thin arcs bowing
toward the centre so the outside stays free for text, arrowhead at the target, label (18 px,
mono only when it is data) at the arc midpoint. The current state carries the accent; a token
(circle r 12, `--anim-accent`) marks it only under `travel` or `cycle` (a thing the source
names that goes round). The terminal or "healthy" state is the focal element.

**Motion story.**
- Setup: all states visible but dimmed; the initial state active.
- Action: the highlight moves along the story path: each transition draws on (0.8-1.2 s),
  then the target lights up and the transition label turns `--anim-accent`, the previous state
  dims. Error transitions in `--anim-danger`. Under `cycle` the arc draws once around and
  closes on its start; under `travel` or `cycle` with a named token, the token rides each
  transition (`offset-path`) instead of the draw-on. Under `switch` the state changes in place.
- Resolution: highlight (or token) at the terminal or "healthy" state.
- Hold.

**Techniques:** draw-on per transition; highlight by fill/stroke token change; labels as
stacked `<text>`; the token with `offset-path` per transition (`travel`/`cycle` only, one
element per hop, each with its own full-pass track).
**Pass:** 7-10 s (once).

**Mistakes.**
- Showing every transition in one pass: show the story path, leave rare ones static.
- Self-loops drawn as tiny circles that clip the label: use a 60-wide loop on the outer side
  of the ring.
- Two current states (or two tokens) at once: there is exactly one current state.

## compare

**Fits:** before/after, old vs new, option A vs B. Up to 5 rows per side.
**Default:** 1680 x 600.

**Composition.** Two to four columns separated by space only (gap 80 for two, 56 for more),
no panels. Each column has a header at the top (the label of a group whose members are all on
that side, else "Before" / "After"), then rows of text with 1.5 px hairline rules between
them, rows spread evenly over the band. Rows with the same index on both sides correspond:
align them exactly. Verdict goes in the caption, not in a panel. The winning side, or its one
decisive row, is the focal element (the hero number when the source states one).

**Motion story.**
- Setup: headers settle; left rows appear with a short stagger (40 to 120 ms, later ones
  closer).
- Action: right side rows appear row by row, each row highlighting the pair it replaces
  (left dims to `--anim-muted`, right turns `--anim-accent`; `--anim-ok` only when the slide
  calls it better). A metric counts via a digit strip. Under `race`, `balance`, `wipe` or
  `transform` the verb's mechanism is the action and the row-by-row reveal shrinks to the set.
- Resolution: the winning side in full, the other at 60 % opacity.
- Hold.

**Techniques:** digit strips or cross-fading `<text>` stacks for changing numbers; highlight by
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

**Composition.** Horizontal bands of equal height, layer 0 at the bottom, separated by 1.5 px
hairlines, no band rects. Layer name at the left in `--anim-font`, sentence case, muted, at
sub-label size (the label of a group whose members all share that layer, else "Layer N"); the
name column is as wide as the longest name. Nodes are rings with their text to the right, one
slot per node across the rest of the band. Edges between layers are vertical (ring to ring),
slightly offset (+-12 x) so a down and an up edge do not overlap. The layer the story ends on
(or the one the source stresses) is the focal element.

**Motion story.**
- Setup: hairlines draw on bottom-up (stagger 100 ms), rings land after their hairline, names
  settle last.
- Action: the highlight moves down through the named nodes, each turning active in turn, then
  back up; nodes already reached stay in the accent without glow. Under `travel` only (the
  source names the request and its path) a request traveller rides top to bottom and a
  response travels back up. Under `nest`, `zoom` or `open` the verb's mechanism replaces the
  down-and-up pass.
- Resolution: top node active with the result.
- Hold.

**Techniques:** hairline draw-on; highlight by stroke token change; travellers with
`offset-path` on vertical paths (`travel` only).
**Pass:** 7-10 s (once).

**Mistakes.**
- Bands entering top-down: stacks build from the bottom.
- Layer names in tracked capitals or mono: sentence case in `--anim-font`.
- Labels inside thin bands below 18 px: with 5 layers use 1200 x 680 or drop `sub`.
- Request and response on the same path: offset them so both remain visible.

## chart

**Fits:** a metric over time, a spike and recovery, a threshold crossing. 1-3 series.
**Default:** 1680 x 600.

**Composition.** Plot area from x 120 (wider when the tick labels need it) to the right edge
minus the series labels, top of the band to its bottom minus the x tick row. Y axis with 3-5
gridlines (`--anim-line`, 1.5 px, 60 % opacity), tick labels 18 px mono right-aligned left of
the axis, tabular numbers. X axis at the plot bottom, 2 px. Series: the one the story is about
4 px in `--anim-accent`, others 2 px in `--anim-accent-2` or `--anim-line`; label at the line
end. Event: vertical dashed line `--anim-muted` from plot top to bottom at the event's x,
an outlined tag (1.5 px, 18 px text) at the top. Threshold, if any, as a horizontal dashed line
with a label. The key value is the focal element: the end point with its readout, at hero
size when the source states the number.

**Motion story.**
- Setup: axes draw on, gridlines follow.
- Action: series draw on left to right in step with the pass (the x range maps to the action
  window); each event's line and tag appear as the trace reaches it. This is `trace`; under it
  a small dot may ride the head of the line. Bars and levels use `grow` instead.
- Resolution: full trace, events tagged, the key value as a readout that counts to its value.
- Hold.

**Techniques:** draw-on with `pathLength="100"` (a head dot, under `trace`, uses `offset-path`
with the same `d`), digit strips or cross-fading `<text>` readouts, for live-looking signals a scrolling trace group with
`translateX` (`linear`, see `pool/latency-trace/latency-trace.html`).
**Pass:** 7-10 s (once).

**Mistakes.**
- Raw data with 1000 points: downsample to <= 200; the path should stay small.
- Y axis not starting at a sensible baseline, making a 2 % change look like 200 %.
- Draw-on and event tags out of sync: compute tag times from the x mapping, not by eye.
