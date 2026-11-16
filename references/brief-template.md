# Brief template

One brief per fragment. The fragment's quality follows the brief's quality, so fill in every
field before building. When several fragments are built in parallel, put the shared fields
(theme, fonts, stage size, gate) in one `BRIEF.md` and give each fragment its own copy of the
per-fragment fields.

Rules that every fragment follows anyway (shape, prefixing, tokens, gate, resting frame,
legibility, control) live in [fragment-contract.md](fragment-contract.md). Do not restate them in
the brief; only record the choices the contract leaves open.

## Fields

```markdown
# Brief: <name>

- **Name:** <kebab-case, 2-24 chars, unique in the deck>
- **Subject:** <one sentence: what the viewer should understand when the pass ends>
- **Audience / tone:** <who watches, how technical, calm or lively>
- **Picture idea:** <one sentence: what the slide says beyond the order of its items; "order only" when that is all; "source figure: <form>" when the slide has its own figure>
- **Form:** <from [archetypes.md](archetypes.md) "Picture idea and form", or bespoke; every element of it stated by the source>
- **Verb:** <one of the twenty verbs or `reveal`, from [motion-verbs.md](motion-verbs.md) section 1>, from the claim: "<the slide's claim as one sentence with a real verb in it>"; supporting verbs, at most two, in sequence
- **Traveller:** <`travel` only: the thing the source names and the places it names ("a dot" is not a name); otherwise "-">
- **Mechanism:** <the CSS/SVG mechanism of the verb from [motion-verbs.md](motion-verbs.md) section 5, and which elements carry it>
- **Archetype:** pipeline | graph | timeline | states | compare | layers | chart (the build family whose composition and timing the form borrows; the motion comes from the verb)
- **Slot:** viewBox `0 0 <W> <H>`, rendered at <w> x <h> px on a <stage> stage
  (see [layouts.md](layouts.md)); text scale = <w> / <W> = <s>
- **Min text size:** <px in viewBox units> so that px * <s> >= 18 (titles >= 22)

## Composition
<Elements with coordinates in viewBox units, left to right / top to bottom.
e.g. "ring `build` r 34 at (500, 180), label below at y 254; line build->test along y 180".>

## Phases
| t (s) | Label | Enters | Highlighted | Flows | Caption |
|---|---|---|---|---|---|
| 0.0 | ... | ... | ... | ... | ... |

- **Cycle:** <seconds> (the pass length: 4 to 10 s for once and step, 8 to 15 s for loop, including the hold)
- **Phases (marks):** <settled moments between narrated steps, nothing visible mid-motion there; three to five (six when the slide narrates six steps), ascending, the last at the hold start; e.g. 2, 4.5, 7> (becomes `data-anim-phases`)
- **Resting frame:** <what the still shows: final state, which labels, which colours>
- **Control:** once | step | loop (the deck's choice from intake, the same for every fragment; loop only on request; a different value needs a reason in `anim/triage.md`; under step the presenter uses the keyboard or a clicker, since a wheel or swipe skips phases)

## Theme
- **Look:** match | lean (one choice per deck; see input-stage.md "Look")
- default `--anim-*` tokens, or the host's `--anim-theme-*` values: <list, or "anim/host-theme.css">
- Colour roles: <which token marks what, e.g. `--anim-accent` = active item, `--anim-ok` = passed>
- **Font hints:** <host font names to set as `--anim-theme-font` / `--anim-theme-mono`, or "system">
- **Replaces:** <the slide element that goes away: the four cards, the tag pills, the HTML diagram>

## Verification plan
- Seconds to render: <t1 t2 t3 ... rest> (one per phase, plus `rest`)
- What each frame must show: <one line per second>
```

## Deliverable

One file `<name>.html` that satisfies [fragment-contract.md](fragment-contract.md), placed in
`<work-dir>/<name>/<name>.html`. Report back: path, viewBox, cycle length, phases with second
marks, and anything not verified.

## Verify

1. `python3 scripts/check_fragment.py <dir>/<name>.html --name <name> --rendered-width <w> --stage-width <stage>`
2. `scripts/render-phases.sh <dir> <W> <H> <seconds from the plan> rest`
3. Open every PNG with your image viewing tool. Fix clipping, overlap, unreadable text, empty panels.
4. `python3 scripts/verify_facts.py <dir>/<name>.html --source <outline.json> --slide <N> --spec <dir>/spec.yaml` passes; every WARN reviewed.
   Re-render. Iterate at least once.

Contract section 8 is the definition of done.

## Example: savings jar (finance lesson)

