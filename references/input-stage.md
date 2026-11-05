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
| `.pptx` | `python3 scripts/extract_slides.py deck.pptx -o anim/outline.json`. Text, bullets, notes and image counts per slide, plus a suggested archetype. Slide images are not interpreted: render every candidate slide and look at it. A chart, graph or diagram picture is the slide's core content and must be redrawn (from its data, with credit) in the fragment, not dropped; an illustration that labels a column, lane, category or actor is kept (embedded beside the fragment or redrawn as a glyph); if it cannot be read, ask for the source. |
| HTML deck | `python3 scripts/extract_slides.py deck.html -o anim/outline.json`. Same JSON; slides are the deck's section elements. The stage is 1920x1080 unless you pass `--stage W H`. Measure slots in the real deck later ([layouts.md](layouts.md)). |
| Markdown (`.md`, `.markdown`) | `python3 scripts/extract_slides.py doc.md -o anim/outline.json`. Same JSON; a slide is each `---`-separated part when the file uses rules, otherwise each `#`. remark decks: `???` becomes `notes`; `.class[...]`, `class:`/`layout:`/`background-*:` lines and `--` are stripped; `layout: true`/`exclude: true` slides are skipped; paragraphs and later headings become bullets. To get an HTML deck to integrate into, run `scripts/md_to_deck.py deck.md -o deck.html` first. Each `#` / `##` section. HTML comments become `notes`; mermaid fences go to `mermaid`. Each section that describes a process, a set of dependencies, a sequence of dates or a before/after is a candidate. Numbered lists and tables are strong signals. |
| Plain docs (other formats) | No extractor. Read the file and apply the same signals. |
| Mermaid blocks | Map directly with the tables in [spec-format.md](spec-format.md) "Mermaid mapping". One block = one candidate. |
| Pasted text / a single slide | Skip triage; go to section 4. |

A `.pptx` is not edited in place. The target is an HTML deck: convert it with a slides skill
first (or in parallel), then integrate fragments into that HTML.

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
      "suggested_archetype": "pipeline",
      "confidence": 0.6,
      "reason": "cues: arrows, numbered steps"
    }
  ]
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
- Animating every slide is a mistake: motion stops meaning "look here".
- Never two animated slides in a row unless they are the same story split in two.
- Prefer the slides the speaker spends longest on (long notes, many bullets, a diagram image).
- Rank by: strength of signal x speaker time x how much a still fails to explain it. Take the
  top of the list up to the budget; mark the rest **maybe** and show them to the user.

Present the triage as a table before building:

| Slide | Title | Decision | Archetype | Why |
|---|---|---|---|---|
| 3 | Release process | illustrate | pipeline | 4 ordered steps, speaker stresses QA gate |
| 7 | Our values | text | - | single statement |

Unless the user asked for silent operation, wait for a yes / edits on this table. It is the
cheapest point to correct course.

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
  BRIEF.md                  shared fields: stage, theme tokens, fonts, gate, min text
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
