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
- **Question:** <the audience question: what a person in the audience would ask that this slide answers, in their words, ending in "?"; taken from the triage row's Question (SKILL.md Phase 0), written before drawing, next to the claim in Verb; no answer, no key word or number of the claim in it ("What happens to the boat in the lock?", not "Does the boat leave one level higher?"); the blind review asks it of the resting slide as `sN-question` ([look-rubric.md](look-rubric.md) section 1)>
- **Insight:** <"By seeing <what changes> unfold, the audience understands <what> better than from the still."; no such sentence, no fragment: the slide's base ships (SKILL.md Phase 0)>
- **Insight on the slide:** <what in the resting frame shows the insight to someone who missed the pass: the trace, the marked stretch, the before beside the after, in the source's words>
- **Audience / tone:** <who watches, how technical, calm or lively>
- **Picture idea:** <one sentence: what the slide says beyond the order of its items; "order only" when that is all; "source figure: <form>" when the slide has its own figure>
- **Form:** <from [archetypes.md](archetypes.md) "Picture idea and form", or bespoke; every element of it stated by the source>
- **Verb:** <one of the twenty verbs or `reveal`, from [motion-verbs.md](motion-verbs.md) section 1>, from the claim: "<the slide's claim as one sentence with a real verb in it>"; supporting verbs, at most two, in sequence
- **Traveller:** <`travel` only: the thing the source names and the places it names ("a dot" is not a name); otherwise "-">
- **Focal element:** <the one thing the eye lands on in the resting frame, marked `data-anim-focal`: the hero text or the shape that is the claim (the full jar, the tipped beam)>
- **Hero:** <the one number or word that is the claim, with where the source states it; "-" when the source states none>
- **Mechanism:** <the CSS/SVG mechanism of the verb from [motion-verbs.md](motion-verbs.md) section 5, and which elements carry it>
- **Archetype:** pipeline | graph | timeline | states | compare | layers | chart (the build family whose composition and timing the form borrows; the motion comes from the verb)
- **Slot:** viewBox `0 0 <W> <H>`, rendered at <w> x <h> px on a <stage> stage
  (see [layouts.md](layouts.md)); text scale = <w> / <W> = <s>
- **Min text size:** <px in viewBox units> so that px * <s> >= 18 (titles >= 22)

## Composition
<Elements with coordinates in viewBox units, left to right / top to bottom.
e.g. "ring `build` r 34 at (500, 180), label below at y 254; line build->test along y 180".>

## Beats
- **Setup and payoff:** <the gap or question the first frame leaves open, and the beat that closes it; e.g. "empty jar, total €0; closed at 5.0 s when the full jar's total lands">

| Time (s) | On screen | What moves (one step of the verb) | End state | Why this beat exists |
|---|---|---|---|---|
| 0.0 | ... | ... | ... | ... |

<Required, written before any SVG. A first frame where everything already stands in its
final place has no setup: rethink the picture (motion-rules.md, Setup, then payoff). One primary move per beat; a beat with no reason is cut.
Things enter by kind (motion-rules.md, Entrance by kind); a 400 to 600 ms stillness comes
just before the answer beat.>

- **Cycle:** <seconds> (the pass length: 4 to 10 s for once and step, 8 to 15 s for loop, including the hold)
- **Phases (marks):** <settled moments between narrated steps, nothing visible mid-motion there; three to five (six when the slide narrates six steps), ascending, the last at the hold start; e.g. 2, 4.5, 7> (becomes `data-anim-phases`)
- **Resting frame:** <what the still shows: final state, which labels, which colours; it answers the Question and shows the Insight without the motion>
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
- **Question:** How does a jar of savings get full?
- **Insight:** By seeing the jar fill coin by coin, the class understands that the €600 is
  nothing but the twelve small deposits.
- **Insight on the slide:** the full jar keeps its twelve separate coins beside "€600", with
  the note "1 coin = €50, one month".
- **Audience / tone:** secondary-school class; calm, concrete, no jokes in the graphic.
- **Picture idea:** many small deposits add up to one full jar.
- **Form:** a jar (the slide names it) filling coin by coin, with a running total beside it
- **Verb:** `accumulate`, then `count`, from the claim: "Twelve deposits of €50 add up to
  €600 in a year."
- **Traveller:** -
- **Focal element:** the total "€600" (`data-anim-focal`), the only hero-size text.
- **Hero:** "€600", from the slide's second bullet.
- **Mechanism:** units (motion-verbs.md section 5): 12 coin elements, one coin = one monthly
  deposit of €50 (twelve, not 20 or more: one per deposit the slide states), each a short drop into the jar in a staggered series; the fill is `scaleY`
  about the jar's base on the move curve; the total is a digit strip (€0, €300, €600) in `steps()`.
- **Archetype:** states (the fill level of `canal-lock` as the bar; the jar is hand-built)
- **Slot:** viewBox `0 0 1680 600`, rendered at 1680 x 600 px on a 1920x1080 stage; text scale = 1.0
- **Min text size:** 20 (sub-label), 72 (the hero total)

## Composition
Jar outline (thin stroke, open top) x 660-1020, y 70-520, about 45 % of the slot height and
more; fill rect inside it, base at y 516. Coins: 12 rings r 16 that rest in two stacked rows
of six inside the jar, each dropping from y 20. Total `€600` (72 px, tabular figures) at
(1200, 300) in a clip window; mono note "1 coin = €50, one month" (20 px) at (1200, 350).
Bracket along the jar's right side, x 1040, y 70-516. Caption "Small amounts add up".

## Beats
- **Setup and payoff:** an empty jar and "€0"; closed at 5.0 s, when the full jar's total
  "€600" lands.

| Time (s) | On screen | What moves (one step of the verb) | End state | Why this beat exists |
|---|---|---|---|---|
| 0.0 | empty jar, "€0", note | jar outline draws on; "€0" and the note settle after it | an empty jar to fill | the viewer sees the container before anything goes in |
| 1.2 | coins 1-6 | coins drop, stagger 120 ms closing to 60 ms; fill rises to half | six coins, half full | small deposits visibly pile up |
| 2.6 | the total | steps to "€300" | "€300" | half a year has a number |
| 3.2 | coins 7-12 | coins drop the same way; fill rises to the top | twelve coins, full jar | the second half fills the jar |
| 4.5 | full jar | nothing (stillness, 0.5 s) | unchanged | the full jar is seen before its total arrives |
| 5.0 | the total | steps to "€600" and takes the accent | "€600" | the claim's number lands |
| 5.6 | bracket, caption | bracket draws on beside the jar; caption cross-fades in | bracket and caption shown | ties the total to the whole jar |
| 6.2 | - | nothing (hold) | resting frame | the finished picture stays |

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
- Seconds: 0 1.2 2.6 3.2 4.6 5.6 6.2 7.2 rest
- 0: jar outline drawing; 2.6: six coins at rest, fill at half, "€300"; 4.6: twelve coins,
  jar full, still "€300"; 6.2, 7.2 and rest: identical, "€600", bracket and caption shown,
  nothing mid-drop.
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
