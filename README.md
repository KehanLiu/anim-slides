# anim-slides

An agent skill that turns boring slides into animation-rich HTML, and turns written processes
and dependencies into animated diagrams. It uses the open
[Agent Skills](https://agentskills.io) format, so the same folder works in Claude Code, Codex,
Cursor, GitHub Copilot, Gemini CLI and Antigravity, OpenCode, Amp, Cline, Roo Code, Kiro,
Factory Droid, Zed, Goose and Devin Desktop.

Give it a PowerPoint, an HTML deck, or a document that describes a pipeline, a dependency
graph, a timeline, a state machine, a comparison or an architecture. It finds the slides worth
illustrating, writes a spec and a brief for each, builds a self-contained animated SVG
fragment, renders phase frames with headless Chrome and looks at them, and inlines the result
into your deck.

## What you get

Each illustration is one **fragment**: a `<style>` plus one inline `<svg>` in a single HTML file.

- **Drop-in.** Works in reveal.js, impress.js, Slidev, frontend-slides decks, hand-written HTML
  and plain scrolling pages. No framework, no build tool, no dependency.
- **Themed by variables.** Fragments read `--anim-theme-*` CSS variables and carry neutral
  fallbacks, so one `:root` rule rethemes every illustration to your brand.
- **Safe to paste.** Every class, id and keyframe is prefixed, so nothing collides with the deck's
  own CSS.
- **Plays only when shown.** Animations are gated on the active slide and the resting frame is
  the finished state, so PDF export and reduced-motion users get a complete still.
- **Two control modes.** `loop` (default, CSS only) for self-running stories; `step` (GSAP
  timeline with labels) when the presenter wants to advance phases with a key.
- **Verified by looking.** The skill renders phases of the cycle to PNG and inspects them before
  it calls anything done.

## Install

The skill is one folder (`SKILL.md`, `references/`, `scripts/`, `examples/`). Any harness that
reads the Agent Skills format picks it up from its skills directory; the folder name must stay
`anim-slides`.

### Option A: the `skills` installer (any harness)

[`skills`](https://github.com/vercel-labs/skills) detects the agents on your machine, keeps one
copy in `.agents/skills/anim-slides` (or `~/.agents/skills/` with `-g`) and links each agent's
own folder to it. Needs Node.js 22.20+.

```bash
npx skills add KehanLiu/anim-slides              # this project, agents detected on your machine
npx skills add KehanLiu/anim-slides -g -y        # for your user, all detected agents, no prompts
npx skills add KehanLiu/anim-slides -g -a codex cursor github-copilot -y   # chosen agents only
npx skills add KehanLiu/anim-slides --list       # show what would be installed
```

Amp has its own equivalent: `amp skill add KehanLiu/anim-slides` (`--global` for your user).
Gemini CLI: `gemini skills install https://github.com/KehanLiu/anim-slides --scope user`.

### Option B: clone into a skills folder

```bash
git clone https://github.com/KehanLiu/anim-slides <skills-dir>/anim-slides
```

`<skills-dir>` per harness (project path, then user path). A symlink to a clone elsewhere works
everywhere except inside a Claude Code plugin.

| Harness | Project | User |
|---|---|---|
| Codex, Cursor, Copilot, OpenCode, Amp, Roo Code, Droid, Zed, Goose, Devin Desktop, Antigravity (project) | `.agents/skills/` | `~/.agents/skills/` |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Cursor (own folder) | `.cursor/skills/` | `~/.cursor/skills/` |
| GitHub Copilot (own folder) | `.github/skills/` | `~/.copilot/skills/` |
| Gemini CLI | `.gemini/skills/` or `.agents/skills/` | `~/.gemini/skills/` |
| Antigravity (user) | `.agents/skills/` | `~/.gemini/config/skills/` |
| OpenCode (own folder) | `.opencode/skills/` | `~/.config/opencode/skills/` |
| Cline | `.cline/skills/` | `~/.cline/skills/` |
| Kiro | `.kiro/skills/` | `~/.kiro/skills/` |
| Factory Droid (own folder) | `.factory/skills/` | `~/.factory/skills/` |
| Devin Desktop (own folder) | `.devin/skills/` | `~/.config/devin/skills/` |

Most of these also read `.claude/skills/`, so a single clone there often serves several tools.
Install one way per machine: two copies with the same name shadow each other.

### Option C: Claude Code plugin (the repo is its own marketplace)

```bash
claude plugin marketplace add KehanLiu/anim-slides
claude plugin install anim-slides@anim-slides-marketplace
```

or `/plugin marketplace add KehanLiu/anim-slides` then `/plugin install anim-slides@anim-slides-marketplace`
inside a session. Update with `claude plugin marketplace update anim-slides-marketplace` and
`claude plugin update anim-slides@anim-slides-marketplace` (auto-update is off for third-party
marketplaces). For a one-off trial from a local clone: `claude --plugin-dir ./anim-slides`.

### Requirements for the scripts

Python 3.9+ and a Chrome or Chromium binary (for phase rendering). Optional: `pyyaml` for full
YAML in specs (a built-in reader covers plain specs like the examples, and JSON always works), and
`python-pptx` for richer PowerPoint extraction (a zip/XML fallback is built in). The harness must
be able to run shell commands and view PNG files; the scripts are called by their path inside the
skill folder, which Claude Code exposes as `$CLAUDE_SKILL_DIR` and other harnesses report when
they load the skill.

## Use

With the skill installed, ask your agent in plain words:

- "Make the pipeline slide in `deck.html` an animated illustration."
- "Convert `talk.pptx` to HTML and animate the process and architecture slides."
- "Here is our release procedure (paste). Turn it into an animated diagram for slide 7."
- "Animate this Mermaid flowchart for a 1200x600 slot."

The skill follows `SKILL.md`: intake and triage, spec, brief, build, verify, integrate, audit.
Harnesses pick it up automatically from its description; to call it by name use `/anim-slides`
(Claude Code, Cursor, Copilot, Kiro, Droid, Antigravity, Devin Desktop), `$anim-slides` (Codex),
or ask for it by name where the agent loads skills through a tool (OpenCode, Zed, Goose, Gemini
CLI).

### Scripts you can also run yourself

```bash
# outline a deck with archetype suggestions per slide
python3 scripts/extract_slides.py deck.pptx -o outline.json

# spec -> skeleton fragment
python3 scripts/scaffold_from_spec.py anim/deploy/spec.yaml -o anim/deploy/deploy.html

# contract checks (prefixes, tokens, gating, text size at rendered width)
python3 scripts/check_fragment.py anim/deploy/deploy.html --name deploy --rendered-width 1200

# phase frames at 1.5 s, 4 s, 7 s, 10 s plus the resting frame, and a contact sheet
scripts/render-phases.sh anim/deploy 1200 600 1.5 4 7 10 rest

# inline into a deck: markup goes between <!-- anim:NAME:start --> / <!-- anim:NAME:end -->,
# style into the head between <!-- anim-style:NAME:start --> / <!-- anim-style:NAME:end -->;
# re-runs replace both blocks, --dry-run prints a summary without writing
python3 scripts/integrate_fragment.py deck.html anim/deploy/deploy.html --name deploy \
  --anchor '<section id="release">' --gate section.present --backup
```

## How it works

```
deck.pptx / deck.html / docs.md / mermaid
        │  extract_slides.py + triage         (references/input-stage.md)
        ▼
  spec.yaml   nodes, edges, groups, phases     (references/spec-format.md)
        │  scaffold_from_spec.py + archetype recipe (references/archetypes.md)
        ▼
  <name>.html  one fragment, CSS keyframes    (references/fragment-contract.md)
        │  check_fragment.py, render-phases.sh, look at the PNGs
        ▼
  deck.html    integrate_fragment.py, gate rewritten for the host
```

## Theming

```css
:root {
  --anim-theme-bg: #0f1218;  --anim-theme-panel: #1a2030;  --anim-theme-line: #3a4660;
  --anim-theme-fg: #eef2f8;  --anim-theme-muted: #9aa7bd;
  --anim-theme-accent: #4cc2ff;  --anim-theme-accent-2: #ffb454;
  --anim-theme-ok: #3ecf8e;  --anim-theme-warn: #ffb454;  --anim-theme-danger: #ff5d5d;
  --anim-theme-font: system-ui, sans-serif;  --anim-theme-mono: ui-monospace, monospace;
}
```

These values equal the built-in fallbacks, so a host only overrides what differs.

## Repository layout

```
SKILL.md                 workflow and rules the agent follows (Agent Skills format)
agents/openai.yaml       optional Codex metadata; other harnesses ignore it
.claude-plugin/          marketplace manifest for the Claude Code plugin install
references/              contract, spec format, archetypes, input stage, brief, layouts, motion rules, lessons
scripts/                 extract, scaffold, check, render, integrate; host snippets
examples/                two finished fragments and five example specs
docs/                    design notes and history
```

## Background

This skill grew out of building about a dozen animated illustrations for a lecture deck, by
hand, in autumn 2026. The repeated loop (brief, build, render phases, look, fix, integrate) and
the gotchas it surfaced are written up in `docs/design-notes-2026-11-01.md`.

## License

MIT, see `LICENSE`.
