---
name: anim-slides
description: Turn boring slides into animation-rich HTML, starting from the question each slide's audience must answer (a slide that already answers it ships unchanged; motion only where seeing a change unfold adds understanding). Builds self-contained animated SVG illustrations (CSS keyframes, optional click-driven step mode) that replace text blocks and screenshots in any HTML slide deck, and creates them directly from documentation of processes, dependencies, timelines or architectures. Use when the user wants to animate a PPT/PPTX or HTML deck, says "improve the slides", "add more animations", "make this deck less boring" or "animate slide 4", draw a process/pipeline/dependency graph/timeline/comparison as an animation, or turn a Mermaid diagram or a written procedure into an animated illustration. Not a deck designer; for a whole deck from scratch a deck skill builds the base first (a small built-in base deck is used only when none is installed); not for video.
license: MIT
compatibility: Python 3.9+ and Chrome or Chromium for the scripts; for PowerPoint sources LibreOffice (soffice) and poppler (pdftoppm), which PDF export also needs; a harness that can run shell commands.
metadata:
  author: Kehan Liu
  version: "0.14.0"
  repository: https://github.com/KehanLiu/anim-slides
---

# anim-slides

Animated SVG figures for slide decks, from existing slides or from documentation.
Output is always a **fragment**: one HTML file with a `<style>` and one `<svg>`, no scripts,
no external files, themed by CSS variables, that drops into any deck.
`references/fragment-contract.md` is the contract. Read it before building anything.

## Terms
- **figure**: what the audience sees on the slide, the drawing and its motion.
- **fragment**: the file that carries one figure, one `<style>` plus one inline `<svg>` (`anim/<name>/<name>.html`).
- **slot**: the box on the slide where the figure sits, measured by `measure_slot.py`.
- **pass**, **phase mark**: the figure's one run of motion (4 to 10 s); a phase mark is a settled moment in it between narrated steps (`data-anim-phases`).
- **hold**, **resting frame**: the hold is the end of the pass where nothing moves; the resting frame is what it shows, the finished figure (the 100 % keyframe, all a PDF shows).
- **gate**: the CSS class or selector that starts the pass when the slide is shown (`section.present`, `.visible`); ungated, a fragment shows its resting frame.
- **match**, **lean**: the two looks. Match takes the deck's palette and fonts; lean keeps the skill's quiet palette on a dark ground.
- **once**, **step**: the two controls. Once plays the pass when the slide appears; step advances it one phase per key press.

## Core principles
1. **Question first.** Every slide starts from the one question its audience should be able to
   answer. A slide whose base already answers it ships as it is, at once. Motion is added only
   when you can name what the audience understands better by seeing a change unfold, and that
   insight is then drawn on the slide (Phase 0, "The question").
2. **Show, don't tell.** The user decides by looking at a rendered figure, not by reading a
   plan. The first fragment is built and rendered before anything is asked.
3. **Ask once.** Every choice goes into one intake message. After it, nothing else is asked.
4. **Figures replace text, nothing else changes.** "Improve the slides", "make it less boring",
   "add (more) animations" and "animate this deck" mean the same thing to this skill: figures
   replace text blocks and screenshots on the slides that carry a process, structure, timeline,
   comparison or data and that get an Insight line. The deck's design, wording and order stay.
5. **Deliver by showing.** The hand-over is a before/after review page, not a report.

`<skill-dir>` below is the folder that contains this SKILL.md (Claude Code exposes it as
`$CLAUDE_SKILL_DIR`; elsewhere use the path you loaded this file from). `anim/` is a work folder
next to the user's deck, `anim/<name>/` one per fragment.

## Phase 0: Read the request

### The question

Before a mode is run, a figure is planned or a script is called, write for each slide (in
Mode C and for a one-slide source: for that slide) three lines, in this order:

1. **Question.** The one question the audience should be able to answer while the slide is up,
   as a sentence ending in a question mark, taken from the source and the occasion ("Which
   room can our group use?", "What happens to the pump after the fourth reading?"). A slide
   with no such question is a statement: its question is "What is the one thing to
   remember?". It is asked in the audience's words and never contains the answer or the
   claim's key words or numbers (the subject noun may appear; the claim's verb and its
   numbers may not): the blind review asks it of the resting slide.
2. **Does the base answer it?** The base is the slide as the deck skill builds it (Mode A) or
   as it stands in the HTML deck (Mode B), complete: every fact of the source, nothing left
   for a figure to add. When a person can answer the question from that still slide, the
   decision is **text** with the reason "base answers: <question>", and the base ships
   **immediately**: no fragment, spec, brief, slot, stills, intake message or review page for
   that slide. A lookup is always answered by the base: the audience finds a row in a table, a
   list or a map, and nothing in it unfolds. So is a single statement, a definition, and a
   figure that already stands on the slide and reads at rest.
