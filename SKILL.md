---
name: anim-slides
description: Turn boring slides into animation-rich HTML. Builds self-contained animated SVG illustrations (CSS keyframes, optional click-driven step mode) that replace text blocks and screenshots in any HTML slide deck, and creates them directly from documentation of processes, dependencies, timelines or architectures. Use when the user wants to animate a PPT/PPTX or HTML deck, says "improve the slides", "add more animations", "make this deck less boring" or "animate slide 4", draw a process/pipeline/dependency graph/timeline/comparison as an animation, or turn a Mermaid diagram or a written procedure into an animated illustration. Not for generating a whole deck from scratch (use a slides skill first) and not for video.
license: MIT
compatibility: Python 3.9+ for the scripts; a Chrome or Chromium binary for phase rendering; any harness that can run shell commands and view PNG files.
metadata:
  author: Kehan Liu
  version: "0.10.0"
  repository: https://github.com/KehanLiu/anim-slides
---

# anim-slides

Animated SVG illustrations for slide decks, from existing slides or from documentation.
Output is always a **fragment**: one HTML file with a `<style>` and one `<svg>`, no scripts,
no external files, themed by CSS variables, that drops into any deck.
`references/fragment-contract.md` is the contract. Read it before building anything.

## Core principles
1. **Show, don't tell.** The user decides by looking at a rendered figure, not by reading a
   plan. The first fragment is built and rendered before anything is asked.
2. **Ask once.** Every choice goes into one intake message. After it, nothing else is asked.
3. **Figures replace text, nothing else changes.** "Improve the slides", "make it less boring",
   "add (more) animations" and "animate this deck" mean the same thing to this skill: figures
   replace text blocks and screenshots on the slides that carry a process, structure, timeline,
   comparison or data. The deck's design, wording and order stay.
4. **Deliver by showing.** The hand-over is a before/after review page, not a report.

`<skill-dir>` below is the folder that contains this SKILL.md (Claude Code exposes it as
`$CLAUDE_SKILL_DIR`; elsewhere use the path you loaded this file from). `anim/` is a work folder
next to the user's deck, `anim/<name>/` one per fragment.

## Phase 0: Read the request

| The user says | Source | Mode | What happens |
|---|---|---|---|
| "improve the slides", "make it less boring", "add (more) animations", "animate this deck" | `.pptx`, Markdown, remark, a document | **A: deck first, then animate** | A deck skill builds the HTML deck; then triage and figures. The budget floor applies (`references/input-stage.md`). |
| the same | an HTML deck (reveal.js, impress.js, frontend-slides, any `<section>`/`.slide` deck) | **B: animate in place** | Triage and figures on the existing deck. |
| "animate slide N", "this diagram", "this chart" | any | **C: single slide** | No triage. No intake message, except one look still when the deck has no theme yet. |
| a process, dependency, timeline or architecture in text, or a Mermaid block | docs, README, pasted text | **D: illustrate from docs** | Pick the archetype (`references/archetypes.md`), spec, build; the host is the page or slot the user names. |
| "make the figures play on click", "loop them", "switch to lean" | an already animated deck | **E: re-integrate** | No rebuild: `integrate_fragment.py --control step|once` per fragment, or `host_theme.py --mode lean|match --apply`. Fragments stay as they are. |

**Mode A, deck first.** anim-slides adds figures to an HTML deck; it does not design one. The
deck comes from, in order: (a) the user's own or organisation's deck skill; (b) `frontend-slides`
when installed (pick the aesthetic preview closest to the source's brand unless the user wants
a new look); (c) only when neither exists, `scripts/md_to_deck.py` (a plain host, not a design:
say so in one sentence). The intake message says up front that the HTML deck has to exist first
and what it costs: a deck skill rebuilds the whole deck, and on a 40-slide deck that is the
longest step. It offers the **lighter path**: standalone animated slide pages for the chosen
slides only (one self-contained HTML per slide at 1280x720 or the source stage: title, fragment,
one-line takeaway), for a user who keeps presenting from PowerPoint or wants to see what the
skill does first. Default is the full deck. The `.pptx` stays the source for
`extract_slides.py` and `render_deck.py`; integration and the match look target the deck the
skill produced. Details: `references/input-stage.md` "Deck first".

**Slot markers.** Ask the deck skill (or do it right after it) to give each candidate slide a
fixed-size slot `<div id="sN-slot">` and to put the markers **inside** it, round its content:
`<div id="sN-slot" style="width:..px;height:..px"><!-- sN-body -->...<!-- /sN-body --></div>`.
`measure_slot.py --selector '#sN-slot'` is then exact and
`integrate_fragment.py --anchor '<!-- sN-body -->' --replace-until '<!-- /sN-body -->'`
replaces the content and keeps the sized div. Markers round the div would delete it.

