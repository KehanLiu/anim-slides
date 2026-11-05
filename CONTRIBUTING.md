# Contributing

Thanks for helping. Bug reports, pool entries and "show your deck" posts are all welcome; use
the issue templates. Scripts stay stdlib only and run on Python 3.9+.

## Run the checks locally

```sh
.github/scripts/check-pool.sh            # what CI runs: checker, scaffolder, gallery, py_compile
python3 scripts/build_gallery.py -o /tmp/gallery && open /tmp/gallery/index.html
```

`check-pool.sh` takes an optional pool folder, so it also checks a private pool.

## Add a pool entry

A pool entry is an example other people adapt, so it has to be generic and clean.

1. **Story.** Domain-neutral: no company, client, product or personal names, no real data.
   Software and non-software domains are both welcome (biology, finance, logistics, teaching).
2. **Folder.** `pool/<name>/<name>.html`, every class, id and keyframe prefixed with `<name>`,
   `data-anim-control="loop"` (CSS only). Add `spec.yaml` if it came from the scaffolder.
3. **Checker.** It must pass at its viewBox width:
   `python3 scripts/check_fragment.py pool/<name>/<name>.html --name <name> --rendered-width <W>`
4. **Look at it.** `cp -R pool/<name> /tmp/anim/ && scripts/render-phases.sh /tmp/anim/<name> W H 1.5 4 7 10 rest`,
   then open every `phase-*.png`. Labels must not overlap or clip, and the resting frame must
   tell the whole story.
5. **Thumbnail.** Copy the `rest` render to `pool/<name>/thumb.png`.
6. **Index.** Add a row to `pool/index.yaml` (name, archetype, domain, viewbox, cycle, spec,
   story, tags, and technique if it uses a trick worth naming) and to the table in
   `pool/README.md`.
7. **Gallery.** Run `build_gallery.py`; it fails if your prefixes collide with another entry.

Open the PR with the contact sheet or a few phase PNGs in the description.

## Changes to the skill

Keep `SKILL.md` short; detail belongs in `references/`. When a script's behaviour changes,
update the matching reference and add a line under "Unreleased" in `CHANGELOG.md`.