3. **Insight**, only when the answer depends on a change: one sentence of the form "By seeing
   <what changes> unfold, the audience understands <what> better than from the still." The
   change must be the source's own: a state that flips, a quantity that grows or drains, an
   order in which a later step depends on an earlier one, one thing holding while another
   moves. "Livelier", "less boring", "draws the eye", "reveals the items one by one" name no
   understanding: with no insight sentence the slide is **text** and its base ships.

A slide with an insight goes on to a figure, and the **insight is made visible on the slide**:
the resting frame shows what the motion showed, as a trace in the source's words (the path
taken, before and after side by side, the stretch where nothing changed marked as such), and
its focal element is the answer to the Question. Someone who walks in after the pass can
answer the question and see why. Motion that leaves no trace has taught nothing a still could
not hold.

When every slide is **text**, the deck skill's complete deck (or the HTML deck as it stands)
is the deliverable: build it, check that it holds every source fact and opens from disk,
deliver it under the name the user asked for, and stop. No `anim/` folder, no question to the
user; the hand-over is one line per slide: its Question and "base answers it". Nothing is
animated to reach a count.

| The user says | Source | Mode | What happens |
|---|---|---|---|
| "improve the slides", "make it less boring", "add (more) animations", "animate this deck" | `.pptx`, Markdown, remark, a document | **A: deck first, then animate** | A deck skill builds the HTML deck, complete; then the Phase 0 question, triage and figures for the slides that get an Insight line. |
| "make N slides about X", "introduce this project" | a topic, repo or notes; no deck | **A: deck first, from a topic** | A deck skill builds the base deck with a slot on each figure slide; figures fill the slots. anim-slides never designs the deck's look. |
| the same | an HTML deck (reveal.js, impress.js, frontend-slides, any `<section>`/`.slide` deck) | **B: animate in place** | Triage and figures on the existing deck. |
| "animate slide N", "this diagram", "this chart" | any | **C: single slide** | No intake message. The slide's Question and Insight go into a one-row `anim/triage.md`; The short path: `references/quick.md` replaces Phases 1 to 3. The named slide gets one figure; a doubt whether motion helps is one line in the hand-over, never an unchanged slide. |
| a process, dependency, timeline or architecture in text, or a Mermaid block | docs, README, pasted text | **D: illustrate from docs** | Picture idea from each section's claim, then form and archetype (`references/archetypes.md`), spec, build; the host is the page or slot the user names. |
| "make the figures play on click", "loop them", "switch to lean" | an already animated deck | **E: re-integrate** | No rebuild: `integrate_fragment.py --control step|once` per fragment, or `host_theme.py --mode lean|match --apply`. Fragments stay as they are. |

