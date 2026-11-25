# Style: quiet shapes

The shape rules of every fragment, under match and lean alike. A host theme (match) changes only
colours and fonts; lean is the optional dark ground with the skill's own palette. Either way the
figure is almost empty and one thing at a time is lit. Think of a lecture diagram drawn with a
fine pen, not a dashboard.

## Principles

0. **Less.** A fragment is the slide's own picture, drawn quietly, plus the movement that
   carries its story. Two cases:
   - *The slide has a figure* (chart, diagram, meaning-carrying illustration): the fragment
     keeps its form: stairs stay stairs, a table of values stays rows, a Gantt stays bars.
     Turning a staircase into a line chart, or adding brackets, arrows, glows or a second
     storyline the figure does not have, is "too much" even when every number is right.
   - *The slide is prose, bullets, cards or a text table*: there is no figure form to keep.
     The form follows the structure the source states (the picture idea, archetypes.md): a
     stated cycle may be a ring, a stated narrowing a funnel, a stated rise a fill level. That
     is drawing the slide, not "too much"; a row is right when order is all the source says.

   In both cases nothing appears that the source does not state (no node, label, number,
   actor, arrow direction or storyline; accuracy.md, rule 0), and several things never travel
   at once. Before adding an element or a motion, ask what the slide loses without it; if the
   answer is nothing, leave it out.
1. **Space and composition.** Fewer elements, larger type, wider gaps; if a slot feels
   crowded, remove a label before shrinking the type. The drawn extent spans at least 60 % of
   the slot's width or height, with no dead bands around a thin strip ([layouts.md](layouts.md)).
   Not always a centred, evenly spaced row: the focal element may sit off centre, and the
   figure's left edge may line up with the headline's. Text and shape edges share two or three
   vertical anchor lines. Gaps inside a group are at most half the gap between groups; equal
   peers may be evenly spaced, the focal step gets more room. At most 12 nodes, and at most 8
   spokes on one hub; more means split the slide or keep a list.
2. **No boxes unless a box is the meaning.** No filled panels, no card borders, no caption
   bars, no chip backgrounds. A group is a hairline bracket (1.5 px, `--anim-line`, open on the
   label side) with a small label at one end, never a framed card and not a tint. A node is a
   ring, a dot or a glyph with its label outside; a step in a pipeline is a label on a line,
   not a rounded rectangle with a fill. When the source names a physical thing (a jar, a beam,
   a ballot box, a cell, a river bed), draw that thing in a few thin strokes instead of a ring
   that stands for it: the subject's own shape says what it is
   ([motion-verbs.md](motion-verbs.md) section 1). Rectangles are allowed only when the
   source shows containers (a table, a lock chamber, a database). In a scene, mark the ground
   that is the thing itself (water, land, a chamber wall) with `data-anim-scene` on the shape
   or its group; `check_look.py` then skips it for boxes and labels on fills. Never mark
   cards or panels behind labels.
3. **The accent lives only in the light.** The accent (`--anim-accent`) marks what is active
   now and what the story has already reached. Reached parts stay in the accent, solid, with
   no glow, in the resting frame; parts not yet reached stay in `--anim-line` and
   `--anim-muted`. When the story ends with every part reached, the accent no longer marks
   anything: the reached parts settle to `--anim-fg` and the focal element alone keeps the
   accent. At rest the accent is at most about a fifth of the drawn ink (`check_look.py`
   measures it from pixels and warns above 25 %), unless the
   accent ink is the focal element itself: one chart series that is the claim may be the accent. Semantic
   colours (`--anim-ok`, `--anim-warn`, `--anim-danger`, `--anim-accent-2`) appear only where
   they carry a meaning stated on the slide (up/down, absorbed/released, good/bad), and at
   most two of them in one fragment. `check_look.py` counts distinct hues (greys and the
   ground ignored): more than four warns, more than six fails.
