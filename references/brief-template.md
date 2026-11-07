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
- **Archetype:** pipeline | graph | timeline | states | compare | layers | chart
- **Slot:** viewBox `0 0 <W> <H>`, rendered at <w> x <h> px on a <stage> stage
  (see [layouts.md](layouts.md)); text scale = <w> / <W> = <s>
- **Min text size:** <px in viewBox units> so that px * <s> >= 18 (titles >= 22)

## Composition
<Elements with coordinates in viewBox units, left to right / top to bottom.
e.g. "box `build` at x 40 y 120 w 220 h 120; wire build->test along y 180".>

## Phases
| t (s) | Label | Enters | Highlighted | Flows | Caption |
|---|---|---|---|---|---|
| 0.0 | ... | ... | ... | ... | ... |

- **Cycle:** <seconds> (the pass length: 4 to 10 s for once, 8 to 15 s for loop, including the hold)
- **Resting frame:** <what the still shows: final state, which labels, which colours>
- **Control:** once | loop | step (once is the default; loop only on request; step only for 4+ narrated phases)

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
4. `python3 scripts/verify_facts.py <dir>/<name>.html --source <outline.json> --slide <N>` passes; every WARN reviewed.
   Re-render. Iterate at least once.

Contract section 8 is the definition of done.

## Example: CI/CD pipeline

```markdown
# Brief: deploy-pipeline

- **Name:** deploy-pipeline
- **Subject:** A commit passes build, test and staging before it reaches production; a failed
  test stops it.
- **Audience / tone:** engineering all-hands; calm, technical, no jokes in the graphic.
- **Archetype:** pipeline
- **Slot:** viewBox `0 0 1680 440`, rendered at 1680 x 440 px on a 1920x1080 stage
  (full-width body above a caption line); text scale = 1.0
- **Min text size:** 20 (labels), 26 (stage names)

## Composition
Five stage boxes 240 x 120, y 140, at x 40, 380, 720, 1060, 1400: commit, build, test, staging,
production. Wires between box centres along y 200. Status chip (64 x 28) above each box at y 96.
Packet: circle r 10 on the wire path.

## Phases
| t (s) | Label | Enters | Highlighted | Flows | Caption |
|---|---|---|---|---|---|
| 0.0 | setup | boxes fade in, stagger 80 ms | - | - | - |
| 1.0 | commit | packet appears at commit | commit | - | "push" |
| 2.0 | build | build chip "ok" | build | packet commit->build | - |
| 3.5 | test | test chip "ok" | test | packet build->test | - |
| 5.0 | staging | staging chip "ok" | staging | packet test->staging | - |
| 6.5 | release | production chip "live" | production | packet staging->production | "released" |
| 8.0 | hold | - | all chips | - | - |

The last 0.4 s of the hold fades everything except the boxes back to the empty state.

- **Cycle:** 8 s
- **Resting frame:** all five boxes, all chips "ok"/"live", production outlined in `--anim-ok`.
- **Control:** once

## Theme
- default tokens; host may override via `--anim-theme-*`.
- Colour roles: `--anim-accent` = stage currently processing, `--anim-ok` = passed,
  `--anim-muted` = idle labels, `--anim-line` = wires.
- **Font hints:** system

## Verification plan
- Seconds: 0 1 2 3.5 5 6.5 8 rest
- 0: boxes entering; 1: packet at commit; 3.5: build chip "ok", packet leaving build for test;
  6.5: packet reaching production; 8: production highlighted, all chips; rest: all chips, no
  packet.
```