**Mode A, deck first.** anim-slides adds figures to an HTML deck; it does not design one. The
deck skill builds the **complete** base: every slide finished and carrying all its source
facts, so that any slide can ship as built. A slide gets a slot only when its Insight line is
written; when none is, the base is delivered at once ("The question"). The
deck comes from, in order: (a) the user's own or organisation's deck skill; (b) `frontend-slides`
when installed (the style preset closest to the source's brand unless the user wants a new
look); (c) only when neither exists, the **built-in base**: for a topic or repo,
`<skill-dir>/base/deck.html` (read `base/README.md` and `base/example.html` first, adapt the
structure, never copy the content, pick the ground by the README's rule), slots on the figure
slides, then figures on top exactly as with a deck skill; for a Markdown source,
`scripts/md_to_deck.py --ground dark|light` (the base's colours and fonts on a plain document
layout). The hand-over then carries one line: "Built on anim-slides' built-in base; a deck
skill such as frontend-slides offers more looks." The skill never installs another skill by
itself and gives no install command it has not read in that skill's own docs. A deck skill exists
when its SKILL.md is on disk, listed by this harness or not: look in `~/.claude/skills`,
`~/.agents/skills`, `~/.codex/skills`, `~/.config/opencode/skills`, `~/.cursor/skills`,
`~/.gemini/skills` and the same folders in the project, then read and follow it. Never draw
a from-scratch deck ad hoc on the lean ground, and never reskin it afterwards: the base (a
deck skill's or the built-in one) comes first. A `deck.md` or an `md_to_deck.py` deck already lying in the folder is
not a choice the user made: with a deck skill installed the fallback is never used and never
offered, not as "keep the existing host" either; the intake's deck question is full deck or
lighter path, nothing else. The intake message says up front that the HTML deck has to exist first
and what it costs: a deck skill rebuilds the whole deck, and on a 40-slide deck that is the
longest step. It offers the **lighter path**: standalone animated slide pages for the chosen
slides only (one self-contained HTML per slide at 1280x720 or the source stage: title, fragment,
one-line takeaway), for a user who keeps presenting from PowerPoint or wants to see what the
skill does first. Default is the full deck. The `.pptx` stays the source for
`extract_slides.py` and `render_deck.py`; integration and the match look target the deck the
skill produced. The deck skill's own questions are folded into the ONE intake message and
recorded in Decisions: density is speaker-led unless the source is a reading deck; style is
the preset or template closest to the source's own look, chosen and named (no style previews
unless the user asks for a new look). The deck skill is run with those answers; it does not
ask the user itself. Details: `references/input-stage.md` "Deck first".

**Slot markers.** Ask the deck skill (or do it right after it) to give each candidate slide a
fixed-size slot `<div id="sN-slot">` and to put the markers **inside** it, round its content:
`<div id="sN-slot" style="width:..px;height:..px"><!-- sN-body -->...<!-- /sN-body --></div>`.
`measure_slot.py --selector '#sN-slot'` is then exact and
`integrate_fragment.py --anchor '<!-- sN-body -->' --replace-until '<!-- /sN-body -->'`
replaces the content and keeps the sized div. Markers round the div would delete it.
The deck skill knows nothing about slots: the main thread tells it, in its brief, "these
slides get a slot of W x H at this position; inner spacing with padding, not margin", because
a child's margin collapses through the slot and shifts `measure_slot.py`'s box.

**Short prompt.** "Make five slides about X" with a deck skill found: the deck skill builds a
finished draft first, with slots on the slides that have an Insight line; anim-slides then
fills the slots. With no such slide the finished draft is the delivery. No
intake message: the defaults (the deck skill's recommended style, match, once, not bundled)
are taken, recorded in Decisions and reported in the hand-over. With no deck skill found, the
same chain runs on the built-in base. `references/reference-case.md` walks through such a deck.

**Mode C, one slide.** Follow `references/quick.md` and nothing else: it replaces Phases 1
to 3 for that slide (no intake message, no brief, no previews, no review agents, no review
page) and names the few commands to run. Read no other reference unless a checker points to
a rule. **The named slide gets a figure:** the user chose this slide, so the triage decides
only what to draw, from the slide's own labels and values; a doubt whether motion helps is
one line in the hand-over after the figure. Only a slide with nothing to draw (a title, a
quote, a single picture) ships unchanged, with the reason. **Every source label stays on the
slide word for word** (`scripts/check_labels.py`); when a label is too long for the figure,
the slide's own text stays beside it. A `.pptx` source with no HTML deck gets the lighter
path's standalone page for that slide.

## Phase 1: Show first, ask once

1. **Extract and render.** `python3 <skill-dir>/scripts/extract_slides.py deck.pptx|deck.html|doc.md -o anim/outline.json`
   and `python3 <skill-dir>/scripts/render_deck.py deck -o anim/render`. Look at the
   `sheet-NN.png` contact sheets (12 slides each), not page by page. Both scripts number
   slides the same way, hidden slides included (`render_deck.py` renders them captioned
   "hidden" and lists them on stderr); note hidden slides in the triage. A picture count in `outline.json` that differs from the
   render points at pictures on the slide layout.
2. **Draft the triage** in `anim/triage.md` (`references/input-stage.md` section 3): every slide
   with Slide, Title, Question, Decision, Insight, Idea, Form, Verb, Archetype, Replaces, Why;
   no silent skips. Question, Decision and Insight come from Phase 0 "The question": a row is
   `illustrate` only with its Insight sentence, and a row whose base answers its question is
   `text` with "base answers it" under Why. On a
   slide of prose, bullets, cards or a table, Idea is one sentence on what it says beyond the
   order of its items, Form follows from it, and the archetype is only the build family
   (`references/archetypes.md` "Picture idea and form"); "order only", a row and `reveal` is a
   valid answer. Verb is the main motion, picked from the claim sentence
   (`references/motion-verbs.md` section 1); `travel` only with the traveller the source names.
   Then read down the Form and Verb columns for repeats (`references/input-stage.md` "Forms and
   verbs across the deck"). Budget 3 to 8 per 30 slides, never two animated slides in a row;
   "add more animations" reads as the upper end of the budget, not beyond it. The budget is a
   cap, never a floor: the count is the number of rows with an Insight, and it may be zero
   (then steps 3 to 5 and Phases 2 and 3 are skipped and the base ships). Re-render candidates with
   `--pages N,...` and open `full/p-NN.png`: `extract_slides.py` cannot see inside pictures.
3. **Theme.** `python3 <skill-dir>/scripts/host_theme.py deck.html --mode match -o anim/host-theme.css`
   and `--mode lean -o anim/lean-theme.css`. Compare the match block once with the deck's own
   CSS variables (muted text, secondary background, accent); on a deck without variables the
   accent may be picked by usage count, so check it against what the deck actually highlights.
   Correct by hand where needed. On a single-accent deck map `--anim-theme-ok` to the line
   colour or the accent unless a slide gives "ok" a meaning (the default mint is a second hue);
   keep `warn`/`danger` only where the source uses them.
4. **Build the first fragment before asking anything**: the most representative illustrate
   slide, through Phase 2's steps (spec, slot, brief, build, check). Render it integrated into
   its slide at rest under match and under lean (`render-phases.sh --theme FILE ...` or
   `--page` on a scratch copy): two stills. When that slide has two plausible figure readings
   (two forms of the idea such as a row or a funnel; timeline or pipeline; table or compare),
   render both readings as stills too.
5. **Send ONE message.** Use the harness's structured-question UI when it has one (Claude Code:
   AskUserQuestion, naming the stills' paths in the question text); otherwise one concise
   message with numbered choices. It carries:
   - the proposal: "N of M slides get a figure", and the triage table;
   - the stills (match and lean; both readings when there are two);
   - **look**: match (the default, for every deck) or lean (offered for talks and pitches
     with no brand rules);
   - **control**: once, stated in one line; add "your deck builds by click; the figures can do
     the same (step), say so if you want it" only when `outline.json` reports `builds` above 0;
   - Mode A only: the deck-first note and its cost, the lighter path, and the deck skill's
     density and style answers (Phase 0, Mode A);
   - **hand-over**: will the file be shared or presented from another machine (then it is
     bundled to one offline file)?

   After this message **nothing else is asked**. If the user is absent or says "just do it",
   take the defaults (full deck, match, once, not bundled) and
   record every default taken in a **Decisions** section of `anim/triage.md`, with Look and
   Control in its header. A brief from a caller that already names slides and look counts as
   the answer.

   Ambiguity is not a question: order, direction or grouping the source leaves open becomes a
   stated assumption in the brief. An unreadable figure is traced from the source picture and
   tagged "traced from <source> figure" (`references/accuracy.md`); it is not asked about.

## Phase 2: Build silently

For each remaining illustrate row (Mode C: from the one-row triage), the main thread writes
spec and brief first (specs are cheap; write them all before building), then builds.

1. **Spec.** `anim/<name>/spec.yaml` per `references/spec-format.md`: nodes, edges, groups,
   phases with second marks, cycle (4 to 10 s), control from intake, `verb:` from the triage
   row (`traveller:` with its `name` for `travel`). Reuse the source's words.
   Under about 12 nodes; split otherwise.
   **Durations are computed, not drawn.** A slide whose point is how long two to six things
   take (each a label with a duration and a unit, verb `race`) gets `archetype: durations`:
   the spec holds each label, value and unit as the slide writes them, plus the slide's own
   takeaway sentence as `claim:`, and step 4 builds the finished figure from it (bars on one
   scale, one speed, the difference or ratio as the focal number). It needs no pool copy and
   no hand-built motion. Shares, counts, prices and other quantities that are not time are
   not durations: they keep their own form. **A corrected value is a spec edit:** change the
   value in `spec.yaml` and run step 4 and the integration again, never edit the fragment. If
   the build stops because the `claim:` sentence no longer follows from the values, reword
   the sentence with the numbers the build prints, change the same sentence wherever the
   slide still shows it, and tell the user which sentence changed.
2. **Pool first, for craft.** Read `<skill-dir>/pool/index.yaml` (and `$ANIM_POOL/index.yaml`
   if set). The pool is the quality floor, not the menu of pictures: look an entry up by the
   triage row's verb first, then form and moves (`verb`, `form`, `moves` and `technique`
   lines), archetype last.
   When an entry draws that form, copy it to `anim/<name>/`, rename the prefix and adapt
   labels, node count, timing, marks and viewBox to the spec. When none does, hand-build the
   form (the normal path, not an exception) with the closest entry open as the bar for stroke
   weights, type sizes and spacing. Never ship a pool fragment unchanged.
3. **Slot and brief.** `python3 <skill-dir>/scripts/measure_slot.py deck.html --slide N --selector '#sN-slot'`
   prints the box, a viewBox, the checker flags and the slide's `type` (body and title size,
   weight, family; without `--selector` an absolutely positioned layout returns junk;
   `references/layouts.md` has the manual way). **Stay in the layout:** the figure fills the
   slot (or the text block or picture it replaces) at its measured size; the slide's other
   content, headline and the deck's CSS stay as they are. **Match the deck:** the fragment takes
   the deck's font (the host sets `--anim-theme-font`) and the type ladder of
   `references/style.md` 5 (at most one hero, only for a number or word the source states;
   nothing under the floor, nothing larger than the title); mono only for data. Fill
   `anim/<name>/brief.md` from `references/brief-template.md` **before any SVG is written**:
   the Question, the Insight and how the resting frame shows it, what the fragment replaces,
   the slot size, the focal element (the answer to the Question), the gap the first frame
   leaves and the beat table (a beat with no reason is cut; a beat that does not serve the
   Insight is cut too).
4. **Build.** `python3 <skill-dir>/scripts/scaffold_from_spec.py anim/<name>/spec.yaml -o anim/<name>/<name>.html --rendered-width <px>`
   covers the plain forms of the seven archetypes: chains, two-row snakes, graphs with lanes,
   line charts, column compares, layer stacks, dot timelines. For `archetype: durations` the same
   command writes the finished race figure (`scripts/race_figure.py`), which is not refined by hand. Funnels, rings, scenes, triangles,
   donuts, bars, timelines with event text and anything the spec cannot express are hand-built
   from the spec; do not force the scaffolder, use its output as the timing skeleton. **The motion
   is the verb's**: build it from its mechanism (`references/motion-verbs.md` section 5); the
   scaffolder draws a moving traveller only for `travel` (a token trip for `cycle`) and leaves
   other verbs to the builder. A travelling marker is used only for `travel` (and the token
   trip of a `cycle`). Each kind enters
   its own way (lines draw on, nodes land, numbers count, areas are revealed, labels follow),
   with the stagger and the one stillness before the answer step, using only the easing set
   (`references/motion-rules.md` "Easing", "Entrance by kind"). The focal element carries
   `data-anim-focal`. Refine with `references/archetypes.md` and `references/style.md`.
   **Phase marks** (`data-anim-phases`): a phase mark is a settled moment between narrated
   steps: nothing visible is mid-motion there. Three to five per slide (six when the slide
   narrates six steps), ascending, the last at the hold start. The scaffolder derives them from
   phase starts; a hand-built fragment sets them by looking at the frames.
   Parallel builders are fine (one subagent per fragment, all in one message), each writing only
   inside `anim/<name>/`, never the deck (`references/input-stage.md` section 5: brief, `soffice` note).
5. **Check by looking.**
   - `python3 <skill-dir>/scripts/check_fragment.py anim/<name>/<name>.html --name <name> --rendered-width <px> --stage-width <host stage width>`.
     Pass `--stage-width`: the text floor defaults to a 1920 stage (18 px; 12 px at 1280).
   - `python3 <skill-dir>/scripts/check_look.py anim/<name>/<name>.html --rendered-width <px> [--stage-width W] [--slot W H] [--theme anim/host-theme.css] --at-marks`
     renders the fragment in headless Chrome at rest and at every phase mark and fails on
     clipped or overlapping labels, text under its contrast floor on the real ground, more than
     three text-holding boxes, more than six hues, or text under the size floor; `--at-marks`
     runs contrast and the text floor at every mark too, one `marks` line each, because a label
     shown mid-pass must read as well as one at rest; `--at-pauses` checks three reproducible
     times between the marks and prints them (finding `pause`); read every WARN
     (faint lines, labels on fills, rest differs from the last mark, missing fonts). A box that
     is the meaning gets `<!-- anim-look: boxes-ok -->` before the `<svg>`; scene ground
     (water, land) gets `data-anim-scene` instead (`references/style.md` 2). On a deck-skill
     deck the fragment-mode font WARNs are expected (its web fonts are not installed locally)
     and can be ignored: the `--page` run in step 7 is the real font check.
   - Between them the two checkers FAIL on an `overshoot` curve and on two `focal` elements,
     and WARN on `easing-set`, `fade-after-fade`, `mono-costume`, `type-ladder`, `focal`
     (none), `node-count`, `line-contrast`, `accent-area`, `stillness` and `pause`: fix each or
     say why in the brief.
   - `<skill-dir>/scripts/render-phases.sh anim/<name> <W> <H> <marks...> <pass> rest`, then
     open every PNG. Fix clipping, overlaps, unreadable text, empty panels. The resting frame
     must read as a complete still (PDF shows only that), and it pays off the gap the first
     frame left open.
   - **Polish loop** (`references/look-rubric.md`): write the three worst problems, ranked,
     fix only those, re-render; also remove the one thing whose loss improves the figure. One
     round always, a second when the first changed the composition.
   - `python3 <skill-dir>/scripts/verify_facts.py anim/<name>/<name>.html --source anim/outline.json --slide <N> --spec anim/<name>/spec.yaml`
     (or `--source doc.md`): 0 FAIL, every WARN decided (`references/accuracy.md`).
   - The verb: with labels covered, the mark frames show the brief's verb happening (grew,
     split, tipped, filled), not one picture with a dot in different places, and they differ
     by more than opacity.
   - The question: open only the `rest` PNG, as someone who missed the pass. It answers the
     brief's Question, and the Insight can be pointed at on it (the trace, the marked stretch,
     the before beside the after). If the answer or the reason is only in the motion, draw it
     into the resting frame. Only when the slides were chosen by the triage (Modes A and B):
     if the slide's base answered the question as well, drop the figure and ship the base. A
     slide the user named (Mode C) keeps its figure.
   Never trust `--virtual-time-budget`, and never trust reading the source instead of the PNG.
   Where the harness cannot show images, run the measuring checks and state in the hand-over
   that the frames were not viewed.