4. **Line weights.** At a 1920 stage: structure (wires, axes, rings, outlines) 2 px in
   `--anim-line`, which reaches 3:1 against the ground; secondary and decorative lines (grid,
   ghosts, brackets) 1.5 px, possibly at reduced opacity; the active path 4 px in the accent.
   `check_look.py` warns on a solid stroke below 1.5:1 against the ground (a dashed or dotted
   one may go down to 1.1:1).
   Dashed for weak or secondary links. Arrowheads small and open.
5. **A type ladder carries the hierarchy.** Sizes at a 1920 stage:

   | Role | Size | Weight | Notes |
   |---|---|---|---|
   | hero | 56 to 96 px | 400 to 500 | the one number or word that is the claim; letter-spacing -0.02em; at most one; only when the source states it |
   | label | 24 to 30 px | 500 to 600 | names of parts |
   | sub-label | 18 to 20 px | 400 | `--anim-muted` |
   | caption | 24 to 28 px | 400 | SVG text under the figure |

   Two different sizes in one fragment differ by at least 1.25x (`check_fragment.py` accepts
   1.2x for rounding); at most four sizes. Every
   number uses `font-variant-numeric: tabular-nums`. Labels are sentence case: no tracked
   capitals, no small caps. Emphasis may come from size and weight as well as colour. Titles
   belong to the slide, not to the fragment; nothing gets a pill.
6. **Captions are a sentence, not a bar.** The narration line is SVG `<text>` inside the
   fragment's SVG, under the figure, centred, with no background rect. Phase changes
   cross-fade the text. No HTML text outside the SVG; an HTML caption belongs to the slide
   (contract section 1).
7. **Mark what is illustrative.** Example values get a small outlined tag ("illustrative",
   1.5 px stroke in `--anim-line`, 18 px) in a corner of the figure, the same way every time.
8. **Glow, not shadow, and only once.** The element active now, or the travelling head, may
   carry a soft glow: a second copy of the shape behind it in the accent at 25 to 35 %
   opacity with a 6 to 10 px blur (`filter: blur()` on the copy, or a wider stroke at low
   opacity). One glow at a time; in the resting frame at most one, on the focal element, or
   none. Lines and arrows never glow.
9. **Motion is calm and happens once.** Rules and values are in
   [motion-rules.md](motion-rules.md); curves come only from its easing set (enter, move,
   exit, land, linear). The entrance follows what enters (motion-rules.md, Entrance by kind): lines draw on, a node lands when its
   line reaches it, a number counts or rides its bar, an area is revealed by a mask in the
   direction of meaning, a label settles last, a caption cross-fades. Not everything fades in.
   The pass plays once when the slide becomes current and ends on the resting frame.
10. **Both grounds.** The same rules hold on a light ground: lines get darker, the glow stays
    coloured, panels stay absent. Both looks are rendered once, as the intake stills
    (SKILL.md, Phase 1); after that, render the look the deck uses.
11. **One focal element.** Every fragment has exactly one, marked `data-anim-focal` on the
    element or its group: the hero number or word, or the shape that is the claim (the full
    jar, the tipped beam, the last bar). It is visibly larger or heavier than its peers (about
    1.5x a peer, or the only hero-size text). Squint test: with the frame blurred, it is still
    seen first.
12. **Mono is for data; fonts come from the deck.** `--anim-mono` only for numbers, units,
    codes, timestamps, identifiers and formulas. Names, terms, translations, group labels and
    layer names use `--anim-font` at sub-label size in `--anim-muted`; a mono text with no
    digit and no code-like token is a fault. The fragment takes the deck's font in both looks
    (the host sets `--anim-theme-font`); standalone it falls back to the stacks in
    [fragment-contract.md](fragment-contract.md) section 3. Never an embedded font, never
    `@font-face`, never a web font load.

## Not this

