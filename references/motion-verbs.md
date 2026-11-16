# Motion verbs

What the movement on a slide can say. A fragment has one **verb**: the main motion, the one
that is the slide's claim. Pick it from the claim, before the form and before any technique.
A dot travelling along a line is one verb of twenty (`travel`), and it is right only when
something really travels.

Limits for every verb ([motion-rules.md](motion-rules.md), [style.md](style.md)): one calm pass
of 4 to 10 s that rests on the finished frame, nothing loops or repeats, at most three things
move at once, no overshoot, the lean look, and nothing drawn that the source does not state
([accuracy.md](accuracy.md)). A slide that already has a figure keeps that figure's form; the
verb then says how that figure moves, not what it turns into.

## 1. From claim to verb

Write the slide's claim as one sentence with a real verb in it (the picture idea,
[archetypes.md](archetypes.md)). The grammar of that sentence picks the motion:

| The claim says | Verbs to consider |
|---|---|
| a number: how much, how many, more than, share of | `grow`, `count`, `accumulate`, `race`, `thin` |
| "became", "replaced", "turned into", old and new | `transform`, `wipe`, `switch` |
| "made of", "consists of", "breaks down into", groups | `split`, `sort`, `open`, `stack` |
| "joins", "combines", "pooled", "together they" | `merge`, `accumulate` |
| "because", "drives", "causes", "the more ... the more" | `drive`, `balance`, `switch` |
| "inside", "within", "part of", "underneath" | `zoom`, `open`, `nest` |
| "versus", "trade-off", "at the cost of" | `balance`, `race` |
| "returns", "again", "feeds back" | `cycle` |
| "from A to B", "is sent", "is handed to", a route | `travel`, `trace` |
| order and nothing more | `reveal` (support move, section 4): the row builds; no traveller |

**The travel test.** `travel` needs a thing the source names (a parcel, a patient, a
request, a drop of water) that changes place, and places the source names. A list of steps is
not a journey: steps that are only in order get `reveal`, and steps that change a quantity,
a state or a shape get the verb of that change. Write the traveller's name in the brief; "a
dot" is not a name.

**One object from the subject.** Prefer the thing itself over a labelled ring: a jar, a beam,
a ballot, a cell, a ledger column, a river bed, drawn in a few thin strokes (a scene needs the
source to describe the physical thing). Rings on a line are the fallback when the source gives
no object, not the default.

## 2. The verbs

`Says` is the meaning. `Screen` is what is seen during the pass and what it rests on.
`Build` is the CSS/SVG mechanism (details in section 5).

### Quantity

- **`grow`** Says: a quantity rises or falls. Fits: a metric, a level, before and after
  values. Screen: a bar, column or level moves from the stated start to the stated end at true
  proportion; a dashed ghost keeps the start. Build: `scaleX`/`scaleY` on the fill about its
  baseline.
- **`count`** Says: a number is reached. Fits: one headline figure; always paired with a
  second verb that shows the quantity (`grow`, `accumulate`). Screen: the numeral steps
  through a few stated or round values and lands on the source's number as the picture lands.
  Build: a digit strip under a clip, or stacked `<text>` cross-faded.
- **`accumulate`** Says: many small things add up to a whole. Fits: budgets, savings,
  backlogs, deposits, doses. Screen: units (one unit = a stated amount) arrive in a staggered
  series into a container and the level or pile rises to the stated total. Build: per-unit
  rise or drop plus a `scaleY` level; units are a series, so they count as one move.
- **`thin`** Says: fewer remain. Fits: funnels, attrition, decay, erosion, depreciation.
  Screen: a field of units at exact scale; at each stage the ones that do not pass fade or
  fall away, the rest stay where they are. Build: opacity per unit in `steps()`; a band that
  tapers to the stated counts.
- **`race`** Says: two quantities under the same clock; the gap is the point. Fits: A versus
  B on one measure, old versus new duration, cost or speed. Screen: two bars or markers start
  together at the same rate, one stops early, the gap is then bracketed and labelled with the
  stated difference. Build: the same keyframes with different end values; a draw-on bracket.

### Composition

- **`split`** Says: one whole divides into parts. Fits: a budget breakdown, a population by
  group, cell division, one cause with several outcomes. Screen: one shape; cut lines appear;
  the parts move apart by a small gap, each at its stated share, and get their labels. Build:
  parts are separate groups from the start, drawn touching; `translate` opens the gaps.
- **`merge`** Says: several join into one. Fits: mergers, pooled funds, tributaries, a
  consensus, a synthesis. Screen: parts move inward until they touch; at the moment they meet
  the outline becomes one and takes the accent. Build: `translate` inward, then a cross-fade
  from the part outlines to the whole outline.