## Phase 1: Show first, ask once

1. **Extract and render.** `python3 <skill-dir>/scripts/extract_slides.py deck.pptx|deck.html|doc.md -o anim/outline.json`
   and `python3 <skill-dir>/scripts/render_deck.py deck -o anim/render`. Look at the
   `sheet-NN.png` contact sheets (12 slides each), not page by page. Both scripts number
   slides the same way, hidden slides included (`render_deck.py` renders them captioned
   "hidden" and lists them on stderr); note hidden slides in the triage. A picture count in `outline.json` that differs from the
   render points at pictures on the slide layout.
2. **Draft the triage** in `anim/triage.md` (`references/input-stage.md` section 3): every slide
   with Slide, Title, Decision, Archetype, Replaces, Why; no silent skips. Budget 3 to 8 per 30
   slides, never two animated slides in a row; "add more animations" reads as the upper end of
   the budget, not beyond it; on a short deck the budget is a floor. Re-render candidates with
   `--pages N,...` and open `full/p-NN.png`: `extract_slides.py` cannot see inside pictures.
3. **Theme.** `python3 <skill-dir>/scripts/host_theme.py deck.html --mode match -o anim/host-theme.css`
   and `--mode lean -o anim/lean-theme.css`. Compare the match block once with the deck's own
   CSS variables (muted text, secondary background, accent); on a deck without variables the
   accent may be picked by usage count, so check it against what the deck actually highlights.
   Correct by hand where needed.
4. **Build the first fragment before asking anything**: the most representative illustrate
   slide, through Phase 2's steps (spec, slot, brief, build, check). Render it integrated into
   its slide at rest under match and under lean (`render-phases.sh --theme FILE ...` or
   `--page` on a scratch copy): two stills. When that slide has two plausible figure readings
   (timeline or pipeline, table or compare), render both readings as stills too.
5. **Send ONE message.** Use the harness's structured-question UI when it has one (Claude Code:
   AskUserQuestion, naming the stills' paths in the question text); otherwise one concise
   message with numbered choices. It carries:
   - the proposal: "N of M slides get a figure", and the triage table;
   - the stills (match and lean; both readings when there are two);
   - **look**: match (default for branded or corporate decks) or lean (talks, pitches);
   - **control**: once, stated in one line; add "your deck builds by click; the figures can do
     the same (step), say so if you want it" only when `outline.json` reports `builds` above 0;
   - Mode A only: the deck-first note and its cost, and the lighter path;
   - **hand-over**: will the file be shared or presented from another machine (then it is
     bundled to one offline file)?

   After this message **nothing else is asked**. If the user is absent or says "just do it",
   take the defaults (full deck, match for branded decks else lean, once, not bundled) and
   record every default taken in a **Decisions** section of `anim/triage.md`, with Look and
   Control in its header. A brief from a caller that already names slides and look counts as
   the answer.

   Ambiguity is not a question: order, direction or grouping the source leaves open becomes a
   stated assumption in the brief. An unreadable figure is traced from the source picture and
   tagged "traced from <source> figure" (`references/accuracy.md`); it is not asked about.

## Phase 2: Build silently

For each remaining illustrate row, the main thread writes spec and brief first (specs are
cheap; write them all before building), then builds.

1. **Spec.** `anim/<name>/spec.yaml` per `references/spec-format.md`: nodes, edges, groups,
   phases with second marks, cycle (4 to 10 s), control from intake. Reuse the source's words.
   Under about 12 nodes; split otherwise.
2. **Pool.** Read `<skill-dir>/pool/index.yaml` (and `$ANIM_POOL/index.yaml` if set). A close
   match (same archetype, similar story) is copied to `anim/<name>/`, renamed and adapted; same
   archetype only: open it as the quality bar. Never ship a pool fragment unchanged.
3. **Slot and brief.** `python3 <skill-dir>/scripts/measure_slot.py deck.html --slide N --selector '#sN-slot'`
   prints the box, a viewBox and the checker flags (without `--selector` an absolutely
   positioned layout returns junk; `references/layouts.md` has the manual way). Fill
   `anim/<name>/brief.md` from `references/brief-template.md`, naming what the fragment replaces.
4. **Build.** `python3 <skill-dir>/scripts/scaffold_from_spec.py anim/<name>/spec.yaml -o anim/<name>/<name>.html --rendered-width <px>`
   covers the plain forms of the seven archetypes: chains, two-row snakes, graphs with lanes,
   line charts, column compares, layer stacks, dot timelines. Triangles, donuts, bars,
   timelines with event text and anything the spec format cannot express are hand-built from
   the spec; do not force the scaffolder, use its output as the timing skeleton. Refine with
   `references/archetypes.md`, `references/motion-rules.md` and `references/style.md`.
   **Phase marks** (`data-anim-phases`): a phase mark is a settled moment between narrated
   steps: nothing visible is mid-motion there. Three to five per slide (six when the slide
   narrates six steps), ascending, the last at the hold start. The scaffolder derives them from
   phase starts; a hand-built fragment sets them by looking at the frames.
   Parallel builders are fine (one subagent per fragment, all in one message), each writing
   only inside `anim/<name>/`, scratch files included; never the deck
   (`references/input-stage.md` section 5 has the builder brief and the `soffice` profile note).