| Default to avoid | Do instead |
|---|---|
| Glow on several things, or on lines | One glow, on what is active now; at rest on the focal element or none |
| Mono for names and terms | `--anim-font`, sub-label size, muted; mono only for data |
| Every text the same size | The ladder: one hero at most, labels, sub-labels, 1.25x apart |
| An evenly spaced, centred row by habit | Group, give the focal step room, share anchor lines with the headline |
| Every shape fading in | Draw lines on, land nodes, reveal areas by mask, labels last |
| Tracked capitals, small caps | Sentence case, normal spacing |
| A row of big numbers beside a bar chart, or number cards | The form of the data relationship: a scaled object, a split whole, one curve (archetypes.md) |
| Everything in its final place, only animating in | A first frame with a gap the pass closes (motion-rules.md, Setup, then payoff) |

## Tokens

Fragments use only `--anim-*` tokens (contract section 3). The fallbacks are the lean palette:
background `#0F1E27`, panel `#0D1820` (used only for the rare container), line `#56707F`,
foreground `#E6EDF0`, muted `#93A7B2`, accent `#34D1BF`, accent-2 `#FF8A3D`, ok `#8ED7AD`,
warn `#FFD15C`, danger `#FF6B6B`. Hosts retheme through `--anim-theme-*`.

## Under a host theme

When the deck keeps its own look (the **match** look, `scripts/host_theme.py --mode match`),
the host supplies the twelve token values and nothing else. Every principle above still holds:
a corporate deck full of rounded panels and coloured pills gets rings, labels on lines and
hairline brackets drawn in its blue and its font, not its panels redrawn in SVG. The test is
the before/after pair: if the resting frame looks like the old slide with the same boxes, the
fragment has copied the host's style instead of adopting its colours. The line token is
darkened or lightened until it reaches 3:1 against the ground (on white about `#768A95`); the
glow stays the accent copy at about 30 % opacity; the one accent is the brand's primary colour.
Fades tuned for the dark ground vanish on white: raise faded and secondary opacities from
about 0.35 to 0.55 to 0.65, and check the faintest element in a rest render.

## Anatomy by archetype

A traveller appears only under the verb `travel` (or as the one trip of a `cycle`): a small
glyph with a label beside it that says what it is (a parcel, a ballot, a blood sample), in the
accent with the one glow. Under every other verb nothing rides the lines; the active element
carries the accent.

- **pipeline**: steps are labels on a single horizontal line with small ring markers; the
  active step carries the accent; a reached step keeps its ring in the accent, solid, no
  glow. `--anim-ok` marks a passed step only when the slide states success.
- **graph**: rings (r 32 to 44 at a 1920 stage) with an optional line glyph inside, labels
  outside (below or beside), wires 2 px, the active path 4 px in the accent; groups as a
  hairline bracket with a small label in `--anim-font`, never a card.
- **timeline**: one axis line, dots on it, labels alternating above and below with a thin
  leader; dates in mono; eras as hairline brackets below.
- **states**: states are rings or glyphs; the current state carries the accent; transitions
  are thin arcs with the label on the arc.
- **compare**: two or more columns separated by nothing but space (or one hairline); row
  labels in `--anim-muted` at the left; the verdict as a sentence below.
- **layers**: bands separated by hairlines, names at the left in `--anim-font`, sentence case,
  muted; the active band carries the accent.
- **chart**: axes 2 px in `--anim-line`, gridlines 1.5 px dotted at 40 to 60 % opacity, one series
  in the accent, reference lines dashed, events as small outlined tags on the trace; the
  value readout is inline text (often the hero), not a card.

## Checklist before shipping

- [ ] Exactly one `data-anim-focal`, and it wins the squint test. Fewer than 4 fills
      (excluding dots and glyphs).
- [ ] Accent only on active and reached parts, at most about a fifth of the ink at rest; at most
      one glow at rest; at most two semantic colours, each explained by the slide.
- [ ] Sizes follow the ladder (1.25x apart, at most four), none under the text floor;
      numbers tabular; sentence case; mono only on data.
- [ ] Figure spans at least 60 % of the slot; no dead bands; at most 12 nodes, 8 spokes.
- [ ] Caption is plain text; illustrative tag present if any number is an example.
- [ ] The verb is visible with the labels covered: something grows, splits, tips or changes
      between the phase frames, not a dot in different places.
- [ ] Rendered in the deck's look; the resting frame is calm and complete.
