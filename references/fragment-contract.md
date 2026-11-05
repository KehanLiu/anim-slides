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
<div class="anim anim-<name>" data-anim="<name>" data-anim-cycle="12" data-anim-control="loop">
  <svg viewBox="0 0 W H" width="100%" height="100%" role="img" aria-label="one-sentence description">
    <!-- the illustration -->
  </svg>
</div>
```

- `<name>` is kebab-case, 2 to 24 characters, unique within the deck: `deploy-pipeline`, `db-failover`, `rag-flow`.
- `data-anim-cycle` is the loop length in seconds. `data-anim-control` is `loop` (default) or `step`.
- Exactly one `<svg>`. HTML text outside the SVG is not allowed; captions belong to the slide.
- Nothing else: no `<script>` (except the `step` variant, see section 7), no `<link>`, no `<image>`,
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
  --anim-bg:       var(--anim-theme-bg,       #0f1218);
  --anim-panel:    var(--anim-theme-panel,    #1a2030);
  --anim-line:     var(--anim-theme-line,     #3a4660);
  --anim-fg:       var(--anim-theme-fg,       #eef2f8);
  --anim-muted:    var(--anim-theme-muted,    #9aa7bd);
  --anim-accent:   var(--anim-theme-accent,   #4cc2ff);
  --anim-accent-2: var(--anim-theme-accent-2, #ffb454);
  --anim-ok:       var(--anim-theme-ok,       #3ecf8e);
  --anim-warn:     var(--anim-theme-warn,     #ffb454);
  --anim-danger:   var(--anim-theme-danger,   #ff5d5d);
  --anim-font:     var(--anim-theme-font,     system-ui, sans-serif);
  --anim-mono:     var(--anim-theme-mono,     ui-monospace, monospace);
}
```

- Inside the SVG use only `var(--anim-*)` for `fill`, `stroke`, `color`, `font-family`.
- Hosts override by setting `--anim-theme-*` once. A light theme is just different values.
- Opacity variants are made with `opacity` or `color-mix()`, not with extra hex literals.
- The checker flags any hex literal or named colour inside the fragment except in the token block.
  It does not check `font-family`; authors must still use `var(--anim-font)` / `var(--anim-mono)`.

## 4. Gating: animate only when shown

Animations must run only while the slide is on screen, so that ten slides do not animate at once
and so a presenter sees the start of the story. The fragment uses one **gate selector**, written as
an ancestor of the wrapper:

```css
.visible .anim-<name> .<name>-pulse { animation: <name>-pulse 12s ease-in-out infinite; }
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

## 6. Legibility and motion budget

- Text at or above 18 px **at rendered size on a 1920-wide stage**:
  `viewBox_text_px * rendered_width / viewBox_width >= 18`. Titles 22 px and up.
  On other stage sizes scale the floor by `stage_width / 1920` (12 px at 1280, 15 px at 1600,
  10 px at reveal.js 960, since the floor never goes below 10) and pass it as
  `check_fragment.py --min-text`. `check_fragment.py --rendered-width` computes the rendered size.
  The checker enforces the 18 px body floor, warns on titles under 22 px, and checks that
  `data-anim-cycle` lies in the 8 to 15 s range.
- Strokes 2 to 3 px at rendered size, round caps and joins, corner radius 4 to 8.
- At most three things moving at once; roughly one third of the elements active at a time.
- Cycle 8 to 15 s with setup, action, resolution and a hold of 1 to 2 s before the loop restarts.
- Entrances decelerate (`ease-out`), exits accelerate and take about 65 % of the entrance time.
- `linear` only for continuous motion (dashes, scrolling traces, spinners).
- Stagger total under 500 ms; a card's content lands 50 to 150 ms after the card.
- Respect `prefers-reduced-motion`: the fragment ends with
  `@media (prefers-reduced-motion: reduce) { .anim-<name> * { animation: none !important; } }`
  which shows the resting frame. A fragment without this block fails the check.

## 7. Control variants

- `loop` (default): CSS keyframes only, `infinite`, no script. Use for any illustration the
  presenter does not need to drive.
- `step`: the presenter advances phases with a key. The fragment adds one inline
  `<script type="module">` after the `<svg>` that builds a paused GSAP timeline with one
  `addLabel('<phase>')` per phase (the first at 0) and registers it under its name. It must work
  whether or not the host script has run yet, so it registers through the early-registration
  queue exactly as `scripts/snippets/step-host.html` documents:
  ```js
  var A = window.animSlides = window.animSlides || {};
  if (A.register) A.register('<name>', tl); else (A.q = A.q || []).push(['<name>', tl]);
  ```
  The deck host script (shipped as `scripts/snippets/step-host.html`) goes in `<head>`, after GSAP
  and before any fragment, as a classic script. It drains `animSlides.q` when it loads; if GSAP is
  missing it turns `register` into a harmless push onto that queue and leaves step control off.
  Hosts set the gate with `animSlides.gate = '<selector>'` after the snippet and never reassign
  `window.animSlides` itself. On Right/Space/PageDown and Left/PageUp the host tweens the
  timeline of the fragment inside the gate to the next or previous label (`tl.tweenTo`), `p`
  pauses or resumes, and at the last or first phase the key passes to the deck. GSAP is loaded once in the
  deck head (a local copy or a pinned CDN URL, as in `scripts/snippets/step-host.html`), never
  inside the fragment.
  Choose `step` only when the brief says so or when the story has four or more phases that each
  need narration.

## 8. Verification

A fragment is done when all three hold:

1. `scripts/check_fragment.py <name>.html --name <name> --rendered-width <px>` passes.
2. `scripts/render-phases.sh <dir> <W> <H> <t1> <t2> ... rest` produced PNGs and every PNG was
   **looked at** (image viewing tool), not inferred from the source. Fix clipping, overlap, unreadable
   text, empty panels. Iterate at least once.
3. The resting frame PNG reads as a complete still.

Headless screenshots never prove smoothness; check once in a real browser before shipping a deck.
