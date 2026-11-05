# anim-slides: skill gap analysis and design notes (historical)

> Written 2026-11-01, before most of this repository existed, after building about a dozen
> animated illustrations for a lecture deck by hand. It is kept as history and as the rationale
> behind the skill. The current workflow is in `SKILL.md` and `references/`; where this note
> disagrees with those files, those files win.

## 1. What the job actually was

"Replace boring text blocks and ugly screenshots in an HTML slide deck with
animated illustrations that explain the content."

Each illustration went through the same loop:

1. **Brief**: subject, composition, phases with timings, slot size on the slide
   (viewBox), palette, fonts, class-prefix rule, "only animate under `.visible`".
2. **Build**: one HTML fragment = `<style>` + `<div class="anim anim-<name>">`
   wrapping one inline `<svg>`; CSS keyframes only, no scripts, no external files.
3. **Verify**: render 4 to 8 phases of the cycle with headless Chrome
   (negative `animation-delay` + `animation-play-state: paused`), look at every
   PNG, fix clipping/overlap/unreadable text, iterate at least once.
4. **Integrate**: hoist the `<style>` into the deck head, namespace every class,
   drop the fragment into a slide slot, re-check in a real browser.

Steps 1, 3 and 4 were repeated by hand for every illustration. That repetition is
the skill gap.

## 2. Skills available at the time

| Skill | Covers | Does not cover |
|---|---|---|
| `frontend-slides` (zarazhangrui, MIT) | Building an HTML deck, entrance effects, PPTX conversion | Diagram-style illustrations with a story, verification of motion |
| `gsap-*` (GreenSock, official) | GSAP API: timelines, labels, stagger, DrawSVG, MorphSVG, MotionPath | Nothing about slides, briefs, or verification; assumes a JS library in the page |
| `motion-design` (LottieFiles) | Timing/easing tables, choreography, 1/3 rules, quality checklist | Framework-agnostic principles only, no production workflow |

None of them: write a structured animation brief, enforce class namespacing
inside a host document, render and inspect phases of a CSS animation, or know
the slot geometry of a given deck.

## 3. The gap, concretely

1. **Brief template.** The quality of the fragment tracked the quality of the
   brief one-to-one. The brief must fix: viewBox and rendered size, phases with
   second marks, cycle length, resting frame, palette, fonts, min text size,
   class prefix, `.visible` gating. See `references/brief-template.md`.
2. **Namespacing.** A fragment that uses `.bar`, `.flow`, `.tag`, `.card`,
   `.node`, `.chip` collides with the deck's own CSS. Chrome applies CSS
   `height`/`width` to SVG `<rect>`, so a deck rule like `.bar { height:100% }`
   produced 1000 px stripes on two slides. Rule: prefix every class with
   `<name>-` in both markup and CSS. `scripts/integrate_fragment.py` does it
   mechanically as a safety net.
3. **Phase rendering.** Headless Chrome screenshots of CSS animations are not
   deterministic: compositor animations (transform, opacity) and main-thread
   animations (stroke-dashoffset, stroke colour) sample at different times, and
   `--virtual-time-budget` makes it worse. The reliable method is a copy of the
   preview with `* { animation-delay: -Ns !important; animation-play-state: paused !important }`.
   `scripts/render-phases.sh` does this.
4. **Slot geometry.** Each slide layout has a known free box; measure it rather
   than guess, so the brief can state the viewBox. See `references/layouts.md`
   (measuring plus generic layouts replaced the slot table proposed here).
5. **Verification by looking.** The agent must open the PNGs with the image
   reader and fix what it sees. Reading the SVG source is not enough. Every
   fragment that was "verified" only by reading code had an overlap.
6. **Resting frame.** The deck exports to PDF; the non-animated state of every
   fragment must read as a complete still (final state, not the empty start).
7. **Parallelism.** Independent fragments were built by parallel subagents
   from the same shared brief, then integrated in one pass. The skill should
   say so explicitly: one subagent per illustration, a shared `BRIEF.md`,
   integration in the main thread.