The slide, from a school lesson on personal finance: title "Fill the jar"; bullets "Put €50 in
the jar every month", "After a year the jar holds €600"; notes "Small amounts add up". Every
number below is the slide's, except €300, derived as 6 x €50 (accuracy.md rule 1).

```markdown
# Brief: savings-jar

- **Name:** savings-jar
- **Subject:** Twelve monthly deposits of €50 fill the jar to €600 in a year.
- **Audience / tone:** secondary-school class; calm, concrete, no jokes in the graphic.
- **Picture idea:** many small deposits add up to one full jar.
- **Form:** a jar (the slide names it) filling coin by coin, with a running total beside it
- **Verb:** `accumulate`, then `count`, from the claim: "Twelve deposits of €50 add up to
  €600 in a year."
- **Traveller:** -
- **Mechanism:** units (motion-verbs.md section 5): 12 coin elements, one coin = one monthly
  deposit of €50 (twelve, not 20 or more: one per deposit the slide states), each a short drop into the jar in a staggered series; the fill is `scaleY`
  about the jar's base; the total is a digit strip (€0, €300, €600) in `steps()`.
- **Archetype:** states (the fill level of `canal-lock` as the bar; the jar is hand-built)
- **Slot:** viewBox `0 0 1680 600`, rendered at 1680 x 600 px on a 1920x1080 stage; text scale = 1.0
- **Min text size:** 20 (labels), 26 (the total)

## Composition
Jar outline (thin stroke, open top) x 660-1020, y 70-520, the hero at about 45 % of the slot
height and more; fill rect inside it, base at y 516. Coins: 12 rings r 16 that rest in two
stacked rows of six inside the jar, each dropping from y 20. Total `€600` (26 px) at
(1200, 300) in a clip window; mono note "1 coin = €50, one month" at (1200, 340). Bracket
along the jar's right side, x 1040, y 70-516. Caption "Small amounts add up".

## Phases
| t (s) | Label | Enters | Highlighted | Flows | Caption |
|---|---|---|---|---|---|
| 0.0 | set | jar draws on, total "€0", mono note | - | - | - |
| 1.2 | months 1-6 | coins 1-6 drop, stagger 120 ms; fill rises to half | newest coin | - | - |
| 2.6 | half | total steps to "€300" | total | - | - |
| 3.2 | months 7-12 | coins 7-12 drop; fill rises to the top | newest coin | - | - |
| 4.6 | full | total steps to "€600" | total | - | - |
| 5.4 | answer | bracket draws on beside the jar | bracket | - | "Small amounts add up" |
| 6.2 | hold | - | total | - | - |

The hold from 6.2 s to 7.2 s is the finished state and stays (it is the resting frame).

- **Cycle:** 7.2 s
- **Phases (marks):** 2.6, 4.6, 6.2 (half full, full, the hold start)
- **Resting frame:** the full jar with twelve coins, the bracket, "€600" in `--anim-accent`, the
  mono note and the caption.
- **Control:** once

## Theme
- default tokens; host may override via `--anim-theme-*`.
- Colour roles: `--anim-accent` = the total and the newest coin, `--anim-line` = jar and
  bracket, `--anim-muted` = the mono note.
- **Font hints:** system

## Verification plan
- Seconds: 0 1.2 2.6 3.2 4.6 5.4 6.2 7.2 rest
- 0: jar outline drawing; 2.6: six coins at rest, fill at half, "€300"; 4.6: twelve coins,
  jar full, "€600"; 6.2, 7.2 and rest: identical, bracket and caption shown, nothing mid-drop.
- Labels hidden, the 2.6 and 4.6 frames still show a jar filling (motion-verbs.md section 6).
- verify_facts: WARN derived for €300 (6 x €50) and WARN words for "coin" (the unit legend)
  are expected; both are named in the report.
```

## Example: not a row (biology, header fields only)

The slide is five numbered bullets: "Blood glucose rises after a meal", "the pancreas releases
insulin", "cells take up glucose", "blood glucose falls back", "lower glucose slows insulin
release; the loop closes". Read as a list it is a five-step row; the last bullet says it returns.

```markdown
- **Picture idea:** blood glucose rises and falls back, and the fall slows the insulin that
  lowered it.
- **Form:** a closed ring of the five bullets around a glucose level that fills and drains;
  the return edge is the last bullet's own; no values (the slide gives none).
- **Verb:** `cycle`, then `grow` for the level, from the claim: "Lower glucose slows the
  insulin release that lowered it."
- **Archetype:** states (ring recipe: the arc draws once around and closes on the return edge;
  `water-cycle` open as the bar)
```