5. **Check by looking.**
   - `python3 <skill-dir>/scripts/check_fragment.py anim/<name>/<name>.html --name <name> --rendered-width <px> --stage-width <host stage width>`.
     Pass `--stage-width`: the text floor defaults to a 1920 stage (18 px; 12 px at 1280).
   - `<skill-dir>/scripts/render-phases.sh anim/<name> <W> <H> <marks...> <pass> rest`, then
     open every PNG. Fix clipping, overlaps, unreadable text, empty panels; iterate at least
     once. The resting frame must read as a complete still (PDF shows only that).
   - `python3 <skill-dir>/scripts/verify_facts.py anim/<name>/<name>.html --source anim/outline.json --slide <N> --spec anim/<name>/spec.yaml`
     (or `--source doc.md`): 0 FAIL, every WARN decided (`references/accuracy.md`).
   Never trust `--virtual-time-budget`, and never trust reading the source instead of the PNG.
6. **Integrate**, in the main thread, one call per fragment:
   `python3 <skill-dir>/scripts/integrate_fragment.py deck.html anim/<name>/<name>.html --name <name> --anchor '<!-- sN-body -->' --replace-until '<!-- /sN-body -->' [--gate 'section.present'] --control once --backup`.
   It hoists the style into the head, inserts the markup between `anim:<name>` markers
   (re-runs replace both), rewrites the gate (`section.present` reveal.js, `.visible` plain
   pages and `md_to_deck.py` decks), adds the print guard and, under `--control step`, the step
   snippet. Plain pages get `scripts/snippets/observer.html`. Apply the theme once:
   `host_theme.py --apply deck.html --from anim/host-theme.css` (lean: the lean file, plus
   `class="anim-lean"` on each animated slide). Keep the working deck lean: read slices round
   the anchor (`grep -n`, `sed -n`), never the whole deck; no inlined fonts or images.
7. **Check the page.** `render-phases.sh --page deck.html --slide N <W> <H> rest` per animated
   slide (never `--no-script` for `rest`: in frontend-slides decks `.visible` both gates and
   shows the slide). The rest render hides a deck's own staggered text (reveal classes keyed
   on the current-slide class): key those reveals also on the deck's active class and add a
   print rule; when the rest render still differs from the running deck, take the final
   screenshot from the running deck. `python3 <skill-dir>/scripts/check_page.py deck.html`
   (paired markers, gated fragments, print guard; a deck skill's font link is the deck's load).
   Open the deck in a real browser once: headless frames never prove smoothness. Audit with
   the checklist at the end of `references/motion-rules.md`.

## Phase 3: Deliver by showing

1. If the file will be shared: `python3 <skill-dir>/scripts/bundle_deck.py deck.html -o deck.bundled.html --fetch`
   (inlines stylesheets, scripts, fonts and images), then `check_page.py deck.bundled.html`
   and one `render-phases.sh --page deck.bundled.html --slide N ... rest`. Do not read the
   bundled file.
2. Render the resting frame of every animated slide of the integrated deck into
   `anim/review/after/` (`render-phases.sh --page deck.html --slide N <W> <H> rest --out anim/review/after/sN`,
   one folder per slide; `review_page.py --help` lists the other names it accepts), and make sure the source renders
   of those slides are in `anim/render/full/` (`render_deck.py --pages`).
3. `python3 <skill-dir>/scripts/review_page.py --deck deck.html --before anim/render/full --after anim/review/after --triage anim/triage.md -o anim/review/index.html`
   (optional `--only animated`, `--previous DIR`, `--title`, `--link-images`). Open it and the
   deck.
4. Send a few lines: N of M slides animated; the review page path; the deck path (the bundled
   one if shared); the two switches for later, one line each:
   `integrate_fragment.py ... --control step` (figures by click) and
   `host_theme.py deck.html --mode lean --apply deck.html` (lean look). The review page is the
   report; no long prose.

## Hard rules
- **Ask once, show first.** One intake message carries the proposal and rendered stills of the
  first fragment; no later questions; defaults taken are recorded in `anim/triage.md`.
- **Deck first.** anim-slides styles fragments, never the deck. A source that is not an HTML
  deck goes through a deck skill (Mode A, announced with its cost and the lighter path);
  `md_to_deck.py` is a last resort, named as such.
