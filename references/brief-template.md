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
- **Archetype:** pipeline | graph | timeline | states | compare | layers | chart (the build family whose recipe and timing the form borrows)
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

## Example: CI/CD pipeline

```markdown
# Brief: deploy-pipeline

- **Name:** deploy-pipeline
- **Subject:** A commit passes build, test and staging before it reaches production; a failed
  test stops it.
- **Audience / tone:** engineering all-hands; calm, technical, no jokes in the graphic.
- **Picture idea:** order only: the slide lists five stages and says nothing else about them.
- **Form:** a row of rings on one line
- **Archetype:** pipeline
- **Slot:** viewBox `0 0 1680 440`, rendered at 1680 x 440 px on a 1920x1080 stage
  (full-width body above a caption line); text scale = 1.0
- **Min text size:** 20 (labels), 26 (stage names)

## Composition
Five rings r 34 on one line along y 180, at x 160, 500, 840, 1180, 1520: commit, build, test,
staging, production; labels below at y 254, status words (mono) above at y 128.
Packet: glowing dot r 10 on the line path.

## Phases
| t (s) | Label | Enters | Highlighted | Flows | Caption |
|---|---|---|---|---|---|
| 0.0 | setup | line draws on, rings fade in, stagger 80 ms | - | - | - |
| 1.0 | commit | dot appears at commit | commit | - | "push" |
| 2.0 | build | build status "ok" | build | dot commit->build | - |
| 3.5 | test | test status "ok" | test | dot build->test | - |
| 5.0 | staging | staging status "ok" | staging | dot test->staging | - |
| 6.0 | release | production status "live" | production | dot staging->production | "released" |
| 7.0 | hold | - | all statuses | - | - |

The hold from 7 s to 8 s is the finished state and stays (it is the resting frame).

- **Cycle:** 8 s
- **Phases (marks):** 2, 3.5, 5, 6, 7 (five settled frames, one after each narrated step: commit, build, test, staging, release; the hold starts at 7)
- **Resting frame:** all five rings, all statuses "ok"/"live", production ring in `--anim-ok`.
- **Control:** once

## Theme
- default tokens; host may override via `--anim-theme-*`.
- Colour roles: `--anim-accent` = stage currently processing, `--anim-ok` = passed,
  `--anim-muted` = idle labels, `--anim-line` = wires.
- **Font hints:** system

## Verification plan
- Seconds: 0 1 2 3.5 5 6 7 8 rest
- 0: rings entering; 1: dot at commit; 3.5: build "ok", dot leaving build for test;
  6: dot leaving staging for production; 7: production highlighted, all statuses; 8 and rest:
  identical, all statuses, no dot.
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
- **Archetype:** states (ring recipe, one token; `water-cycle` open as the bar)
```
