# Reference case: a five-slide intro deck from a short prompt

The prompt: "Make five slides introducing this project". No deck, no source file. This is
the chain SKILL.md Phase 0 describes for a topic with no deck, shown on anim-slides' own intro
deck. The base comes from a deck skill when one is on disk (frontend-slides here); when none
is found, from the built-in base, `base/deck.html`. The finished deck on the built-in base is
`base/example.html`; the chain is the same either way.

## The chain

1. **Base first.** The deck skill builds the five slides as a finished draft: its own style
   preset, title, copy, layout. Without a deck skill the main thread builds them from
   `base/deck.html` after reading `base/README.md` and `base/example.html`: the five slide
   types, the ground by the README's rule (dark here: a developer audience on screens), the
   slots already in place. A deck skill's brief from anim-slides names the figure slides and
   asks for a fixed-size slot on each, markers inside the slot
   (`<div id="s2-slot" style="width:..px;height:..px"><!-- s2-body -->...<!-- /s2-body --></div>`).
2. **No questions.** A short prompt takes the defaults (the preset the deck skill recommends,
   or the base's ground; match look, `once`, not bundled); they go into Decisions and the
   hand-over, not into a question. On the built-in base the hand-over adds one line: built on
   the built-in base, a deck skill such as frontend-slides offers more looks.
3. **Figures fill the slots.** For each slot: `measure_slot.py --selector '#sN-slot'` gives the
   box and the slide's `type` line; `host_theme.py --mode match` gives palette and font; the
   fragment is adapted from the pool when an entry fits, built otherwise; then
   `check_look.py --at-marks`, integration, `check_look.py --page deck.html --slide N --at-marks`.
   The deck's layout, headlines and CSS are not touched.

## Slide by slide

Phase 0 comes first: every slide gets its Question, then either an Insight or "text: the base
answers it". One slide of five gets a figure.

| # | Slide (deck skill or base) | Question | Decision: Insight or reason | anim-slides adds |
|---|---|---|---|---|
| 1 | Cover: project name, one-line promise, a picture slot | What is the one thing to remember? | text: the base answers it (name and promise) | Nothing. The cover's picture slot holds a still crop of `canal-lock` (see the note). |
| 2 | What it does: one sentence above a wide slot | How does a boat get up to the higher canal? | illustrate. By seeing the chamber fill while the gates stay shut, the audience understands that the water lifts the boat, and that the upper gates open only once both levels match. | `pool/canal-lock` adapted to the slot (viewBox, timing, labels in the deck's font), verb `grow`, one pass. The resting frame keeps the trace: the dashed start level and the lift marker. |
| 3 | Benefits: three short points | What do I get from it? | text: the base answers it (three unrelated points) | Nothing. |
| 4 | Workflow: source in, three phases, deck out | What happens between handing over a deck and getting it back? | text: the base answers it (order only; showing the steps one by one adds no understanding) | Nothing. The base's ring row stays as built. |
| 5 | Call to action: install command and a sample prompt | How do I start? | text: the base answers it | Nothing. The deck sets `npx skills add KehanLiu/anim-slides` and the sample request README.md shows ("animate slide 4 of deck.pptx") in its own type. |

What the rows show: the question gate decides, not the content type (slide 4 states a process
but its order is all there is); pool first for slide 2, with palette and font from
`host_theme.py` and label sizes on the type ladder (`style.md` 5); the budget is a cap, so one
figure is the right count here, and no two animated slides sit next to each other.

**Note: the deck holds two things the current Phase 0 would not build.** `base/example.html`
predates "question first" and is kept as it is.
- Slide 1: the still crop of `canal-lock` (its own `canal-still` prefix, no keyframes) in
  `#s1-slot`. No Insight asks for it. It is the base's cover picture ("a still of the real
  output", `base/README.md`), not a triaged figure.
- Slide 4: the ring row fades in step by step (`.wf-step` k1 to k5, 0.3 s to 2.7 s). That is
  an order-only reveal in the base's own CSS. The triage above would not add it.

## Checks that make it pass

- Slide 2: `check_look.py --page deck.html --slide 2 --at-marks` with 0 FAIL: no label
  clipped, overlapping or under the text floor at rest or at any phase mark, every label above
  its contrast floor on the slide's real ground at every mark, and the figure clear of the
  headline (the `gap` line).
- Slide 1: the still has no `data-anim` wrapper (it is a static crop), so it is checked by
  looking at the 1280 x 720 render, not by `check_look.py`.
- On the built-in base, the same checks on both grounds: the light ground feeds the figure
  light tokens (`ok`, `warn`, `danger` included) through `--anim-theme-*`, so `canal-lock`
  passes contrast at every mark without edits.
- The blind review (`look-rubric.md`) scores Host fit on all five slides: the figures should
  look like the deck drew them.

## What would be wrong

- anim-slides drawing the deck on its own lean dark ground and reskinning it afterwards with
  the deck skill's look (a real run did this when the deck skill was not registered in the
  harness; `lessons.md`, Host decks).
- A figure that moves the headline, resizes the slot, or sets its own font instead of the
  deck's or sizes off the type ladder.
- A clean resting frame with a caption that is unreadable at its phase mark.
- A `reveal` figure on slide 4 to make the steps appear one by one: no Insight, so the base
  ships.