6. **Integrate**, in the main thread, one call per fragment:
   `python3 <skill-dir>/scripts/integrate_fragment.py deck.html anim/<name>/<name>.html --name <name> --anchor '<!-- sN-body -->' --replace-until '<!-- /sN-body -->' [--gate 'section.present'] --control once --backup`.
   It hoists the style into the head, inserts the markup between `anim:<name>` markers
   (re-runs replace both), rewrites the gate (`section.present` reveal.js, `.visible` plain
   pages and `md_to_deck.py` decks), adds the print guard and, under `--control step`, the step
   snippet. Plain pages get `scripts/snippets/observer.html`. Apply the theme once:
   `host_theme.py --apply deck.html --from anim/host-theme.css` (lean: the lean file, plus
   `class="anim-lean"` on each animated slide). Keep the working deck small: read slices round
   the anchor (`grep -n`, `sed -n`), never the whole deck; no inlined fonts or images. Read
   `references/lessons.md` when integrating into a deck a deck skill built, or when a check
   fails in a way the other references do not explain.
7. **Check the page.** `render-phases.sh --page deck.html --slide N <W> <H> rest` per animated
   slide (never `--no-script` for `rest`: in frontend-slides decks `.visible` both gates and
   shows the slide). The rest render hides a deck's own staggered text (reveal classes keyed
   on the current-slide class): key those reveals also on the deck's active class and add a
   print rule; when the rest render still differs from the running deck, take the final
   screenshot from the running deck. `python3 <skill-dir>/scripts/check_page.py deck.html`
   (paired markers, gated fragments, print guard): check_page warns on the deck's web-font
   link and fails on any other external load.
   `python3 <skill-dir>/scripts/check_verbs.py deck.html --triage anim/triage.md`: 0 FAIL (a
   verb on every fragment, a reason on each repeat over a third, no marker outside `travel`
   and the token trip of a `cycle`).
   `python3 <skill-dir>/scripts/check_look.py --page deck.html --slide N --at-marks` per animated
   slide measures the fragment on the slide's own ground and stage width, at rest and every
   mark, and its gap to the slide's own text (FAIL on covering it); a contrast FAIL on a light
   ground means faded opacities or status colours must be raised (`references/style.md`,
   "Under a host theme").
   Open the deck in a real browser once (or ask the user to): headless frames never prove smoothness. Audit with
   the checklist at the end of `references/motion-rules.md`.