- **`sort`** Says: the same units, rearranged, show a structure. Fits: shares, majorities,
  rankings, "of every 100 ...". Screen: a grid of identical units; each unit slides to its
  group or rank and takes its group's colour; group labels and counts appear last. Build: one
  `translate` track per unit (rows as a staggered series); the same element moves, it is
  never swapped for another.
- **`stack`** Says: each level rests on the one below. Fits: prerequisites, maturity levels,
  strata, layered costs. Screen: layers rise into place bottom-up, each one settling on the
  last. Build: staggered rise per layer; the pyramid or stairs as the resting frame.
- **`nest`** Says: one thing contains another. Fits: jurisdiction, scope, sets and subsets,
  hierarchy by containment. Screen: the innermost thing first, then each enclosing outline
  draws around it, outward, with its label on the outline. Build: draw-on of rings or
  outlines, inside out.

### Change

- **`transform`** Says: the same thing takes a new form. Fits: a redefinition, a
  metamorphosis, a shape changing under a cause (a coastline, a curve flattening, a
  distribution shifting). Screen: one outline changes into another in place; the old outline
  stays as a dashed ghost. Build: `d: path()` keyframes between paths with the same commands,
  inside `@supports`, with a cross-fade as the base (section 5).
- **`wipe`** Says: one state replaces another; what differs is the point. Fits: reform,
  redesign, land use then and now. Screen: the before picture; a thin boundary line sweeps
  across once and the after picture stands behind it; elements that did not change do not
  move. Build: `clip-path: inset()` on the after layer, the boundary line translated with it.
- **`switch`** Says: the same object, a new condition, at the moment of a cause. Fits:
  status changes, thresholds crossed, ripeness, health, legal status. Screen: the cause
  arrives (a level reaches a line, a signature lands), then the object changes colour, glyph
  or outline in place. Build: stacked copies cross-faded; a colour step along a stated scale.

### Cause

- **`balance`** Says: two things weigh against each other. Fits: trade-offs, supply and
  demand, arguments for and against, equilibrium. Screen: a beam on a pivot; weights land
  one by one on each side; the beam tilts to the side the source says is heavier and stops.
  Build: `rotate` on the beam group about the pivot, pans counter-rotated to hang straight.
  Only when the source states which side outweighs, or that they are level.
- **`drive`** Says: one part moves another. Fits: mechanisms and physical metaphors the
  source uses itself: a lever, a valve, gears, a pump, a pulley, a dam gate. Screen: the first
  part moves, then the part it acts on, in that order and in true ratio. Build: coupled
  `rotate`/`translate` tracks with the second starting 50 to 150 ms after the first; a gear
  ratio is an angle ratio.

### Looking closer

- **`zoom`** Says: the explanation is in a part of the whole. Fits: nested scale (organ to
  cell, country to district, year to one week). Screen: the whole; a ring marks the part; the
  view moves into it until it fills the slot and the finer detail fades in; a small outline of
  the whole stays in a corner. Build: `scale` and `translate` on one root group, a cross-fade
  between the two levels of detail.
- **`open`** Says: this is inside, or this is how the parts fit. Fits: anatomy, a device, a
  layered product, a budget line with sub-lines. Screen: either the shell is cut away to show
  the contents (cutaway), or the layers move apart along one axis, get their labels and stay
  apart (exploded view). Build: `clip-path: inset()` on the shell; `translate` per layer
  along one axis.

### Path and time

- **`travel`** Says: a named thing goes from one named place to another. Fits: logistics, a
  patient pathway, a message between actors, migration. Screen: the traveller as a small
  glyph or labelled chip that says what it is, moving once along the route; it changes on
  arrival (colour, tick, new label) when the source says it does. Build: `offset-path`.
  Passes the travel test in section 1 or is not used.
- **`trace`** Says: a route, a curve or a trajectory takes shape. Fits: a trend whose shape
  is the point, a border, an orbit, a signature path. Screen: the line draws on at even speed
  and stops; reference lines and the one named event appear when the line reaches them.
  Build: draw-on by `stroke-dashoffset`, or a growing clip rect for a data series.
- **`cycle`** Says: the end feeds the start. Fits: seasons, feedback loops, reuse, a life
  cycle. Screen: stations on a ring; the arc draws once around and closes on its start; the
  closing segment is the last move and takes the accent. One trip, then rest. Build: draw-on
  of a circle path; no rotation that repeats.

## 3. Combining

A fragment has one main verb and at most two supporting ones, in sequence, never at once.
Pairs that work: `accumulate` + `count`; `grow` + `switch` (the level reaches the line, the
state changes); `sort` + `count`; `zoom` + any verb inside the detail; `trace` + `switch`
(a timeline scrubbed: the cursor moves along the axis and the picture above changes at each
stop); `split` + `grow` (the parts become bars).

## 4. Support moves

