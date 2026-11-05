# Pool

Finished fragments that satisfy `references/fragment-contract.md`, at least one per archetype.
The agent checks here before building from scratch (SKILL.md, step 1b): a close match is
adapted (relabel, re-time, retheme), anything else still serves as the quality bar for density,
timing and legibility. `index.yaml` lists every entry with its archetype, size, cycle, story and
tags.

Each folder is `pool/<name>/`: the fragment `<name>.html`, `thumb.png` (its resting frame) and,
where the fragment came from the scaffolder, `spec.yaml`. Most fragments were polished by hand
after scaffolding, so the spec reproduces the structure and timing, not every detail.

| | Name | Archetype | viewBox | Cycle | Story |
|---|---|---|---|---|---|
| ![](deploy-pipeline/thumb.png) | `deploy-pipeline` | pipeline | 1680×440 | 12 s | A commit becomes a canary that earns 100 % of traffic, with auto-rollback watching |
| ![](service-deps/thumb.png) | `service-deps` | graph | 1680×600 | 14 s | A provider outage stays contained to Payments |
| ![](db-failover/thumb.png) | `db-failover` | graph | 1000×560 | 14 s | The primary database fails, the replica is promoted, on-call approves, traffic is rerouted |
| ![](roadmap/thumb.png) | `roadmap` | timeline | 1680×440 | 12 s | Three milestones shipped, mobile in progress, v2 next |
| ![](job-states/thumb.png) | `job-states` | states | 1200×600 | 12 s | A job fails, retries after a backoff and succeeds on the second attempt |
| ![](cache-compare/thumb.png) | `cache-compare` | compare | 1680×600 | 12 s | A cache turns repeated 180 ms reads into 8 ms hits |
| ![](rag-stack/thumb.png) | `rag-stack` | layers | 1200×640 | 13 s | One question goes down a RAG stack and returns as a cited answer |
| ![](cloud-spend/thumb.png) | `cloud-spend` | chart | 1680×600 | 12 s | Spend climbs past budget until autoscaling brings it back under |
| ![](latency-trace/thumb.png) | `latency-trace` | chart | 800×500 | 14 s | A deploy spikes p99 latency over the SLO, a rollback brings it back (seamless scrolling strip chart) |

All are `data-anim-control="loop"` (CSS only, no script). Without a `.visible` ancestor, and
under `prefers-reduced-motion`, each shows its resting frame: the finished state of the story.

## Preview

`render-phases.sh` expects a folder named after the fragment, which every pool entry already is:

```sh
cp -R pool/db-failover /tmp/anim/
scripts/render-phases.sh /tmp/anim/db-failover 1000 560 1.5 4 7 10 rest
```

Then open every `phase-*.png` and look at it. The generated `preview-*.html` files are paused
stills; for real motion drop the fragment into a page with a `.visible` ancestor (or use
`scripts/snippets/observer.html`) and open that in a browser.

## Scaffold from a spec

```sh
python3 scripts/scaffold_from_spec.py pool/deploy-pipeline/spec.yaml -o /tmp/anim/my-pipeline/my-pipeline.html
```

Rename `name:` in the spec first when you adapt it, so prefixes stay unique within the deck.

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

Fills mixed from `--anim-bg` (label plates, tinted tags) assume it matches the slide
background; if `--anim-theme-bg` differs they show as faint boxes.

## Private pools

Fragments with work- or client-specific content do not belong here. Keep them in a folder of
your own with the same layout (`<name>/<name>.html`, optional `index.yaml`) and point
`ANIM_POOL` at it; the agent searches it after this pool.

## Contributing

A new entry needs: a domain-neutral story, a clean `check_fragment.py` run at the viewBox width,
phase renders you have looked at, `thumb.png` from the `rest` render, and a row in `index.yaml`
and in the table above.
