## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## Checklist

- [ ] `.github/scripts/check-pool.sh` passes locally
- [ ] Script changes: still stdlib only and Python 3.9 compatible

For a new pool entry (see CONTRIBUTING.md):

- [ ] The story is domain-neutral, with no company, client or personal data
- [ ] `check_fragment.py --name NAME --rendered-width <viewBox width>` passes
- [ ] I rendered phases with `render-phases.sh` and looked at every PNG
- [ ] `thumb.png` is the `rest` render
- [ ] Rows added to `pool/index.yaml` and the table in `pool/README.md`

## Screenshots

<!-- Contact sheet or phase renders for visual changes. -->
