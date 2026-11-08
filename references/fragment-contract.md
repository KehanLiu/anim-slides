# Fragment contract

Every animated illustration this skill produces is one **fragment**: a self-contained
piece of HTML that drops into any slide deck or web page. This file is the contract.
`scripts/check_fragment.py` enforces the mechanical parts.

## 1. Shape

One file `<name>.html` containing exactly two top-level things, in this order:

```html
<style>
  /* every selector scoped under .anim-<name>; every keyframe named <name>-... */
</style>
<div class="anim anim-<name>" data-anim="<name>" data-anim-cycle="8" data-anim-control="once"
     data-anim-phases="2,4.5,7">
  <svg viewBox="0 0 W H" width="100%" height="100%" role="img" aria-label="one-sentence description">
    <!-- the illustration -->
  </svg>
</div>
```

- `<name>` is kebab-case, 2 to 24 characters, unique within the deck: `deploy-pipeline`, `db-failover`, `rag-flow`.
- `data-anim-control` is `once` (default; also assumed when the attribute is absent), `step` or
  `loop` (section 7). `data-anim-cycle` is the pass length in seconds: 4 to 10 for `once` and
  `step`, 8 to 15 for `loop`.
- `data-anim-phases` lists the phase stop marks in seconds, comma-separated: strictly
  ascending, each above 0 and at most the pass length. Segment k runs from mark k-1 (0 for the
  first) to mark k; the last mark is where the hold starts (the figure is complete and nothing moves after it, so
  the frame at the last mark is the resting frame). The marks
  are the start seconds of every phase after the first. Required under `step`, validated under
  `once` when present; the scaffolder always writes it, so a fragment can switch control
  without a rebuild.
- Exactly one `<svg>`. HTML text outside the SVG is not allowed; captions belong to the slide.
- Nothing else: no `<script>` (under any control), no `<link>`, no `<image>`,
  no `<img>`, `<iframe>`, `<object>`, `<embed>` or `<foreignObject>`, no `href`/`xlink:href`/`src`
  that points outside the fragment (only `#id` references), no `url(...)` to external files,
  no `@import`, no `@font-face`.

## 2. Namespacing

- Every class and every id in markup and CSS starts with `<name>-`. The two wrapper classes
  `anim` and `anim-<name>` are the only exceptions.
- Every `@keyframes` name starts with `<name>-`.
- Every CSS selector starts with `.anim-<name>` or with `<gate> .anim-<name>` (section 4).
- Why: host decks have global rules like `.bar`, `.card`, `.node`, `.flow`, `.step`, `.label` and Chrome
  applies CSS `width`/`height` to SVG `<rect>`. Unprefixed classes have produced 1000 px stripes.

## 3. Theme tokens

Fragments never hard-code brand colours or fonts. They read CSS custom properties and declare
their own fallbacks on the wrapper, so a fragment looks right standalone and adopts the host theme
when the host defines the same variables on `:root` or on the slide.

```css
.anim-<name> {
  --anim-bg:       var(--anim-theme-bg,       #0F1E27);
  --anim-panel:    var(--anim-theme-panel,    #0D1820);
  --anim-line:     var(--anim-theme-line,     #2A3D49);
  --anim-fg:       var(--anim-theme-fg,       #E6EDF0);
  --anim-muted:    var(--anim-theme-muted,    #93A7B2);
  --anim-accent:   var(--anim-theme-accent,   #34D1BF);
  --anim-accent-2: var(--anim-theme-accent-2, #FF8A3D);
  --anim-ok:       var(--anim-theme-ok,       #8ED7AD);
  --anim-warn:     var(--anim-theme-warn,     #FFD15C);
  --anim-danger:   var(--anim-theme-danger,   #FF6B6B);
  --anim-font:     var(--anim-theme-font,     system-ui, sans-serif);
  --anim-mono:     var(--anim-theme-mono,     ui-monospace, monospace);
}
```

- Inside the SVG use only `var(--anim-*)` for `fill`, `stroke`, `color`, `font-family`.
- Hosts override by setting `--anim-theme-*` once. A light theme is just different values.
  `scripts/host_theme.py DECK.html --mode match|lean` writes that block (match: the deck's palette
  and fonts on `:root`; lean: the lean values plus the lean ground on `.anim-lean` slides) and
  `--apply` puts it between `<!-- anim-theme:start/end -->` markers in the deck head.
  `scripts/render-phases.sh --theme FILE` renders a fragment under such a block, so one fragment
  can be shown in both looks at intake.
- Opacity variants are made with `opacity` or `color-mix()`, not with extra hex literals.
- The checker flags any hex literal or named colour inside the fragment except in the token block.
  It does not check `font-family`; authors must still use `var(--anim-font)` / `var(--anim-mono)`.

## 4. Gating: animate only when shown

