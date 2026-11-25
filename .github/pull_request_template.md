## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## Checklist

- [ ] `.github/scripts/check-pool.sh` passes locally (it runs every check below)
- [ ] Unit tests pass: `python3 -m unittest discover -s tests -v`
- [ ] Script changes: still stdlib only and Python 3.9 compatible
- [ ] Behaviour changes: the matching reference is updated and `CHANGELOG.md` has an `## Unreleased` entry

For a new pool entry (see CONTRIBUTING.md):

- [ ] The story is domain-neutral, with no company, client or personal data
- [ ] The wrapper carries `data-anim-control="once"`, `data-anim-verb`, `data-anim-cycle` and `data-anim-phases`
- [ ] A travelling marker is used only for a named thing that really travels
- [ ] `check_fragment.py --name NAME --rendered-width <viewBox width>` passes
- [ ] `check_look.py --rendered-width <viewBox width> --at-marks --at-pauses` passes
- [ ] I rendered phases with `render-phases.sh` and looked at every PNG
- [ ] `thumb.png` is the `rest` render
- [ ] Row added to `pool/index.yaml` with `name`, `archetype`, `form`, `verb`, `moves`, `domain`, `viewbox`, `cycle`, `phases`, `spec`, `story` and `tags`
- [ ] Row added to the table in `pool/README.md`
- [ ] `check_verbs.py --pool pool/index.yaml` passes (at most a third of entries use a travelling marker)

## Screenshots

<!-- Contact sheet or phase renders for visual changes. -->