Never the main verb of a fragment that has a claim beyond order.

- **`reveal`**: the static frame and items enter in a staggered series, in an order that
  follows the content (reading order for a sequence, centre out for a hub, bottom up for a
  base, cause before effect). It is the whole motion only for an order-only slide.
- **`mark`**: an annotation drawn onto what is already there: an underline, a ring around a
  value, a bracket with a label, a strike-through. A highlight sits behind the text, a mark
  on top. Used for the one element the claim is about; three at most.
- **`dim`**: everything outside the current focus drops to 0.35 opacity (0.55 to 0.65 on a
  light ground) so one part can be read alone.

## 5. Mechanisms

Checked in Chromium with `scripts/render-phases.sh`. Every animated element has one
full-pass keyframe track that ends on its resting value (motion-rules.md, Techniques).

- **Scale about a point** (`grow`, `zoom`): `transform-box: view-box` and a
  `transform-origin` in px at the baseline, pivot or focus. A level is `scaleY` from the
  stated start ratio to 1.
- **Rotate about a pivot** (`balance`, `drive`): the same two properties; angles from the
  source or small (under 15 degrees) when the source gives only a direction.
- **Units** (`accumulate`, `sort`, `thin`): one element per unit, 20 to 100 units, one unit
  = a stated amount, written in a mono note ("1 dot = 100 voters"). Stagger by row or group
  so the series stays under about 1.2 s. A unit that moves keeps its identity to the end.
  Declare the series with `data-anim-series="<id>"` on the units or their parent `<g>`:
  the checker then counts it as one move (same properties on every member, starts at most
  120 ms apart, each staged step over within 1.6 s, at most 100 members; motion-rules.md,
  Concurrency).
- **Digit strip** (`count`): a column of `<text>` values inside a `<clipPath>` window, moved
  with `translateY` in `steps()`; three to six values, the last the source's number. CSS
  counters do not render in SVG text.
- **Wipe and cutaway**: `clip-path: inset(0 100% 0 0)` to `inset(0)` on a `<g>`; for a
  cutaway the inset grows on the shell instead.
- **Morph** (`transform`): both paths with the same commands in the same order. Base rule:
  the two shapes stacked and cross-faded. Enhancement inside
  `@supports (d: path("M0 0"))`: hide the second shape and animate `d` on the first. Safari
  does not animate `d` and shows the cross-fade. Polygons can morph everywhere with
  `clip-path: polygon()` at equal vertex counts.
- **Uneven travel** (`travel` through a narrowing): `offset-distance` keyframes that are not
  evenly spaced, so units slow before the narrow point and spread after it.
- **Draw-on**: `pathLength="100"`, `stroke-dasharray: 100 120`, `stroke-dashoffset` 101 to 0.

## 6. Shape of a pass

The verb is the action; give it room. A pass that spends its seconds on entrances and one
second on the claim has the proportions backwards.

| Part | Share | What |
|---|---|---|
| set | 10 to 20 % | the static frame and the starting state enter (`reveal`); the start is a readable picture |
| action | 40 to 60 % | the verb, in two to four staged steps with a settled moment between them |
| answer | 10 to 20 % | what the action produced: the gap bracket, the total, the new label, a `mark` |
| hold | 0.8 to 1.5 s | nothing moves; this is the resting frame |

- **Stage it.** Change one kind of thing per step: positions first, then colours, then
  labels. A staged change is easier to follow than everything interpolating at once.
- **Same element, same thing.** An element that stands for something keeps standing for it;
  between unrelated pictures cross-fade, do not fly shapes across.
- **Follow-through.** What the action touches reacts 50 to 150 ms after it: the label lands
  after its bar, the pan dips after the weight.
- **Something visibly changes in every phase,** and each phase mark is a picture that reads
  as a still.
- **One hero.** The thing the verb acts on is the largest thing in the slot (about 40 % of
  it or more). Supporting moves are smaller and start 100 to 200 ms after the hero's.
- **Ease by role.** Arrivals decelerate, moves on screen ease in and out, a level or a bar
  runs at the move curve; one easing on everything reads as generated (motion-rules.md,
  Easing).
- **Still is allowed.** A slide that is explained by pointing at parts of one picture gets
  the picture, `dim` and one `mark` per phase. Do not invent a traveller to have motion.
- **Cover the words.** With every label hidden, the frames at the phase marks should still
  show that something grew, split, tipped or changed. If they show the same picture with a
  dot in different places, the verb is missing.

## 7. Verbs across a deck

Write the verb in the triage table and the brief. When the same main verb covers more than a
third of a deck's fragments (and at least three), re-read those slides: each repeat needs a
reason from the source in its triage row, and `travel` needs the traveller's name. A deck
where every fragment is `travel` or `reveal` has drawn the layout of its text, not its ideas.
