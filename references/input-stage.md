# Input stage

From a user's existing deck or documentation to a short list of illustration briefs. Output of
this stage: one folder per illustration with a spec and a brief, ready for parallel building.

```
source (pptx / html / md / mermaid)
  -> outline.json            scripts/extract_slides.py (pptx / html / md)
  -> triage                  which slides get an illustration
  -> spec.yaml per pick      references/spec-format.md
  -> brief.md per pick       references/brief-template.md
  -> <name>.html per pick    one builder each (subagent or sequential)
```

## 1. Inputs

| Input | How to read it |
|---|---|
| `.pptx` | `python3 scripts/extract_slides.py deck.pptx -o anim/outline.json`. Text, bullets, notes and image counts per slide, plus a suggested archetype. An image count that differs from the pictures in the render points at pictures on the slide layout (a cover photo on the layout). Slide images are not interpreted: run `scripts/render_deck.py deck.pptx -o anim/render`, read the `sheet-NN.png` contact sheets for triage, and open `full/p-NN.png` (`--pages`) only for the candidates. A chart, graph or diagram picture is the slide's core content and must be redrawn (from its data, with credit) in the fragment, not dropped; an illustration that labels a column, lane, category or actor is kept (embedded beside the fragment or redrawn as a glyph); if it cannot be read, ask for the source. The HTML deck to integrate into comes from a deck skill (see "Deck first" below); the pptx stays the triage source. |
| HTML deck | `python3 scripts/extract_slides.py deck.html -o anim/outline.json`. Same JSON; slides are the deck's section elements. The stage is 1920x1080 unless you pass `--stage W H`. Measure slots in the real deck later ([layouts.md](layouts.md)). |
| Markdown (`.md`, `.markdown`) | `python3 scripts/extract_slides.py doc.md -o anim/outline.json`. Same JSON; a slide is each `---`-separated part when the file uses rules, otherwise each `#`. remark decks: `???` becomes `notes`; `.class[...]`, `class:`/`layout:`/`background-*:` lines and `--` are stripped; `layout: true`/`exclude: true` slides are skipped; paragraphs and later headings become bullets. The HTML deck to integrate into comes from a deck skill first (see "Deck first" below); only when none is installed, run `scripts/md_to_deck.py deck.md -o deck.html` as a fallback host and tell the user it is not a designed deck. Each `#` / `##` section. HTML comments become `notes`; mermaid fences go to `mermaid`. Each section that describes a process, a set of dependencies, a sequence of dates or a before/after is a candidate. Numbered lists and tables are strong signals. |
| Plain docs (other formats) | No extractor. Read the file and apply the same signals. |
| Mermaid blocks | Map directly with the tables in [spec-format.md](spec-format.md) "Mermaid mapping". One block = one candidate. |
| Pasted text / a single slide | Skip triage; go to section 4. |

A `.pptx` is not edited in place. The target is an HTML deck: convert it with a deck skill
first (or in parallel), then integrate fragments into that HTML.

### Deck first

Two jobs, two skills. The deck skill owns the deck: layout, typography, slide design, the
brand. anim-slides owns the animated figures, which take the deck's colours and fonts under
the match look (`scripts/host_theme.py` on the deck the skill produced). So a source that is
not an HTML deck yet goes to a deck skill before triage, in this order: the user's own or
organisation's deck skill; `frontend-slides` when installed (pick the aesthetic preview closest
to the source's brand unless the user wants a new look); only when neither exists,
`scripts/md_to_deck.py` as a fallback. Its output is a plain host for integration (full-width
title, the body as bullets, images as they come), not a design; say so to the user in one
sentence, because the deck will read like a document until a deck skill or a designer styles
it. Converting a pptx to Markdown and then to `md_to_deck.py` throws away the pptx's own
layout; keep the pptx as the source for `extract_slides.py` and `render_deck.py` either way.

When the deck skill builds the HTML deck, ask it (or do it right after) to wrap each candidate
slide's body in a fixed-size slot between markers, with the id and marker names `md_to_deck.py`
uses (there the slot is an empty sibling of the marked body; here it holds the body):