- **Keep the slide's visuals.** A chart, graph, table, map, flowchart or scientific figure is
  the slide's core content: redraw it from its data and animate that, never replace it with a
  text summary. An icon or picture that labels a column, lane, category or actor is content
  too: embed it beside the fragment (licence permitting) or redraw it as a glyph. Only a
  background, a logo or an unrelated photo may go; when unsure, keep it and say so.
- **Make a visible change.** A fragment replaces the slide's cards, pills, bullet column or HTML
  diagram. Motion over the existing drawing with the boxes left in place is not an
  illustration; if nothing else is possible, the brief says why.
- **Less.** The slide's own figure in its own form (stairs stay stairs, a table stays rows)
  plus one movement; no invented chart forms, brackets, arrows or storylines; one glowing
  element at most, never a glowing line. The look follows `references/style.md` (no filled
  cards, chips or caption bars; rings and thin lines; one accent; at most two semantic
  colours) under match and lean alike: a host theme changes colours and fonts only.
- **Accurate.** Every number and label traces to the source or is marked illustrative;
  `verify_facts.py --spec` passes before a figure is done (`references/accuracy.md`).
- **Contract.** Prefix every class, id and keyframe with `<name>-`; colours and fonts only via
  `var(--anim-*)` with the contract's fallbacks; animate only under the gate (ungated = the
  finished state); no `<script>`, `<link>`, `<image>`, `@import`, `@font-face` in a fragment;
  text at or above 18 px at rendered size on a 1920 stage (scaled by `--stage-width`), titles
  22 px and up.
- **Plays once.** One pass of 4 to 10 s when the slide becomes current, iteration count 1,
  fill forwards, 100 % keyframe = resting frame, nothing looping or pulsing while the slide is
  up. At most three things moving at once, reduced-motion block present.
- **One control per deck.** `once` unless the user asks for `step`; mention step only when the
  source builds by click. A slide that differs needs a reason in `anim/triage.md`. Step
  listens to keys only: present it with the keyboard or a clicker.
- **No network loads.** None in fragments, no new ones in the deck; loads the deck already has
  stay. Work on a lean deck; bundle only at hand-over when it will be shared.
- **Deliver by showing.** The before/after review page (`review_page.py`) is part of done.

## Files
- `references/fragment-contract.md` — the output contract (shape, prefixes, tokens, gate, resting frame, control variants)
- `references/input-stage.md` — deck first, outline JSON, triage, look and control, slide to spec to brief, handoff
- `references/spec-format.md` — the spec; Mermaid mapping; worked examples
- `references/archetypes.md` — pipeline, graph, timeline, states, compare, layers, chart: composition and motion
- `references/brief-template.md` — the brief every fragment starts from
- `references/layouts.md` — measuring a slot; 16:9 layouts and viewBoxes
- `references/motion-rules.md` — timing, easing, choreography, audit checklist
- `references/style.md` — the visual style and its checklist
- `references/accuracy.md` — accuracy rules and the `verify_facts.py` gate
- `references/lessons.md` — gotchas from real runs
- `scripts/extract_slides.py` — pptx/html/md to outline JSON with archetype suggestions and `builds`
- `scripts/render_deck.py` — contact sheets plus full-size pages for candidates; hidden slides rendered and marked
- `scripts/host_theme.py` — host glue: match (from the deck's CSS) or lean; `--apply` into the deck head
- `scripts/md_to_deck.py` — fallback host when no deck skill is installed; not a designed deck
- `scripts/scaffold_from_spec.py` — spec validation and skeleton fragment for the plain archetype forms
- `scripts/check_fragment.py` — static contract checks
- `scripts/verify_facts.py` — provenance gate against the source slide (`--self-test`)
- `scripts/render-phases.sh` — phase PNGs and contact sheet with headless Chrome; `--page` for a host page
- `scripts/measure_slot.py` — free box of a slide with viewBox and checker flags
- `scripts/integrate_fragment.py` — idempotent inlining, gate rewrite, prefix safety net, `--control once|step`
- `scripts/check_page.py` — page checks: external loads, markers, gating, print guard, step snippet
- `scripts/bundle_deck.py` — one self-contained file for hand-over (`--fetch` for remote assets)
- `scripts/review_page.py` — before/after review page for delivery
- `scripts/snippets/observer.html`, `scripts/snippets/step-host.html` — host helpers (scroll gate; step mode)
- `pool/` — finished, checked fragments with thumbnails and specs; `pool/index.yaml` lists them

## Related skills (use them when your harness has them; none is required)
- A deck skill (the user's own, frontend-slides, reveal.js, Slidev) builds the deck in Mode A.
- A motion-design skill for deeper timing guidance; a pptx skill for sources beyond what
  `extract_slides.py` reads.
