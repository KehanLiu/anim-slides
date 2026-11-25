# Contributing

Thanks for helping. Bug reports, pool entries and "show your deck" posts are all welcome; use
the issue templates. Everything an agent runs in `scripts/` stays stdlib only and runs on
Python 3.9+. The one exception is a maintainer script outside `scripts/`:
`.github/scripts/build_hero.py`, which rebuilds the README GIF and needs Pillow.

## Run the checks locally

```sh
.github/scripts/check-pool.sh            # what CI runs
python3 scripts/build_gallery.py -o /tmp/gallery && open /tmp/gallery/index.html
```

`check-pool.sh` runs seven steps:

1. `check_fragment.py` on every pool fragment at its viewBox width.
2. `scaffold_from_spec.py` on every `pool/*/spec.yaml`, into a temp folder.
3. `build_gallery.py` into a temp folder.
4. `check_look.py --at-marks --at-pauses` on every pool fragment, rendered in headless Chrome.
5. `check_verbs.py --pool`: every entry names a verb, and at most a third use a travelling
   marker.
6. `py_compile` on `scripts/*.py`.
7. The unit tests in `tests/`.

Steps 4 and 7 need Chrome or Chromium. Without it, step 4 is skipped with a notice and the
rendered tests in step 7 skip themselves. Set `CHROME=/path/to/chrome` to point at one.
`check-pool.sh` takes an optional pool folder, so it also checks a private pool.

To run the unit tests alone, or one test file:

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_gallery -v
```

## Add a pool entry

A pool entry is an example other people adapt, so it has to be generic and clean.
[`pool/README.md`](pool/README.md) is the authority on what an entry contains; the steps
below are the short form.

1. **Story.** Domain-neutral: no company, client, product or personal names, no real data.
   Mark illustrative numbers as such. All fields are welcome (biology, finance, civics, earth
   science, teaching, software).
2. **Verb.** Pick the one motion verb that carries the claim, from
   [`references/motion-verbs.md`](references/motion-verbs.md). Use a travelling marker (verb
   `travel`, the trip of a `cycle`, or the `packet-hop` move) only for a named thing that
   really travels. At most a third of the pool may use one, so check the current share
   before you add another.
3. **Folder.** `pool/<name>/<name>.html`, every class, id and keyframe prefixed with `<name>`,
   CSS only. The wrapper carries `data-anim-control="once"`, `data-anim-verb`,
   `data-anim-cycle` and `data-anim-phases` (stop marks in seconds, the last one the finished
   figure). Add `spec.yaml` if it came from the scaffolder.
4. **Checker.** It must pass at its viewBox width:
   `python3 scripts/check_fragment.py pool/<name>/<name>.html --name <name> --rendered-width <W>`
5. **Look check.** It must also pass the rendered look lint (needs Chrome):
   `python3 scripts/check_look.py pool/<name>/<name>.html --rendered-width <W> --at-marks --at-pauses`
6. **Look at it.** Render the phases at the viewBox size (`W` and `H`):
   `scripts/render-phases.sh pool/<name> W H 1.5 4 7 10 rest`.
   The PNGs go to a temp folder that the script prints. Open every `phase-*.png`. Labels
   must not overlap or clip, and the resting frame must tell the whole story.
7. **Thumbnail.** Copy the `rest` render to `pool/<name>/thumb.png`.
8. **Index.** Add a row to `pool/index.yaml` with `name`, `archetype`, `form`, `verb`,
   `moves`, `domain`, `viewbox`, `cycle`, `phases`, `spec`, `story` and `tags`, plus
   `technique` if it uses a trick worth naming. `phases` repeats the wrapper's
   `data-anim-phases`. Add a row to the table in `pool/README.md` too.
9. **Pool checks.** Run `python3 scripts/check_verbs.py --pool pool/index.yaml` and
   `build_gallery.py`. The gallery build fails if your prefixes collide with another entry.
   Then run `.github/scripts/check-pool.sh` once more.

Open the PR with the contact sheet or a few phase PNGs in the description.

## Changes to the skill

Keep `SKILL.md` short; detail belongs in `references/`. When a script's behaviour changes,
update the matching reference, and add or extend an `## Unreleased` section at the top of
`CHANGELOG.md`.

## Rebuild the README GIF

`docs/media/hero.gif` is built by a maintainer script. It needs headless Chrome and Pillow
(`pip install pillow`). Run it from the repo root:

```sh
python3 .github/scripts/build_hero.py --gif /tmp/hero.gif  # try it somewhere else first
python3 .github/scripts/build_hero.py                      # then overwrite docs/media/hero.gif
```

By default the before slide is `examples/first-slide/source.html` and the after fragment is
`pool/parcel-route/parcel-route.html`. Pass `--png PATH` to also write a still of the after
slide. Run it with `--help` for the other options.