8. **Review by a fresh pair of eyes** (part of done). Before the review, run step 5's
   `verify_facts.py` command again with `--strict`: fix every `pairing` FAIL (a value beside
   the wrong label), decide each `pairing: review` WARN by reading the source, and record any
   FAIL on a label that is a true paraphrase, with its reason, in the brief. Render per animated slide
   `sN-before.png` (`anim/render/full/p-NN.png`), `sN-first.png` (first frame), the mark
   frames, the three `--at-pauses` frames and `sN-after.png` (rest), plus one un-animated slide as `context-after.png`, into
   `anim/review/blind/`. ONE fresh reviewer that has not seen the build (a subagent where the
   harness has one, otherwise a new session with no access to this conversation; if neither
   is possible, the hand-over says the review was not blind) works in two steps (`references/look-rubric.md`
   sections 1 and 3). **First read:** it gets only `sN-after.png` and the brief's Question per
   slide, and answers each in one sentence plus "could not tell". Write each answer verbatim
   as `sN-first-answer` under "First read" in Decisions before sending anything more; it is
   never edited and the hand-over quotes it. **Scoring:** then the same reviewer (or a second
   fresh one given the answers) gets the other stills and each slide's claim, scores the
   fourteen items and answers `ship` or `fix` (at most three problems, ranked) with the frame
   each is on. No brief, spec, triage or conversation at any step. `fix` blocks done: fix (or
   rebuild, as the rubric says; a weak first read is fixed in the picture, never in the
   question), re-render, review with a new reviewer, first read again. At most two rounds;
   still rebuilding after the second means the picture idea is wrong: back to the brief. A
   finding is never softened because the build took effort; findings left go into the
   hand-over and Decisions.