```html
<!-- s4-body --><div id="s4-slot" style="width:1680px;height:610px">...</div><!-- /s4-body -->
```

`measure_slot.py deck.html --slide 4 --selector '#s4-slot'` then measures exactly (on an
absolutely positioned layout, measuring without `--selector` returned junk), and
`integrate_fragment.py --anchor '<!-- s4-body -->' --replace-until '<!-- /s4-body -->'`
replaces the body cleanly. The deck skill's own web-font link (Google Fonts, Fontshare) is the
deck's load, not one anim-slides adds; `bundle_deck.py --fetch` inlines it at hand-over.

## 2. Outline JSON

`extract_slides.py` emits:

```json
{
  "source": "deck.pptx",
  "stage": [1920, 1080],
  "slides": [
    {
      "index": 3,
      "title": "Release process",
      "bullets": ["Tag a commit on main", "CI builds and tests", "Deploy to staging", "Promote to production"],
      "notes": "Speaker: stress that QA signs off on staging.",
      "text": "Release process Tag a commit on main CI builds and tests ...",
      "has_image": true,
      "image_count": 1,
      "builds": 4,
      "suggested_archetype": "pipeline",
      "confidence": 0.6,
      "reason": "cues: arrows, numbered steps"
    }
  ],
  "builds": 4
}
```

| Field | Meaning |
|---|---|
| `source` | Basename of the input file (`deck.pptx`, not the path). |
| `stage` | Slide size in px: `--stage W H` when passed; otherwise pptx slide size scaled to 1920 wide, and `[1920, 1080]` for HTML and Markdown. Feeds `--min-text` scaling ([layouts.md](layouts.md)). |
| `index` | 1-based slide number as the presenter sees it. |
| `title` | Title placeholder text, or the first heading; `""` if none. |
| `bullets` | Body paragraphs in order, one string per bullet, indentation flattened. |
| `notes` | Speaker notes, `""` if none. Often states the real point of the slide. |
| `text` | All visible text concatenated, for searching. |
| `has_image`, `image_count` | Pictures on the slide (screenshots, diagrams, photos). |
| `tables` | pptx only, when present: each table as a list of rows (lists of cell strings). A two-column table suggests `compare`. |
| `connectors` | pptx only: count of connector lines and arrow shapes. Counts as a pipeline cue, or graph when they branch. |
| `title_guessed` | `true` when there was no title placeholder and the title came from the largest-font box or first short paragraph. |
| `aspect` | Top level: `"16:9"` or `"4:3"`. |
| `builds` | Per slide (always present, 0 when none) and as a deck total at the top level: click builds the source already has. pptx: click-triggered effects in the slide's animation timeline (`p:cTn nodeType="clickEffect"`). HTML: elements with class `fragment` (reveal.js), `data-fragment-index`, `build`/`build-item`, `substep` (impress.js), and `.step` nested inside a slide. Markdown: remark `--` incremental separators. A total above 0 is the one case where `step` is mentioned to the user (below); the default stays `once`. |
| `mermaid` | Markdown only, and only when present: a list of strings, the body of each mermaid fence in the section. A recognised diagram type sets the suggestion with confidence 0.9. |
| `suggested_archetype` | One of the seven archetypes or `null` (= keep as text). A heuristic. |
| `confidence` | 0 to 1. Below 0.4 treat as a guess. |
| `reason` | Short human-readable signal that produced the suggestion. |

The suggestion is a starting point. The model decides, using the rules below.

## 3. Triage

Read every slide's `title`, `bullets` and `notes`. Mark each slide **illustrate**, **maybe** or
**text**.

Illustrate when the content is:
- a process or procedure (ordered steps, "then", arrows) -> `pipeline` / `states`
- dependencies or an architecture (calls, uses, components and connections) -> `graph` / `layers`
- a timeline or roadmap (dates, quarters, versions) -> `timeline`
- a comparison (before/after, A vs B, two columns) -> `compare`
- data over time (a trend, an incident, a metric) -> `chart`
- a screenshot of a diagram that the speaker walks through step by step

