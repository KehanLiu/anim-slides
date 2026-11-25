# One slide, the short path

For "animate slide N" (Mode C). This page replaces Phases 1 to 3 of `SKILL.md` for that one
slide: no intake message, no brief, no previews, no review page, no review agents. Read no
other reference file unless a checker names a rule you need to look up, and do not read the
scripts or their `--help`: the commands below are complete. Aim for about ten tool calls and
one Write for the figure. `S` is `<skill-dir>/scripts`.

## 1. Read (one command)

Print the slide's markup and the deck's `<style>` in one go, and note: the stage size, the
ground and text colours, the font, the accent, the class the deck puts on the current slide
(`active`, `current`, `present`, `visible`), and the slide's free box under its heading.

## 2. Decide (four lines, no file reading)

Write `anim/triage.md` with four lines only: **Question** (what the audience must answer from
this slide), **Insight** (what the picture shows that the text hides), **Form** (the drawing)
and **Verb** (the one motion). The form follows the content:

| The slide holds | Draw | Verb |
|---|---|---|
| durations | bars from one start line on one time axis, built by the spec (step 3) | `race` |
| shares of a whole, or parts that add up to one total | one bar (or ring) cut into parts at true size, every part filled and labelled on or right beside its part; never one bar per row | `split` |
| steps in order, a branch or loop | a row of steps on one line; the branch leaves the line where it happens | `reveal`, `switch` |
| a table with one row or column that matters | the table kept, one bar per row for the column that matters, the row that matters lit | `grow` |
| parts and what contains or feeds what | nested outlines and arrows in the direction the source states | `nest`, `travel` |
| dated events | one axis to scale, each event at its date | `trace` |
| options with long labels and a number each | the labels kept as the slide writes them, one bar per option | `grow` |

A slide with nothing to draw (a title, a quote, one picture) ships unchanged with the reason.

## 3. Build (one Write, or one spec)

- **Durations:** write `anim/<name>/spec.yaml` (`archetype: durations`, each bar's label and
  value as the slide writes them, `status: real|illustrative`, the slide's takeaway sentence
  as `claim:`) and run
  `python3 $S/scaffold_from_spec.py anim/<name>/spec.yaml -o anim/<name>/<name>.html --rendered-width <slot px>`.
  The output is final. Schema: the "Durations" section of `spec-format.md`, only if needed.
- **Everything else:** write `anim/<name>/<name>.html` in one go, to this contract:

```html
<style>
.anim-NAME{ --anim-bg:var(--anim-theme-bg,#0F1E27); --anim-panel:var(--anim-theme-panel,#0D1820);
  --anim-line:var(--anim-theme-line,#56707F); --anim-fg:var(--anim-theme-fg,#E6EDF0);
  --anim-muted:var(--anim-theme-muted,#93A7B2); --anim-accent:var(--anim-theme-accent,#34D1BF);
  --anim-accent-2:var(--anim-theme-accent-2,#FF8A3D); --anim-ok:var(--anim-theme-ok,#8ED7AD);
  --anim-warn:var(--anim-theme-warn,#FFD15C); --anim-danger:var(--anim-theme-danger,#FF6B6B);
  --anim-font:var(--anim-theme-font,system-ui,sans-serif);
  --anim-mono:var(--anim-theme-mono,ui-monospace,Menlo,monospace);
  display:block;width:100%;height:100% }
.anim-NAME svg{display:block;width:100%;height:100%}
.anim-NAME .NAME-label{font-family:var(--anim-font);font-size:30px;fill:var(--anim-fg)}
@keyframes NAME-grow{0%{transform:scaleX(0)}10%{transform:scaleX(0);animation-timing-function:cubic-bezier(0.16,1,0.3,1)}40%{transform:scaleX(1)}100%{transform:scaleX(1)}}
.visible .anim-NAME .NAME-bar{animation:NAME-grow 7s linear 1 both}
@media (prefers-reduced-motion: reduce){ .anim-NAME *{animation:none !important} }
</style>
<div class="anim anim-NAME" data-anim="NAME" data-anim-cycle="7" data-anim-control="once"
     data-anim-phases="2,4.5,6" data-anim-verb="grow">
<svg viewBox="0 0 W H" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="one sentence that tells the story">
  <g data-anim-focal> … the one element the eye should land on … </g>
</svg>
</div>
```

  The rules the checker enforces, so that it passes the first time:
  - every class, id and keyframe starts with `NAME-`; every selector starts with `.anim-NAME`
    or `.visible .anim-NAME`; colours only through the twelve `--anim-*` tokens; no script, no
    image, no link, no HTML text inside the fragment;
  - every animation rule sits under `.visible`, runs once (`1 both`) on one clock (the same
    duration everywhere, timing inside the keyframe percentages), with
    `cubic-bezier(0.16,1,0.3,1)` to enter and `linear` only for motion that tracks time or scale;
  - the viewBox is the slot at stage scale (one unit = one stage pixel), so 18 px is the
    smallest text and the slide's own body size is the normal label size;
  - the pass is 4 to 8 s, at most three things move at once, everything is drawn by 5 s, a
    short stillness comes before the last step, nothing loops or pulses, and the frame at the
    end is complete: every value has its filled shape and its label;
  - exactly one `data-anim-focal`, one accent, the accent only on what the Insight is about;
  - values drawn as lengths, areas or positions are to scale, from zero, on one scale.
  - no line, bracket or guide runs through text, and no label touches another: leave 12 px.

## 4. Keep every label

Every text run of the source slide stays on the animated slide word for word: the heading,
table headings, each label at full length, each value with its unit as written. Draw around
the words, do not rewrite them. When a label is too long for the figure, keep the slide's own
text block and put the figure beside or under it. Nothing is added except the figure's own
arithmetic (a total, a difference, a ratio) and a short axis note.

## 5. Put it in and check (three commands)

```bash
cp deck.html deck-animated.html        # or the output name the user gave
python3 $S/host_theme.py deck-animated.html --mode match --apply deck-animated.html
python3 $S/integrate_fragment.py deck-animated.html anim/<name>/<name>.html --name <name> \
    --anchor '<unique string before the replaced block>' --replace-until '<unique string after it>' \
    --gate '<the deck's current-slide selector, e.g. .slide.active>'
python3 $S/check_fragment.py anim/<name>/<name>.html --name <name> --rendered-width <slot px> \
  && python3 $S/check_labels.py deck.html deck-animated.html --slide N \
  && python3 $S/check_look.py --page deck-animated.html --slide N --at-marks
```

Give the slot a fixed size on the slide (`style="width:…px;height:…px"` on the wrapper you
pass with `--wrap`), so the figure fills the free box. Fix every FAIL and run the line again;
two rounds at most, then report what is left. WARN lines are read once and fixed only when
they name a real defect on this slide.

## 6. Look once

Render two frames in one command
(`GATE=<current-slide class, e.g. active> bash $S/render-phases.sh --out anim/shots --page deck-animated.html --slide N 1920 1080 <mid second> rest`)
and open both pictures, once. Check three things: the answer to the Question can be pointed at in
the resting frame, nothing overlaps or is clipped, and the mid frame shows the motion doing
what the Verb says. Fix what fails, once.

## 7. Hand over (five lines)

What the slide now shows; what was replaced and what was kept; that the checks pass (or what
is left); that the motion was seen only as still frames; where the file is. No offers, no
switches, no review page.
