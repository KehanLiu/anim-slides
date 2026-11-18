# Built-in base deck

A small designed deck for the case where nobody has a deck yet ("Make five slides introducing
this project") and **no deck skill is found** on disk (SKILL.md, Phase 0, Mode A). The order
stays the same as with a deck skill: the base deck is built first, with a slot on each figure
slide, then anim-slides fills the slots. When a deck skill exists (the user's own, or
frontend-slides), that skill builds the deck and this folder is not used.

- `deck.html`: the template. Page skeleton (16:9 stage, keyboard and swipe navigation, `#N`
  links, the `.visible` gate fragments animate under, progress bar, print one slide per page,
  reduced motion), the five slide types as marked sections with placeholder text and named
  slots, all colours and fonts as CSS variables with every `--anim-theme-*` mapped to them.
- `example.html`: the same template filled for one project (anim-slides itself). Read it to
  see the rules applied; adapt the structure to the user's material, never copy its content
  or its canal-lock figure.

The delivery message says in one line that the deck is built on the built-in base and that a
deck skill such as frontend-slides offers more looks. Nothing is installed automatically.

## One look, two grounds

Set `data-ground` on `<html>`; nothing else changes.

| Ground | Use it when | Palette (text contrast on ground) |
|---|---|---|
| `dark` (default) | Screens and LED walls in a dimmed room; developer or technical audiences; a talk | ground `#0F1E27`, text `#E6EDF0` 14.4:1, muted `#93A7B2` 6.8:1, accent `#34D1BF` 8.9:1 |
| `light` | A lit room or daylight, a projector that greys out blacks, a deck that will be printed or read as a PDF, a business or classroom audience | ground `#F2F5F5`, text `#11222B` 14.9:1, muted `#475B66` 6.5:1, accent `#00776B` 5.0:1 |

Rule: light when the deck will be printed or read on paper or PDF, or presented with the room
lights on; dark otherwise. When unsure, light for a meeting room, dark for a stage. Record the
choice in the Decisions section of `anim/triage.md`.

Figures follow the ground through the `--anim-theme-*` variables, including `ok`, `warn` and
`danger`, so a pool fragment needs no edit to read on the light ground.

## The five slide types (sizes at the 1920 x 1080 stage)

| # | Type | Job | Main visual | Area |
|---|---|---|---|---|
| 1 | Cover | Name it, say what it does, show proof | A still of the real output, slot `#s1-slot` 1920 x 590 along the bottom edge | 55 % |
| 2 | Live demo | Let the audience watch it work once | The live figure, slot `#s2-slot` 1760 x 629 at (80, 236) | 53 % |
| 3 | Benefits | Three reasons to care | One line glyph per column, at most 300 x 210 | at least 25 % stays empty |
| 4 | Workflow | Input to result | Steps as rings on one line, slot `#s4-slot` 1760 x 640 at (80, 260) | 54 % |
| 5 | Call to action | What to type next | Two large monospace lines | at least 25 % stays empty |

1. **Cover.** Title block at (120, 120): name 140 to 170 px, one line of what it does at 40 to
   48 px (10 words at most), one mono kicker at 24 to 28 px. For an animated figure use a still
   crop of its resting frame under its own prefix (static rules only, viewBox narrowed to the
   most telling part), not a second live copy. No folio.
2. **Live demo.** Headline, the slot, one caption line at 28 to 32 px (22 words at most): what
   the figure is, where it comes from, how long it plays. Nothing else.
3. **Benefits.** At most three columns, 96 px gaps, from y = 350. Each: glyph (line and accent
   colours, no fills, no boxes), a claim of 2 to 4 words at 46 px that fits on one line, one
   supporting line at 32 px (16 words, 3 rendered lines at most).
4. **Workflow.** 3 to 5 rings (r about 100), centres at least 400 px apart, on one thin line;
   input left in mono, result right after an arrow. Under each ring the name at 32 to 36 px
   (4 words at most) and up to two mono lines at 24 px (24 characters each). The step the
   headline is about gets the accent and the only glow.
5. **Call to action.** Two steps: a 28 px mono label over a 68 px mono line (40 characters at
   most) with a 4 px accent rule. The command is copied verbatim from the project's README; the
   sample request is one the project documents. Footer at most two lines at 28 px.

**Headlines:** a claim, not a topic ("Three phases, one question", not "How it works"), 6 words
and 32 characters at most, one line at 96 px. Read only the headlines in order: they should
tell the story.

**Sizes:** cover title 140 to 170 px; headline 96 px; claim or step name 32 to 54 px; body and
caption 28 to 34 px; mono sub-label and folio 22 to 28 px (24 px minimum for anything the
audience must read); side padding 120 px, top padding 96 px. Text at least 4.5:1 on the
ground on both grounds, accent at least 3:1 (the palette gives 5:1 or more).

**Slots:** height = width x (figure viewBox height / width); at least 1600 px wide on a demo
slide; nothing else within 24 px; markers inside the slot (`<!-- sN-body -->` ...
`<!-- /sN-body -->`); inner spacing with padding, not margin. Slide types may be dropped or
repeated; a figure slide keeps one main visual.

**Verify** as for any deck: every slide rendered at 1280 x 720 on the chosen ground, an
animated slide also mid-pass; `check_page.py deck.html`; `check_look.py --page deck.html
--slide N --at-marks` per animated slide.
