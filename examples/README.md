# Examples

Two reference fragments that satisfy `references/fragment-contract.md`. Use them as a
quality bar for density, timing and legibility, not as templates to copy.

| File | Name | viewBox | Cycle | Demonstrates |
|---|---|---|---|---|
| `db-failover.html` | `db-failover` | `0 0 1000 560` | 14 s | Phases over a service topology: requests reach the primary database, it fails and requests stall, health checks propose promoting the replica, on-call approves, traffic is rerouted to the new primary. Phase changes are opacity swaps on stacked layers, timed by shared 14 s keyframes. |
| `latency-trace.html` | `latency-trace` | `0 0 800 500` | 14 s | A continuous strip chart with events built into the trace: a service's p99 latency scrolls past, a deploy pushes it over a dashed SLO line, an alert fires and a rollback brings it back to baseline, while the version, status and latency readouts change in step. The trace and its markers are drawn twice and shifted by one period, so the loop is seamless. |

Both are `data-anim-control="loop"` (CSS only, no script). Without a `.visible` ancestor, and
under `prefers-reduced-motion`, each shows its resting frame: the finished state of the story.

## Preview

`render-phases.sh` expects a folder named after the fragment:

```sh
mkdir -p /tmp/anim/db-failover && cp examples/db-failover.html /tmp/anim/db-failover/
scripts/render-phases.sh /tmp/anim/db-failover 1000 560 1.5 4 7 10 rest

mkdir -p /tmp/anim/latency-trace && cp examples/latency-trace.html /tmp/anim/latency-trace/
scripts/render-phases.sh /tmp/anim/latency-trace 800 500 1.5 4 7 10 rest
```

Then open every `phase-*.png` and look at it. The generated `preview-*.html` files are paused
stills; for real motion drop the fragment into a page with a `.visible` ancestor (or use
`scripts/snippets/observer.html`) and open that in a browser.

## Retheme

The fragments read only `--anim-*` tokens, which fall back to a neutral dark palette.
Set the `--anim-theme-*` variables once on `:root` (or on a slide) in the host page:

```css
:root {                          /* example: a light theme */
  --anim-theme-bg: #ffffff;       /* must match the slide background: label plates use it */
  --anim-theme-panel: #f2f4f8;
  --anim-theme-line: #c5ccd8;
  --anim-theme-fg: #14181f;
  --anim-theme-muted: #5b6474;
  --anim-theme-accent: #0a6cff;
  --anim-theme-accent-2: #d9480f;
  --anim-theme-ok: #2b8a3e;
  --anim-theme-warn: #e67700;
  --anim-theme-danger: #c92a2a;
  --anim-theme-font: 'Inter', system-ui, sans-serif;
  --anim-theme-mono: 'JetBrains Mono', ui-monospace, monospace;
}
```

In `db-failover`, the small plates behind the line-loading
labels are filled with `--anim-bg` so they mask the lines; if `--anim-theme-bg` does not match
the slide background they show as faint boxes.

## Example specs

`specs/` holds one spec per archetype family, in the format of `references/spec-format.md`.
Each file starts with the scaffold command that turns it into a skeleton fragment; the output
passes `check_fragment.py` as generated and is meant to be refined by hand.

| File | Name | Archetype | Story |
|---|---|---|---|
| `specs/pipeline.yaml` | `deploy-pipeline` | pipeline | Commit, build, test, staging, production, with a rollback edge |
| `specs/dependency-graph.yaml` | `service-deps` | graph | Two service groups, a store, an external provider and an event bus |
| `specs/timeline.yaml` | `roadmap` | timeline | Five product milestones |
| `specs/job-states.yaml` | `job-states` | states | Queued, running, failed, retried, succeeded |
| `specs/load-chart.yaml` | `load-spike` | chart | A load trace crossing a limit, with fault and recovery events |

```sh
python3 scripts/scaffold_from_spec.py examples/specs/pipeline.yaml -o /tmp/anim/deploy-pipeline/deploy-pipeline.html
scripts/render-phases.sh /tmp/anim/deploy-pipeline 1680 440 1 2.5 4 5.5 7 8.5 rest
```
