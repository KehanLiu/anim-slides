# Eval corpus: no ugly slides, no matter the input

These cases are trap inputs: small decks built to trip one known way the skill can go wrong:
a forced figure on a list, clipped German compounds, Chinese labels drawn as empty boxes,
faint lines on a white ground, a 4:3 stage treated as 16:9, fifteen dots crammed on one
axis, a twenty-node web drawn as spaghetti, actor icons dropped, a chart picture turned into
a sentence, an already animated deck rebuilt instead of switched. Each case says what a good
result looks like and carries graders that check it from the run's transcript and files.

The corpus is for the skill to test itself after a change to `SKILL.md`, `references/`,
`scripts/` or `pool/`: the run report shows which traps it still falls into.

## Cases

| Case | Trap | Mode |
|---|---|---|
| `bare-improve-html` | bare "improve the slides": one intake message, show before ask, once control | B |
| `bullets-twelve` | twelve unrelated facts must stay text | B, user absent |
| `dense-table` | 8 x 5 table of long cells: text floor, no clipping, no boxes | C |
| `chart-picture` | the chart is a PNG: redraw from its values, never a summary | C |
| `long-words-de` | long German compounds in a six-step pipeline | C |
| `cjk-labels` | Chinese timeline labels need a CJK-capable font | B, user absent |
| `light-theme-faint` | white host with line colour `#E6E6E6`: raise contrast, no glowing lines | B, user absent |
| `stage-4x3` | 1600 x 1200 stage: measure the slot, fit the viewBox | C |
| `timeline-fifteen` | fifteen dated events: split or group, 3 to 6 phase marks | B, user absent |
| `graph-twenty-nodes` | twenty-node food web: split or group under about 12 nodes | C |
| `icons-are-content` | compare columns labelled by actor icons: keep or redraw them | B, user absent |
| `already-animated-switch` | "make the figures play on click": Mode E, `--control step` only | E |

The Mode B cases other than `bare-improve-html` say "just do it" in the prompt: an eval run
cannot answer the intake question, so those cases test the default path (defaults recorded
under Decisions). `bare-improve-html` tests the intake itself; its run may end at the one
question, and its graders are written so that is a pass.

## Layout of a case

```
evals/<case>/
  prompt.md          frontmatter (tags, max_turns, timeout_seconds, allowed_tools) + the prompt as typed
  case.yaml          schema_version, name, expected_outcome, context.scaffold_script
  place-files.sh     copies files/ into the run's working folder (executable)
  files/             the input deck (deck.html, plus any picture or work folder it needs)
  graders/NN-*.md    one verifiable statement each (type llm, focus trace, weight 1)
```

## Run with the CLI

From the skill folder (each run is a full, billed Claude session; a full Mode B case takes
up to an hour):

```bash
claude plugin eval . --allow-tools Write,Edit,Bash --scaffold
claude plugin eval . --allow-tools Write,Edit,Bash --scaffold --runs 1 --case 'long-words-*'
claude plugin eval . --allow-tools Write,Edit,Bash --scaffold --runs 1 --tag mode-c
```

`--scaffold` is needed: it runs each case's `place-files.sh`, which puts the input deck in
the working folder. The default is 3 runs per case; `--runs 1` for a quick pass, `--case` or
`--tag` to pick cases, `-j 2` to run two at once. The first run asks you once to trust the
folder. Results and the HTML report go to `evals/results/` (ignored by git).

## Run one case by hand

1. Copy the case's input to a scratch folder: `cp -R evals/<case>/files/. /tmp/<case>/`.
2. Start a fresh session of your harness in that folder, with the skill installed, and type
   the prompt from `evals/<case>/prompt.md` (the line above "Input files").
3. When it finishes, check each statement in `evals/<case>/graders/` against the transcript
   and the files, and read `expected_outcome` in `case.yaml`.
4. Review the result by eye with `references/look-rubric.md`: a fresh reviewer that sees
   only the before and after PNGs. Any score below 3 is a failure of the case, even when all
   graders pass.

## Add a case

- **One trap per case.** Name it after the trap (lowercase, hyphens; not `results`, `files`
  or `mocks`). If a real run produced an ugly slide, reduce the input to the smallest deck
  that still produces it.
- **Synthetic input.** Write the deck yourself: invented but plausible content, no real
  company, no client material, no power-grid stories; vary the domain (biology, finance,
  civics, earth science, history). Keep it small (4 to 8 slides, one HTML file with
  `<section class="slide">`, a `.visible` current-slide class and `#N` hash navigation) so a
  run stays short. Pictures go next to the deck, not inline as base64.
- **Check the input.** Open the deck in a browser (or headless Chrome `--screenshot`) and
  run `python3 scripts/extract_slides.py evals/<case>/files/deck.html` to confirm the
  extractor sees the slides and the trap.
- **Verifiable graders.** Three to five, each one statement a reader can settle from the
  transcript and the files: a file exists, a script ran and printed 0 fail, a string is
  present or absent, a value is in a range. Name scripts by their repo names. Avoid taste
  words ("looks nice"); taste belongs to the look rubric.
- **Expected outcome.** Concrete: which slides change, which stay, what the figure keeps.