## Phase 3: Deliver by showing

1. If the file will be shared: `python3 <skill-dir>/scripts/bundle_deck.py deck.html -o deck.bundled.html --fetch`
   (inlines stylesheets, scripts, fonts and images), then `check_page.py deck.bundled.html`
   and one `render-phases.sh --page deck.bundled.html --slide N ... rest`. Do not read the
   bundled file.
2. When the deck will be printed or sent as a PDF:
   `python3 <skill-dir>/scripts/export_pdf.py deck.html --install [--source static-deck.html] [--paper letter|a4|both]`.
   It writes one landscape page per slide and reads the PDF back: every label of a slide on
   its page, inside the page and drawn; every table cell in its own cell, repeated values
   counted; no presenter note (`aside.notes`, `.speaker-notes`, `[data-presenter-only]`) on
   any page. Labels seen only during the pass (step captions, a changing state label) are
   printed in a strip under their slide; with `--source` (the deck before figures) so are the
   source words a figure shortened. `--install` writes the print rule into the deck once
   every paper passed, so the browser's own Print fits Letter and A4 too. A FAIL blocks the
   hand-over and leaves an earlier PDF in place. Without the rule a fixed 1920 px page loses
   the right side of every slide.
3. Render the resting frame of every animated slide of the integrated deck (in Mode A every
   slide: the whole deck is new, and the review page's Deck column is empty for the rest) into
   `anim/review/after/` (`render-phases.sh --page deck.html --slide N <W> <H> rest --out anim/review/after/sN`,
   one folder per slide; `review_page.py --help` lists the other names it accepts), and make sure the source renders
   of those slides are in `anim/render/full/` (`render_deck.py --pages`).
4. `python3 <skill-dir>/scripts/review_page.py --deck deck.html --before anim/render/full --after anim/review/after --triage anim/triage.md --title "<deck name>" -o anim/review/index.html`
   (optional `--only animated`, `--previous DIR`, `--link-images`). Animated slides play live
   on the page, on the deck's ground and theme, once in view and again with Replay; the resting
   still stays under them for print. Open it and the deck.
5. Send a few lines: N of M slides animated, each with its Question and Insight in one line
   and its recorded first answer quoted verbatim (every round);
   the slides kept as base with "base answers it"; the review page path; the deck path (the bundled
   one if shared); the two switches for later, one line each:
   `integrate_fragment.py ... --control step` (figures by click) and
   `host_theme.py deck.html --mode lean --apply deck.html` (lean look). On the built-in base,
   add the one line from Phase 0 (Mode A). The review page is the report; no long prose.

## Hard rules
- **Question first.** Each slide has a written Question before anything is built. A base that
  answers it ships complete and at once, with no figure. A figure needs an Insight sentence
  naming what the audience understands better by seeing a change unfold, and its resting frame
  shows that insight and answers the Question without the motion. No figure is built to reach
  a count, to fill a slot or because the skill was invoked (Mode C too: from the one-row triage).
- **Ask once, show first.** One intake message carries the proposal and rendered stills of the
  first fragment; no later questions; defaults taken are recorded in `anim/triage.md`.
- **Deck first.** anim-slides styles fragments, never the deck: a source or topic with no HTML
  deck goes through a deck skill, else the built-in base; nothing is installed automatically
  (Phase 0, "Mode A, deck first").
- **Stay in the layout, match the deck.** A figure fills its slot at the measured size in the
  deck's palette, font and type scale; slide layout, headlines and deck CSS do not change.
  Readability, contrast, clipping and gaps are checked at rest and at every phase mark.
- **Keep the slide's visuals.** A slide whose own chart or figure already answers its Question
  ships unchanged. (A slide the user named is drawn all the same, Mode C.) Once a slide has an Insight line, a chart, graph, table, map, flowchart or
  scientific figure on it is the core content: redraw it from its data and animate that, never
  drop it or replace it with a text summary. An icon or picture that labels a column, lane, category or actor is content
  too: embed it beside the fragment (licence permitting) or redraw it as a glyph. Only a
  background, a logo or an unrelated photo may go; when unsure, keep it and say so.
- **Make a visible change.** A fragment replaces the slide's cards, pills, bullet column or HTML
  diagram. Motion over the existing drawing with the boxes left in place is not a figure; if
  nothing else is possible, the brief says why.
- **Less.** A slide with a figure keeps the figure's own form (stairs stay stairs, bars stay
  bars) plus one movement. On a slide of prose, bullets, cards or a table the form follows the
  picture idea and may come only from structure the source states; the content never grows:
  no node, label, number, arrow direction, actor, bracket or storyline the source does not
  state, and a source that states only order gets a row and `reveal`. The look follows
  `references/style.md` under match and lean alike (a host theme changes colours and fonts
  only): no filled cards, chips or caption bars; rings and thin lines; one focal element; the
  accent only on what is active or reached (at most about a fifth of the ink at rest); at most two semantic colours; glow on one element
  at a time, never on a line; mono only for data; the deck's font, never an embedded one.
