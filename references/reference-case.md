# Reference case: a five-slide intro deck from a short prompt

The prompt: "Make five slides introducing this project". No deck, no source file. This is
the chain SKILL.md Phase 0 describes for a topic with no deck, shown on anim-slides' own intro
deck. The base comes from a deck skill when one is on disk (frontend-slides here); when none
is found, from the built-in base, `base/deck.html`. The finished deck on the built-in base is
`base/example.html` (a copy is `docs/intro-deck/index.html`); the chain is the same either way.

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

| # | Slide (deck skill or base) | anim-slides adds | Rule it shows |
|---|---|---|---|
| 1 | Cover: project name, one-line promise, a picture slot | A still crop of `pool/canal-lock`: its resting frame, viewBox cropped to the chamber and the boat, no keyframes. The motion is saved for slide 2. | Stay in the layout: the crop fits the cover's picture slot at its measured size; title and promise stay the deck skill's. |
| 2 | What it does: one sentence above a wide slot | `pool/canal-lock` adapted to the slot (viewBox, timing, labels in the deck's font): boat in, gates close, water rises, boat out. The full pass plays once. | Pool first: a fitting entry is adapted, not rebuilt. Match the deck: palette and font from `host_theme.py`, label sizes on the type ladder (`style.md` 5). |
| 3 | Benefits: three short points | Nothing. A list of benefits states no process, so it stays text; it also keeps two animated slides apart. | Figures replace text only where the slide carries a process, structure or data; the budget. |
| 4 | Workflow: deck in, figures out | A `reveal` row of the steps the slide names (deck skill builds, slots measured, figures built, checked, delivered), each step lit as it is reached and staying lit, in the slot below the headline. | One verb from the claim: order only, so a row and `reveal`, no travelling dot. |
| 5 | Call to action: install command and a sample prompt | Nothing. The deck skill sets `npx skills add KehanLiu/anim-slides` and a sample prompt ("Make five slides introducing this project") in its own type. | Deck first: the deck's own design carries the text slides. |

In `base/example.html` slide 4 keeps the base's own ring row in its slot (a fragment may
replace it between the `s4-body` markers), and slide 5's sample request is the one README.md
shows ("animate slide 4 of deck.pptx").

## Checks that make it pass

- Slides 2 and 4: `check_look.py --page deck.html --slide N --at-marks` with 0 FAIL: no label
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
  harness; `lessons.md`).
- A figure that moves the headline, resizes the slot, or sets its own font instead of the
  deck's or sizes off the type ladder.
- A clean rest frame with a caption that is unreadable at its phase mark.