Animations must run only while the slide is on screen, so that ten slides do not animate at once
and so a presenter sees the start of the story. The fragment uses one **gate selector**, written as
an ancestor of the wrapper:

```css
.visible .anim-<name> .<name>-step { animation: <name>-step 8s linear 1 both; }
```

- Author fragments with the gate `.visible`. It is a convention, not a dependency.
- `scripts/integrate_fragment.py --gate '<selector>'` rewrites the gate at build time. Known values:

| Host | Gate selector |
|---|---|
| frontend-slides decks | `.visible` |
| reveal.js | `section.present` |
| impress.js | `.step.active` |
| Slidev | `.slidev-page.slidev-page-active` (or use the observer below) |
| plain scrolling page | `.visible` plus `scripts/snippets/observer.html` |
| always on (demo page) | `--gate none` removes the gate |

- Without the gate (and with `--gate none`) selectors must still work: the gate is a prefix, never a
  structural requirement.

## 5. Resting frame

The state **without** the gate is the resting frame. It must read as a finished still: the final
state of the story, all labels visible, nothing half-drawn. Decks export to PDF and PDF sees only
the resting frame. In practice: set the end-state values in the base rule, and let the keyframes
start `from` the empty state.

**Resting frame = finished state = 100 % keyframe.** Under `once` every track's 100 % stop
holds exactly the value of the base rule (or has no 100 % stop, which ends on the base value),
and `animation-fill-mode: forwards` (or `both`) keeps it there. The pass therefore ends on the
resting frame and nothing jumps, resets or restarts while the slide is up; the reduced-motion
still, the PDF page and the last frame of the pass are one and the same picture.

## 6. Legibility and motion budget

- Text at or above 18 px **at rendered size on a 1920-wide stage**:
  `viewBox_text_px * rendered_width / viewBox_width >= 18`. Titles 22 px and up.
  On other stage sizes scale the floor by `stage_width / 1920` (12 px at 1280, 15 px at 1600,
  10 px at reveal.js 960, since the floor never goes below 10) and pass the stage as
  `check_fragment.py --stage-width W` (or the floor itself as `--min-text`). `check_fragment.py --rendered-width` computes the rendered size.
  The checker enforces the 18 px body floor, warns on titles under 22 px, and checks that
  `data-anim-cycle` lies in the range of the control (once and step 4 to 10 s, loop 8 to 15 s).
- Strokes 2 to 3 px at rendered size, round caps and joins, corner radius 4 to 8.
- At most three things moving at once; roughly one third of the elements active at a time.
- **One pass (`once`, the default):** 4 to 10 s shaped as a single staggered reveal, the action,
  then a hold of 0.8 to 1.5 s on the finished state, which stays. No element moves twice unless
  the story needs it: a packet that travels its path once is fine, a pulse that repeats is not.
  No `infinite`, no iteration count above 1, no marching dashes.
- **Motion concurrency:** what counts is how many things move at the same instant, not how many
  tracks exist (one track per element is the normal shape). At most three at once; a staggered
  reveal counts as one. The checker warns above 3 and fails above 6.
- **Glow concurrency:** at most one glow visible at a time (a `filter: blur()`/`drop-shadow()`
  copy or a `*glow*` class); arrows and lines never glow (warn at 2, fail above 2).
- `loop` only: 8 to 15 s with setup, action, resolution and a hold of 1 to 2 s before it restarts.
- Entrances decelerate (`ease-out`), exits accelerate and take about 65 % of the entrance time.
- `linear` only for continuous motion (dashes, scrolling traces, spinners).
- Stagger total under 500 ms; a card's content lands 50 to 150 ms after the card.
- Respect `prefers-reduced-motion`: the fragment ends with
  `@media (prefers-reduced-motion: reduce) { .anim-<name> * { animation: none !important; } }`
  which shows the resting frame. A fragment without this block fails the check.

## 7. Control variants

- `once` (default): CSS keyframes only, no script. Every gated animation has
  `animation-iteration-count: 1` (no `infinite`) and `animation-fill-mode: forwards` or `both`,
  and its 100 % keyframe equals the resting frame (section 5). One track per element spans the
  whole pass: `animation: <name>-x 8s linear 1 both`, timing as keyframe percentages, no
  `animation-delay`. The pass starts when the gate class arrives, so it plays once each time the
  slide becomes current: reveal.js `section.present`, the `.visible` toggle of frontend-slides
  decks and `scripts/snippets/observer.html` all remove the gate when the slide is left and add
  it again on return, so a presenter who goes back sees the pass once more, then the still.
  Use `once` for every slide illustration unless the deck's control is `step` or the user asks
  for a loop.
- `loop`: CSS keyframes, `infinite`, no script. Only when the user asks for a continuous loop
  (a kiosk screen, a gallery card, a hero banner); 8 to 15 s with a hold before the reset.