- **One verb per fragment.** The main motion is the verb of the slide's claim, written in the
  triage row and the brief and carried as `data-anim-verb` on the wrapper; no dot travels
  unless the source names what travels. One verb over a third of the deck needs a reason per
  repeat.
- **Accurate.** Every number and label traces to the source or is marked illustrative;
  `verify_facts.py --spec` passes before a figure is done (`references/accuracy.md`).
- **Contract.** Prefix every class, id and keyframe with `<name>-`; colours and fonts only via
  `var(--anim-*)` with the contract's fallbacks; animate only under the gate (ungated = the
  finished state); no `<script>`, `<link>`, `<image>`, `@import`, `@font-face` in a fragment;
  text at or above 18 px at rendered size on a 1920 stage (scaled by `--stage-width`), titles
  22 px and up.
- **Plays once.** One pass of 4 to 10 s when the slide becomes current, iteration count 1,
  fill forwards, 100 % keyframe = resting frame, nothing looping or pulsing while the slide is
  up. At most three things moving at once (more than three warns, more than six fails);
  reduced-motion block present.
- **One control per deck.** `once` unless the user asks for `step`; mention step only when the
  source builds by click. A slide that differs needs a reason in `anim/triage.md`. Step
  listens to keys only: present it with the keyboard or a clicker.