## 4. Lessons learned (put these in the skill)

- Keep all text in a fragment at or above 18 px *at rendered size*. Compute
  from viewBox scale, not the viewBox number.
- Use `pathLength="100"` (or 1000) on paths that draw on, so dasharray maths is
  the same for every path.
- Prefer stacked `<text>` elements that cross-fade over animating text content.
- Animating `transform` on a `<clipPath>` child does not repaint reliably in
  Chrome; animate a cover rect or the clip rect's `width` instead.
- When lines attach to a shape that later splits or moves in parts (a bar, a
  group), end each line inside the part it belongs to so the split needs no
  re-attachment.
- Use `offset-path` for packets along wires; it is CSS-only and smooth.
- Linear easing is right for continuous loops (dashes, scrolling traces,
  spinners) and wrong for spatial moves with a start and end.
- Exits should accelerate and take ~65 % of the entrance time.
- Follow-through: content inside a card lands 50 to 150 ms after the card.
- Anything that loops longer than 5 s needs a pause key for the presenter.
- Never trust `--virtual-time-budget` for CSS animation frames.
- A headless screenshot never proves smoothness; check once in a real browser.

## 5. Where GSAP fits

The deck stays dependency-free and CSS-only, which is fine for loops that the
presenter does not need to control. GSAP earns its 70 KB when a fragment needs
runtime control: step through phases on a key press (timeline labels),
pause/seek, morph shapes (MorphSVG), or draw complex paths (DrawSVG). The note
proposed two fragment templates, `css` and `gsap`.

What shipped instead: one fragment shape with `data-anim-control="loop"` (default,
CSS keyframes only) or `data-anim-control="step"` (one paused GSAP timeline with
a label per phase). The host advances phases with `tl.tweenTo(label)` through
`scripts/snippets/step-host.html`. See `references/fragment-contract.md`.

## 6. Proposed skill structure (as proposed then)

```
anim-slides/
  SKILL.md                     workflow, rules, when to use
  references/brief-template.md the brief every fragment starts from
  references/motion-rules.md   motion rules (easing, durations, stagger budget)
  references/slot-sizes.md     free boxes per slide layout (became layouts.md)
  references/lessons.md        the gotchas above, kept growing
  scripts/render-phases.sh     fragment + viewBox -> phase PNGs
  scripts/integrate_fragment.py namespace classes, hoist <style>, insert into a slide
  scripts/check_fragment.py    static checks: no script, prefixes, .visible gating, text size
  pool/db-failover/            sequence-heavy reference
  pool/latency-trace/          strip-chart reference (continuous trace with baked events)
```

Added since: `references/fragment-contract.md`, `spec-format.md`, `archetypes.md`,
`input-stage.md`; `scripts/extract_slides.py`, `scripts/scaffold_from_spec.py`,
`scripts/snippets/`; `pool/*/spec.yaml`. The "no script" rule now has one exception:
step mode allows one module script.

## 7. Open questions (resolved)

- *Should the skill own the slide layout too?* No. It measures the slot but does
  not own the slide layout (`references/layouts.md`).
- *Should presenter step-through be the default for story animations?* No. Loop
  is the default; step is opt-in.
- *Should fragments live as separate files next to the deck and be inlined at
  build time?* Yes. Fragments live in `anim/<name>/` next to the deck and are
  inlined idempotently by `scripts/integrate_fragment.py`.

## 8. Using the scripts

```bash
# static checks (prefixes, gating, text size at the rendered width)
python3 scripts/check_fragment.py anim/<name>/<name>.html --name <name> --rendered-width 1200
# phase frames: seconds into the cycle, plus the resting frame
scripts/render-phases.sh anim/<name> 1200 600 1.5 4 7 10 rest
# integrate into a deck slide (anchor = unique string in that slide)
python3 scripts/integrate_fragment.py deck.html anim/<name>/<name>.html --name <name> \
  --anchor '<section id="release">' --gate section.present --backup
```
