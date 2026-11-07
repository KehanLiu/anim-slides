# Accuracy

A fragment adds motion, not facts. Everything it says must already be on the slide (or in the
document) it illustrates. `scripts/verify_facts.py` checks the mechanical part; a reviewer and
the rendered slide check the rest.

## Rules
0. **The slide's pictures are content until proven otherwise.** A chart or figure is redrawn
   from its data. An illustration that distinguishes items (one bird per open-access model,
   one figure per actor, an organ the slide is about) is kept: embed the source image beside
   the fragment when the licence allows (credit it), or redraw it as a simple SVG glyph in the
   same colours. Drop only backgrounds, logos and unrelated photos, and say what you dropped.
   The figure's form is content too: a staircase is redrawn as a staircase, not re-plotted as
   a line chart; a table stays rows; the slide's reading order stays. Changing the form is an
   interpretation the author did not make.
1. **Numbers come from the source.** Every value, date, percentage, unit and axis value is on the
   slide, in its notes or tables, or in a figure you have read. If a value is a placeholder, the
   fragment itself says so in visible text ("illustrative values"); a comment is not enough.
   A derived number (22x from 180 ms / 8 ms) is allowed only when the derivation is trivial and
   the slide's own numbers produce it.
2. **Labels use the source's words.** Shorten by dropping words, never by paraphrasing into
   what the slide "means": the slide says "President approves", so the chip says "approved",
   not "signed into law"; "arrives in the warehouse" does not become "shipped to the customer".
3. **Slots must not invent a claim.** A why / reason / cause chip, a legend or a category label
   asserts a relation. Put text there only when the source states that relation ("because",
   "due to", "so"). A state that follows an action is not its reason.
4. **One slide unless stated.** Facts from neighbouring slides or earlier builds of the same
   figure are allowed only when the spec says the fragment spans those slides; cite them in the
   spec header.
5. **Arrows and directions follow the slide.** Who sends to whom, what causes what, which way a
   curve shifts: copy the slide's arrows. If the slide has none, state the assumption in the
   brief and keep the drawing neutral (no arrowheads).
6. **Charts are redrawn from their data at exact scale.** Read the values off the figure, write
   them into the spec's header comment ("E0 (10 B$, 8%)"), plot them on a linear axis with
   evenly spaced ticks. No smoothing, no extra points, no invented trend between known points.
7. **Unreadable figure: ask, don't guess.** If a value, label or arrow on a picture cannot be
   read at the rendered resolution, ask the user for the source data or a better image, or leave
   that element out. Never fill a gap with a plausible number.

## Running the gate
```
python3 <skill-dir>/scripts/verify_facts.py anim/<name>/<name>.html \
    --source anim/outline.json --slide 23 [--slides 22-24 | --deck-wide] \
    --spec anim/<name>/spec.yaml [--allow anim/<name>/allow.txt] [--strict]
```
`--source` may also be a text or Markdown file (read whole), and `--source-text` takes a string.
`--slide` names the primary slide(s); `--slides` and `--deck-wide` only add context. The spec's
leading comment block and `--allow` (one term per line) hold what you transcribed from figures.

Reading the output (same style as `check_fragment.py`; exit 1 on any FAIL):

| Line | Meaning | Action |
|---|---|---|
| `FAIL numbers` | a number on no slide, spec header or allow list | fix it, or transcribe its source into the spec header |
| `WARN spec-only` | found only in the spec header / allow list | compare with the rendered slide once |
| `WARN cross-slide` | found only on a context slide | fine if the spec says the fragment spans it; else remove |
| `WARN derived` | computed from two source numbers (shown) | check the derivation is what the slide implies |
| `WARN words` / `names` | label words or names absent from the source | reword to the slide's terms, or justify in the brief |
| `WARN splice` | label joins words that never share a source bullet | check the combination is the slide's claim |
| `WARN causal-slot` | text in a why/reason slot, source states no cause | move it out of the slot or reword |
| `OK axis` / `indices` | tick labels on a linear grid, 1..k step badges | none |

Every WARN needs a decision. `--strict` turns the label-level WARNs into FAILs. Use it before a
final review, not as the build gate: true labels with paraphrased words will fail too.
The gate cannot read pictures and does not check arrow directions or plotted positions: the
rendered PNG next to the rendered source slide is still the final check.

## Checklist for a brief
```
- Every number is on slide N (or in the spec header, transcribed from its figure).
- Labels use the slide's own words; shorten, never paraphrase or explain.
- Why/reason/legend slots only hold relations the slide states.
- Arrows, directions and order exactly as on the slide; no facts from other slides.
- Charts redrawn from their data at exact scale; unreadable figure = ask, not guess.
- verify_facts.py: 0 FAIL, each WARN fixed or justified in the report.
```
