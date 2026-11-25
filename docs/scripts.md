# Running the scripts yourself

The agent runs these scripts during a skill run (see [`SKILL.md`](../SKILL.md) for the order).
You can also run them by hand from the skill folder. Each one prints its options with `--help`.
[`README.md`](../README.md#requirements) lists what each needs (Python 3.9+, Chrome or
Chromium, and poppler or LibreOffice for some).

The examples use a fragment named `deploy` in `anim/deploy/`. A *fragment* is one HTML file
with a `<style>` and one inline `<svg>`. The *gate* is the class that starts the animation when
the slide is shown (`.visible` by default, `section.present` in reveal.js).

```bash
# outline a deck with archetype suggestions per slide
python3 scripts/extract_slides.py deck.pptx -o anim/outline.json

# spec -> skeleton fragment
python3 scripts/scaffold_from_spec.py anim/deploy/spec.yaml -o anim/deploy/deploy.html

# contract checks (prefixes, tokens, gating, text size at rendered width)
python3 scripts/check_fragment.py anim/deploy/deploy.html --name deploy --rendered-width 1200 --stage-width 1920

# rendered look checks at rest and at every phase mark (needs Chrome)
python3 scripts/check_look.py anim/deploy/deploy.html --rendered-width 1200 --at-marks

# trace every label and number to the source slide
python3 scripts/verify_facts.py anim/deploy/deploy.html --source anim/outline.json --slide 4 --spec anim/deploy/spec.yaml

# phase frames at 1.5 s, 4 s, 7 s, 10 s plus the resting frame, and a contact sheet (temp dir)
scripts/render-phases.sh anim/deploy 1200 600 1.5 4 7 10 rest

# resting frame of the finished host page (what PDF export shows)
scripts/render-phases.sh --page deck.html 1920 1080 rest

# inline into a deck: markup goes between <!-- anim:NAME:start --> / <!-- anim:NAME:end -->,
# style into the head between <!-- anim-style:NAME:start --> / <!-- anim-style:NAME:end -->;
# re-runs replace both blocks, --dry-run prints a summary without writing
python3 scripts/integrate_fragment.py deck.html anim/deploy/deploy.html --name deploy \
  --anchor '<section id="release">' --gate section.present --backup

# PDF, one slide per landscape page, every label checked (needs poppler)
python3 scripts/export_pdf.py deck.html --paper a4
```