- **No network loads.** None in fragments, no new ones in the deck; loads the deck already has
  stay. Work on the unbundled deck; bundle only at hand-over when it will be shared.
- **Brief before drawing.** The brief names the focal element and carries the beat table
  before any SVG is written; motion uses only the easing set and enters by kind.
- **Reviewed blind.** A reviewer that has not seen the build answers each Question from the
  resting slide first, then scores (Phase 2 step 8); passing the checkers is not looking right.
- **Deliver by showing.** The before/after review page (`review_page.py`) is part of done.

## Files
References, each with when to read it:
- `references/fragment-contract.md`: before building anything; shape, prefixes, tokens, gate, resting frame, controls.
- `references/input-stage.md`: Modes A and B; deck first, outline JSON, triage, look and control, handoff to builders.
- `references/quick.md`: the whole path for one named slide (Mode C).
- `references/spec-format.md`: writing a spec (Phase 2 step 1); Mermaid mapping, worked examples.
- `references/archetypes.md`: choosing the form ("Picture idea and form"), then the chosen family's section.
- `references/brief-template.md`: per fragment, before any SVG is written.
- `references/layouts.md`: when `measure_slot.py` cannot measure the slot.
- `references/motion-rules.md`: timing, easing, entrance by kind; its audit checklist after integration.
- `references/motion-verbs.md`: picking the verb (section 1) and building its mechanism (section 5).
- `references/style.md`: building and polishing every fragment; "Under a host theme" on a contrast FAIL.
- `references/accuracy.md`: writing labels and numbers; deciding `verify_facts.py` findings.
- `references/look-rubric.md`: the polish loop and the blind review.
- `references/lessons.md`: integrating into a deck a deck skill built, or a check failing in a way the others do not explain.
- `references/reference-case.md`: a short prompt ("make N slides about X"); a five-slide deck worked through.

Every script takes `--help` for its flags. `scripts/snippets/step-host.html` is the step-mode
host snippet that `--control step` inserts.

## Related skills (use them when your harness has them; none is required)
- A deck skill (the user's own, frontend-slides, reveal.js, Slidev) builds the deck in Mode A.
- A motion-design skill for deeper timing guidance; a pptx skill for sources beyond what
  `extract_slides.py` reads.