Keep as text:
- quotes, testimonials, a single statement or key message
- agenda, section dividers, title and thank-you slides, contact slides
- dense legal, compliance or definition text that must be read verbatim
- lists of unrelated items (no order, no relation between them)
- slides whose image is a photo or a product screenshot meant to be looked at

Budget:
- 3 to 8 illustrations per 30 slides is normal. One per section is a good rhythm.
- On a short deck (under about 15 slides) the budget is a floor, not a cap: every slide whose
  content is a process, a structure, a timeline, a comparison or a data series gets one. A
  10-slide deck with 3 animated slides is the usual reason a user says "I see almost no change".
- Animating every slide is a mistake: motion stops meaning "look here".
- Never two animated slides in a row unless they are the same story split in two.
- Prefer the slides the speaker spends longest on (long notes, many bullets, a diagram image).
- Rank by: strength of signal x speaker time x how much a still fails to explain it. Take the
  top of the list up to the budget; mark the rest **maybe** and show them to the user.

Write the triage to `anim/triage.md` before building, every slide on its own row, and keep it
with the work folder. The header records the two per-deck choices (next sections):

```markdown
Look: match (branded course deck)
Control: step (source builds by click: outline.json builds = 14)
```

| Slide | Title | Decision | Archetype | Replaces | Why |
|---|---|---|---|---|---|
| 3 | Release process | illustrate | pipeline | the four step cards | 4 ordered steps, speaker stresses QA gate |
| 7 | Our values | text | - | - | single statement |

A **text** row needs a reason from the "keep as text" list above; a row without one is a
silent skip and a defect. "Replaces" names the element on the slide that goes away (cards,
pills, a bullet column, an HTML diagram). A fragment that adds motion over the slide's existing
drawing and leaves the boxes in place replaces nothing; it is allowed only with a reason in
this column.

Unless the user asked for silent operation, wait for a yes / edits on this table. It is the
cheapest point to correct course.

### Look: match or lean

Settle this once per deck, right after triage, before any fragment is built:

- **match** (default for branded, corporate and course decks): fragments take the host's
  palette and fonts. `python3 scripts/host_theme.py deck.html --mode match -o anim/host-theme.css`
  reads the deck's CSS variables and most used colours and writes the `--anim-theme-*` block;
  check its table against a slide and once against the deck's own variables (muted text,
  secondary background, accent glow): where the derivation picked a computed mix instead of
  the deck's variable, correct the block by hand. Then `--apply` it to the deck head
  (markers, idempotent).
- **lean** (talks, pitches, decks with no brand rules): fragments keep the lean palette and the
  animated slides get a dark ground. `--mode lean` writes a `.anim-lean` block; add that class
  to each slide that carries a fragment.

Only colours and fonts differ between the two. The shape rules in [style.md](style.md) hold in
both: rings and labels on lines, hairline brackets, one lit accent, space. A match theme never
licenses filled cards or pills because the deck has them.

Build the first fragment, render it under both (`render-phases.sh --theme anim/host-theme.css`
and `--theme anim/lean-theme.css`), and show the two stills to the user with one sentence each.
If the user named a look already, skip the question and note the choice in `BRIEF.md`.

### Control: once or step

One control per deck. The default is **once**: each slide's figure plays one calm pass when
the slide appears and rests. It is not a question to put to the user; `step` (the entrance
draws on, then each click lands the next phase; clicks past the last phase go to the next
slide) is used only when the user asks for click-through.

- Do not recommend step unprompted. When `outline.json` reports `builds` above 0 (reveal.js
  `.fragment`, PowerPoint click animations, impress.js substeps, the deck's own keyboard build
  steps) the presenter is used to clicking through slides: mention it in one line in the same
  message as the look ("your deck builds by click; the figures can do the same (step), say so
  if you want it") and carry on with once unless they do.
- A step deck is presented with the keyboard or a clicker. Step listens to keys only; a deck
  that also navigates by wheel or swipe (frontend-slides does) skips the phases on a scroll.
- The phases of a step fragment are the narrated phases of the brief, 3 to 5 per slide; their
  marks go on the wrapper as `data-anim-phases`.
- Step costs nothing extra in the fragment: the file is the same as under `once`.
  `integrate_fragment.py --control step` sets the wrapper and puts the small step-host snippet
  in the deck head; the click rides on the deck's own navigation (the snippet takes a key only
  while a phase remains, otherwise the deck gets it). Switching later is a re-run with the
  other `--control`.
