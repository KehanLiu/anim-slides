# Style: lean and quiet

The default look of every fragment. The slide is dark, almost empty, and one thing at a time is
lit. Think of a lecture diagram drawn with a fine pen on a blackboard, not a dashboard.

## Principles

1. **Space is the main material.** The figure fills about 60 to 70 % of its slot and sits
   centred; the rest stays empty. Fewer elements, larger type, wider gaps. If a slot feels
   crowded, remove a label before shrinking the type.
2. **No boxes unless a box is the meaning.** No filled panels, no card borders, no caption
   bars, no chip backgrounds. A group is a hairline bracket (2 px, `--anim-line`, open on the
   label side) with a small mono label at one end, never a framed card and not a tint. A node is a ring, a dot or a glyph with its label outside; a step in a pipeline is a
   label on a line, not a rounded rectangle with a fill. Rectangles are allowed only when the
   source shows containers (a table, a lock chamber, a database).
3. **One accent lights the story.** The accent (`--anim-accent`) marks what is active now, with
   a soft glow. Everything else is drawn in `--anim-line` and `--anim-muted`. Semantic colours
   (`--anim-ok`, `--anim-warn`, `--anim-danger`, `--anim-accent-2`) appear only where they
   carry a meaning stated on the slide (up/down, absorbed/released, good/bad), and at most two
   of them in one fragment.
4. **Quiet weight.** Strokes 2 to 3 px for structure at a 1920 stage, 4 to 5 px for the active path,
   dashed for weak or secondary links. Arrowheads small and open. Emphasis comes from colour
   and glow, not from thickness or size jumps.
5. **Type carries the hierarchy.** Label: `--anim-font`, 600 weight, 22 to 28 px at a 1920
   stage. Sub-label under it: `--anim-mono`, 400 weight, 18 to 20 px, `--anim-muted` (a term,
   a unit, a translation, a value). Numbers and key words that matter get the accent colour
   inline; nothing gets a pill. Titles belong to the slide, not to the fragment.
6. **Captions are a sentence, not a bar.** The narration line sits as plain text under the
   figure, centred, 24 to 28 px, with no background rect. Phase changes cross-fade the text.
7. **Mark what is illustrative.** Example values get a small outlined tag ("illustrative",
   2 px stroke in `--anim-line`, mono 18 px) in a corner of the figure, the same way every time.
8. **Glow, not shadow.** The active element may carry a soft glow: a second copy of the shape
   behind it with the accent colour at 25 to 35 % opacity and a 6 to 10 px blur
   (`filter: blur()` on the copy, or a wider stroke at low opacity). Nothing else glows.
9. **Motion is calm.** Enter with a 16 px rise and fade (600 ms, `cubic-bezier(.2,.7,.2,1)`),
   draw-on over 1.2 s, dim-not-hide for things that lose focus (opacity 0.35). No bounce, no
   scale beyond 1.05, no more than one thing arriving at a time unless they are a staggered
   series (80 ms apart).
10. **Both themes.** The same rules hold on a light background: lines get darker, the glow
    stays coloured, panels stay absent. Always render both before calling a fragment done.

## Tokens

Fragments use only `--anim-*` tokens (contract section 3). The fallbacks are the lean palette:
background `#0F1E27`, panel `#0D1820` (used only for the rare container), line `#2A3D49`,
foreground `#E6EDF0`, muted `#93A7B2`, accent `#34D1BF`, accent-2 `#FF8A3D`, ok `#8ED7AD`,
warn `#FFD15C`, danger `#FF6B6B`. Hosts retheme through `--anim-theme-*`.

## Under a host theme

When the deck keeps its own look (the **match** look, `scripts/host_theme.py --mode match`),
the host supplies the twelve token values and nothing else. Every principle above still holds:
a corporate deck full of rounded panels and coloured pills gets rings, labels on lines and
hairline brackets drawn in its blue and its font, not its panels redrawn in SVG. The test is
the before/after pair: if the resting frame looks like the old slide with the same boxes, the
fragment has copied the host's style instead of adopting its colours. On a white ground the
glow is the accent copy at about 30 % opacity with blur, lines go darker (`--anim-line` around
`#C3CFDC` on white), and the one accent is the brand's primary colour.

## Anatomy by archetype

- **pipeline**: steps are labels on a single horizontal line with small ring markers; the
  packet is a glowing dot; a passed step keeps its ring in `--anim-ok` with no check-box.
- **graph**: rings (r 32 to 44 at a 1920 stage) with an optional line glyph inside, labels
  outside (below or beside), wires 2 to 3 px, the active path 4 px accent with glow; groups as a hairline bracket
  with a small mono label, never a card.
- **timeline**: one axis line, dots on it, labels alternating above and below with a thin
  leader; eras as hairline brackets below.
- **states**: states are rings or glyphs; the token is a glowing dot; transitions are thin
  arcs with the label on the arc.
- **compare**: two or more columns separated by nothing but space (or one hairline); row
  labels in `--anim-muted` at the left; the verdict as a sentence below.
- **layers**: bands separated by hairlines, names at the left in mono caps; the traveller
  is a glowing dot.
- **chart**: axes 2 px in `--anim-line`, gridlines dotted at 40 % opacity, one series in the
  accent, reference lines dashed, events as small outlined tags on the trace; the value
  readout is inline text, not a card.

## Checklist before shipping

- [ ] Fewer than 4 fills in the whole fragment (excluding dots and glyphs).
- [ ] One accent, at most two semantic colours, each explained by the slide.
- [ ] Every label has room; nothing smaller than the text floor; sub-labels in mono muted.
- [ ] Caption is plain text; illustrative tag present if any number is an example.
- [ ] Rendered in dark and light; the resting frame is calm and complete.