- `step`: the presenter lands each phase with a click. **The fragment is the same file as
  under `once`**: the same CSS keyframes, full-pass tracks, iteration count 1, fill
  `forwards`/`both`, the 100 % keyframe equal to the resting frame, gated on the gate class, no
  script. Only the wrapper differs: `data-anim-control="step"` and a required
  `data-anim-phases` (section 1). The host plays the pass in segments:
  `scripts/snippets/step-host.html`, a small plain script between the markers
  `<!-- anim-slides:step-host:start -->` and `<!-- anim-slides:step-host:end -->`, sits once
  in `<head>` before any fragment (`integrate_fragment.py --control step` puts it there, sets
  the gate and replaces it on a later run). Through the Web Animations API it holds every CSS
  animation inside a step wrapper paused at 0. When the slide first becomes current it plays
  segment 1 by itself, so the figure draws on with the slide. Each forward key (Right, Space,
  PageDown) plays the next segment and stops on its mark; during a segment a forward key jumps
  to that mark. A backward key (Left, PageUp) snaps to the previous mark without motion. At the
  last mark a forward key passes to the deck, at the first mark a backward key passes to the
  deck, so the snippet consumes a key only while a phase remains. The phase reached is kept
  when the presenter leaves the slide and comes back (as reveal.js fragments do; leaving
  mid-segment lands on that segment's mark). Several step
  wrappers on one slide advance together. Under reduced motion nothing animates and every key
  passes through; printing shows the resting frame. `animSlides.gate` may be set after the
  snippet (default `.visible`).
  `once` versus `step` is decided once per deck at intake, not per fragment: a deck that
  already builds by click (the extractor's `builds`) is recommended `step`, others `once`.
  Because the file is identical, the switch is a re-run of `integrate_fragment.py --control`.

## 7b. Edge paths (scaffolded fragments)

The scaffold writes each wire's path once, as a CSS custom property on the fragment
(`--<name>-e-<from>-<to>: path("...")`), and packets ride it with `offset-path: var(...)`.
The wire itself still needs its `d` attribute (Safari cannot read `d` from a variable), so a
hand reroute changes `d`, its `-hl` highlight copy and that one variable.

## 8. Verification

A fragment is done when all four hold:

1. `scripts/check_fragment.py <name>.html --name <name> --rendered-width <px> --stage-width <W>` passes.
   Besides sections 1 to 6 it checks the control (`--control once|loop|step` overrides the
   wrapper; no `data-anim-control` means `once`):
   - `once`: FAIL on any `infinite` in the style, on a gated animation without fill-mode
     `forwards`/`both`, on an iteration count above 1, on `data-anim-cycle` outside 4 to 10 s;
     WARN when a track's last opacity differs from the resting frame's.
   - `step`: the `once` checks, plus a required `data-anim-phases` (ascending, above 0, at most
     the pass); under `once` the attribute is validated when present.
   - `loop`: `data-anim-cycle` 8 to 15 s.
   - all controls, measured by sampling the pass every 20 ms (duration, positive delay,
     iteration count and fill mode resolved per animation):
     - motion concurrency: an element is moving while it sits between two consecutive keyframe
       stops whose declarations differ. An interval where opacity rises from 0 (optionally with
       a settling transform) and nothing else changes is an **appear**; all appears active at
       one instant count as one thing together, so a staggered reveal counts as one. Every other
       moving element is an action and counts once; opacity-only swaps inside the same group
       (stacked status copies of one node) count once for that group, and a track on a `<g>`
       counts once however many children it carries. Concurrency = actions + 1 if anything is
       appearing. WARN above 3, FAIL above 6: "N things move at once at t=X s; at most three,
       or a staggered series".
     - glow concurrency: a glow element has `filter: blur()`/`drop-shadow()` or a class
       containing `glow`; it is visible while its own and its ancestors' opacity is above 0
       (static opacity for the whole pass, fill `forwards` after it). WARN above 1, FAIL above
       2: "N glows visible at once at t=X s; one glowing element at most". A stroke-only glow
       (a `<line>`, `<polyline>` or a `fill="none"` path) warns: "lines and arrows never glow".
     - an info line gives the number of distinct animation names (not a check).
2. `scripts/render-phases.sh <dir> <W> <H> <t1> <t2> ... <pass> rest` produced PNGs (under
   `step` render each phase mark; for `once` and `step` include one time at or past the pass length: it must be identical to `rest`) (in the temp folder it prints) and every PNG was
   **looked at** (image viewing tool), not inferred from the source. Fix clipping, overlap, unreadable
   text, empty panels. Iterate at least once.
3. The resting frame PNG reads as a complete still.
4. `scripts/verify_facts.py <name>.html --source <outline.json> --slide <N>` passes and every WARN
   was reviewed ([accuracy.md](accuracy.md)).

Headless screenshots never prove smoothness; check once in a real browser before shipping a deck.