- One mode per deck, so the presenter always knows what a click does. A slide that differs
  needs a reason in its triage row. `loop` is not part of this question; it is only for a
  kiosk, gallery or hero on request.
- If the user named a control already, skip the question. Record the choice in the triage
  header, in `BRIEF.md` and in each brief's Control field.

## 4. Slide -> spec -> brief

For each chosen slide:

1. **Pick the archetype** with the table in [archetypes.md](archetypes.md). Override the
   extractor's suggestion when the content says otherwise.
2. **Extract nodes** from bullets in order. Reuse the slide's own words as labels; shorten to
   <= 24 chars by dropping articles and verbs of saying, never by inventing new terms. Move
   detail (durations, owners, counts) to `sub`.
3. **Extract edges** from verbs: "then" / "next" -> `flow`; "needs" / "depends on" / "calls" ->
   `depends`; "sends" / "notifies" / "on failure" -> `event`; "reads" / "writes" -> `data`.
4. **Phases** from the speaker notes when they narrate an order; otherwise derive them
   ([spec-format.md](spec-format.md) "Deriving phases"). Notes sentences become `note`s.
5. **Name** the fragment from the slide title: `Release process` -> `release-process`
   (<= 24 chars, unique in the deck).
6. **Measure the slot** in the HTML deck and set `size` to its aspect ratio
   ([layouts.md](layouts.md)). The slide's bullets usually move to a caption or speaker notes;
   the fragment replaces the bullet block or the image.
7. **Write the brief** from [brief-template.md](brief-template.md): composition from the
   archetype recipe, phases table copied from the spec, verification seconds = each phase `t`
   plus `rest`.

Ask the user only when the answer changes the drawing:
- order is unclear (bullets could be parallel or sequential)
- direction is unclear ("A and B integrate" - who calls whom?)
- grouping is unclear (which items belong together)
- the slide has more than ~12 items: which to keep, or split into two illustrations?
- the image on the slide is the real content and cannot be read

Otherwise state the assumption in the brief ("Assumed steps are sequential") and continue.
Batch all questions for all slides into one message.

## 5. Handoff

Layout next to the deck:

```
anim/
  outline.json              (from extract_slides.py)
  triage.md                 Look and Control header, one row per slide
  BRIEF.md                  shared fields: stage, look, control, theme tokens, fonts, gate, min text
  release-process/
    spec.yaml
    brief.md
    release-process.html    built by the subagent
  data-deps/
    spec.yaml
    brief.md
    data-deps.html
```

- The main thread writes `outline.json`, the triage table, every `spec.yaml` and `brief.md`,
  and the shared `BRIEF.md`. Specs are cheap; write them all before building any fragment.
- Then build the illustrations. With a harness that runs parallel subagents, launch **one
  subagent per illustration, all in one message**; otherwise build them one after another from
  the same briefs. Each builder is given: its folder,
  `BRIEF.md`, the contract, and the instruction to run `scaffold_from_spec.py`, refine,
  run `check_fragment.py` and `render-phases.sh`, look at every PNG, and report path, viewBox,
  cycle, phase seconds and anything unverified.
- Builders write only inside their own folder, scratch files included (a shared scratch
  directory lets one builder overwrite another's helper scripts). They never touch the deck.
- Builders that run `soffice` in parallel each need their own profile:
  `soffice -env:UserInstallation=file:///tmp/lo-<name> --headless --convert-to pdf ...`;
  with a shared profile the second call exits silently without output.
- Speaker notes can carry structure the slide lacks (who proposes and who decides, which step
  matters). Use it for groups and emphasis, and cite it in the spec's header comment.
- A caller's brief that already names the slides counts as approval of the triage table.
- Integration (`integrate_fragment.py`, one call per fragment) and the final in-browser check
  stay in the main thread, sequentially, because they edit the same deck file.
