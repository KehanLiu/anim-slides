# First slide: bare session vs session with anim-slides

Date: 2026-11-24. Question: a first-time user has one slide. What does one neutral prompt produce with and without the skill, in fresh headless sessions that use the same model and the same tools?

## Setup

| Item | Value |
|---|---|
| Harness | Claude Code CLI 2.1.331 (`claude_code_version` in both init events) |
| Model | `--model opus`, resolved to `claude-opus-5-5` (init event `model` and every assistant message in both transcripts) |
| Skill under test | anim-slides 0.13.0, commit 4034476, taken with `git archive HEAD` (uncommitted work in the worktree is not in the copy) |
| Source slide | `examples/first-slide/source.html` (unchanged) |
| Prompt | `examples/first-slide/prompt.txt` (unchanged, one line, does not name the skill): "Turn the slide in source.html into an animated diagram that explains it. Write one self-contained HTML file, result.html, that opens from disk." |
| Turns | One prompt, no follow-up. First output kept as written. |
| Timeout | 60 minutes per arm. Neither run reached it. |
| Runs | Both arms started at 21:30:23 (+01:00), in parallel, as background processes |

Each arm ran in its own new directory that held only `source.html` (the skill arm also held `.claude/skills/anim-slides`). The runner is `harness/runarm.py`. Exact command, identical in both arms, with the working directory set to the arm's folder and stdin closed:

```
claude -p "$(cat prompt.txt)" \
  --model opus --output-format stream-json --verbose \
  --setting-sources project,local --strict-mcp-config \
  --permission-mode bypassPermissions
```

`claude` here stands for the CLI binary itself, called by its full path, not through a shell function or alias.

### Isolation

This follows an earlier private harness, which used `--setting-sources project,local`. Nothing in `~/.claude` was modified.

- `--setting-sources project,local` leaves out user settings. With it, the user-level skills in `~/.claude/skills` (among them anim-slides and frontend-slides) and the user's `CLAUDE.md` are not loaded. User-enabled plugins and their skills are not loaded either.
- `--strict-mcp-config` with no `--mcp-config` removes all MCP servers (`mcp_servers: []` in both init events).
- The earlier harness also passed `--disable-slash-commands` in the bare arm. That flag was not used here, because it also removes the built-in skills, and the two arms would then differ in more than the one skill.

Evidence comes from the `system/init` event of each transcript (line 1 of each raw transcript; the raw transcripts are kept out of git, see Limits). See also `harness/transcript-stats.txt`.

- bare `skills`: deep-research, design, design-sync, dataviz, update-config, verify, debug, code-review, simplify, batch, fewer-permission-prompts, doctor, claude-approvals, loop, schedule, claude-api, workflow-authoring, run, run-skill-generator, plugin-authoring. These are all built into the CLI. None is anim-slides, frontend-slides, gsap or motion-design.
- skill `skills`: `anim-slides` plus exactly the same 20 built-in skills.
- `plugins` (both arms): cc-plugin-agents-md, cc-plugin-telemetry, cc-plugin-privacy, cc-plugin-plugin-authoring (built in).
- `tools`: the same list in both arms.
- The bare session invoked no skill. The skill session invoked `Skill {"skill": "anim-slides"}` as its first tool call.

Two cheap probe sessions (model haiku; their transcripts are kept out of git) ran with the same flags. Each was asked whether its instructions contain two strings that occur only in the user's global instruction file. Both answered no, and both listed their skills: anim-slides was visible only in the skill probe. That answer is the model's self-report and is weaker evidence than the init event.

Built-in skills that might bear on the task were visible in both arms: `design`, `dataviz`. Neither session invoked them.

### Removed pool entry

For this run only, the copy of the skill under test had `pool/parcel-route/` deleted, and its entries removed from `pool/index.yaml` and `pool/README.md`. That pool entry is a finished animated figure of this same slide, and the session could otherwise have copied it. The entry is still in the repository's pool; only the test copy lacked it.

The name `parcel-route` still appears as an example in the copy's `references/motion-verbs.md` (line 266) and `references/archetypes.md` (line 44). Those two lines were left as committed.

The skill session named its fragment `parcel-route`, most likely taken from those reference lines. It never listed or read the deleted folder: no tool call touches `pool/parcel-route`. Its output shares one text node with the deleted figure ("Delivered"), and its lines match the deleted file at a difflib ratio of 0.137. The deleted figure's own labels (for example "Mon 09:12 · online", "Van 7 · 32 stops") do not appear in the output. After the run, `diff -rq` showed the installed skill copy unchanged apart from the planned removal.

## Results

| | bare | skill |
|---|---|---|
| Elapsed (wall clock) | 349 s | 213 s |
| Turns (`num_turns`) | 13 | 16 |
| Tool calls | 10 (Read 5, Bash 4, Write 1) | 13 (Bash 9, Read 3, Skill 1) |
| Tokens, cumulative (`modelUsage`) | input 24, cache write 29,952, cache read 258,924, output 31,479 (thinking 2,665) | input 28, cache write 64,232, cache read 579,647, output 18,317 (thinking 6,562) |
| Cost reported by CLI | $0.92 | $1.00 |
| `result.html` size | 15,122 bytes | 16,373 bytes |
| Other files written | 6 PNG screenshots in `/tmp` (outside its project folder) | `anim/frames/`: 11 files, 701,613 bytes (check renders and previews, left in the project folder) |
| Opens from disk | yes, no page errors | yes, no page errors |
| Network loads | none (the only URL is the SVG namespace string) | none |
| Play once / replay | loops: the 7-step sequence restarts about every 24 s, and the active stage has an endless pulse ring. Has buttons for back, pause, forward and replay, plus keys and `#0` to `#6` deep links | plays once (9 s) and rests on the finished frame; the frame 6 s after rest is byte-identical to the rest frame. No replay control: reload to replay |
| Reduced motion | finished frame (step 6), no motion | finished frame, no motion |
| Print (`--print-to-pdf`) | prints the step that is current at print time (step 1 or 2 in the tests), with the control buttons; the lead time is missing | finished frame (print rule sets `animation: none`) |
| Untraceable visible facts | 2 | 0 |
| Manual corrections needed before showing | 3 | 0 (2 optional) |

For `--print-to-pdf` and `--force-prefers-reduced-motion` runs, Chrome did not exit by itself in this environment. It was stopped by a 60 s `timeout` after it had written its output files. The PDFs were checked with `pdfinfo` and `pdftotext`, and rendered with `pdftoppm`. Only the PNG renders are stored.

### verify_facts.py (`--strict`)

The script as committed in 4034476 and the version with the label-to-value pairing check added later the same day gave the same output. Full text is in `verify_facts-output.txt`.

- bare: `FAILED: 1 fail, 3 warn`. FAIL: "Tracking # sent", no source match for "sent". WARN: "Five" in the aria-label, and "Animated diagram", "stages" in aria-labels. The script reads the static HTML. The bare arm builds its stage captions, numbers and status pill text in JavaScript, so the script did not see those labels. They are covered in the manual list below.
- skill: `PASS: 0 fail, 2 warn`. Both warnings are in the aria-label ("five", "travels", "stages").

## Per-arm description

Screenshots are in `bare/shots/` and `skill/shots/`, taken with Playwright driving the installed Google Chrome. Files: `desktop-*` at 1440x900 and `mobile-*` at 390x844, at 1 s (`t1s`), mid-pass (`mid`), at rest (`rest`), 6 s after rest (`rest-plus6s`), with reduced motion (`*-reduced-0.3s.png`, plus `cli-reduced-motion-1440.png` from Chrome's `--force-prefers-reduced-motion`), and print (`print-vtb1000-1.png`, `print-vtb30000-1.png`: page 1 of each PDF, printed at the two virtual-time budgets named in the file names).

Frames that were byte-identical to another frame are not stored:

- In both arms and at both sizes, the reduced-motion frame at 3.3 s was identical to the one at 0.3 s. `*-reduced-0.3s.png` stands for both: nothing moves under reduced motion.
- In the skill arm, the frame 6 s after rest was identical to the rest frame at both sizes. `skill/shots/*-rest.png` stands for both. In the bare arm the two differ (the loop has restarted), so both are kept.
- In the skill arm, the two print budgets gave identical renders. `skill/shots/print-vtb1000-1.png` stands for both.

The print PDFs themselves are not stored; their PNG renders are. For the bare arm the times are 1 s, 10 s and 20 s, because its sequence lasts about 24 s. Two extra frames show steps 2 and 4 (`desktop-t5.5s-step2.png`, `desktop-t12.3s-step4.png`).

### bare

Output: `bare/result.html`.

This is a diagram, not restyled bullets. The six bullets become five numbered circular stations on a horizontal road. Title and footer are kept in the source's palette. A cardboard parcel hops from station to station, an orange progress line fills behind it, and the current station turns orange with a repeating pulse ring. Each stage gets one extra drawing:

1. an envelope with a "Tracking # sent" chip
2. an "Aisle 14" chip with a red scan beam and "pack · label · scan"
3. three lines fanning out to three truck rectangles, with a "by postcode" chip
4. an arc of 30 dots, "+ about 30 other stops"
5. a signature pad with a drawn signature

The last step draws a bracket under the row: "≈ 28 hours / typical lead time, from order to doorstep". A "Tracking status" pill at top right shows the current stage name and turns green with "“Delivered”".

Stage captions are full paraphrases of the bullets, which keeps more source detail than the skill arm.

Observations:
- Nothing is clipped, and the text does not overlap at 1440x900.
- At rest the parcel box touches the lower-left corner of the signature pad (a 2-unit overlap in SVG units).
- At 1 s a half-drawn curved stroke runs from the parcel to the envelope.
- The finished frame (`desktop-rest.png`) reads well, but it is on screen for only about 6 s of every 24 s cycle. Then the slide resets to stage 1 (`desktop-rest-plus6s.png`).
- At 390 px wide the 16:9 slide shrinks to 390x219 and the text is about 4 to 5 px tall. The source slide has the same limit.

### skill

Output: `skill/result.html`.

This is a diagram. The bullet list is replaced by five ringed stations with line icons, labels in the slide's navy, and a short detail line under each label taken from the bullet. Title and footer are unchanged. The fragment is CSS-only: no script, one 9 s pass gated by `.visible`.

A small parcel outline slides along a route line above the stations. The line fills in navy behind it, and each ring turns navy and its detail fades in as the parcel arrives. A hairline bracket then draws under the row with "Typical lead time: **about 28 hours** from order to doorstep".

Observations:
- At 1 s all five station labels are already shown in grey.
- At rest (`desktop-rest.png`) everything is navy and readable. Nothing is clipped and nothing overlaps.
- The route line runs above the rings, not through them, so the parcel travels on a separate rail over the stations.
- The bracket and the unlit rail use `#c3cbd6` on `#f9f9f7`, about 1.55:1 contrast. The bracket is faint. The session's own check_look passed it, because that check scores text, not lines.
- Detail lines are shorter than the bullets. They leave out "staff locate the item", "the driver hands it over" and "confirmation".
- Mobile has the same 16:9 shrink as the bare arm.
- The session ran the skill's `check_page.py` (PASS, 2 warnings about markers and gate) and `check_look.py --at-marks` (PASS, 0 warnings). It looked at its own frames and tightened the SVG viewBox once.
- It left its check renders in `anim/frames/`, and its final message says this folder can be deleted. `check_page.py`'s "no leftovers" line ran before the frames were rendered.

## Accuracy: visible facts

Source text: the title, six bullets, footer "Logistics 101 · Operations onboarding" and the slide number 4.

### bare (labels drawn by script included)

| Visible text | Traceable |
|---|---|
| Title, footer, "4" | yes |
| Stage names (5) | yes ("Sorted at regional hub" drops "the") |
| Captions: "Customer checks out online; confirmation e-mail with a tracking number", "Item located (aisle 14), packed, labelled and scanned out", "Parcels scanned and routed onto trucks by postcode", "Loaded onto a local van with about 30 other stops", "Handed over, signature collected, status changes to “Delivered”" | yes |
| Station numbers 1 to 5 | yes (order of the list) |
| "Tracking # sent" | yes in meaning (receives e-mail with tracking number); flagged by verify_facts for the word "sent" |
| "Aisle 14", "pack · label · scan", "by postcode", "+ about 30 other stops", 30 dots, "signature" | yes |
| "≈ 28 hours", "typical lead time, from order to doorstep" | yes |
| Three truck rectangles | drawing, count not in source (illustrative) |
| Status pill "Waiting for order" (step 0, at start and after each loop) | **no** |
| Status pill values "Order placed", "Picked at the warehouse", "Sorted at regional hub", "Out for delivery" shown as tracking statuses | **no**: the source names only "Delivered" as a status. The session said so in its own final message. |

Untraceable: 2 items, plus one illustrative drawing (three trucks).

### skill

| Visible text | Traceable |
|---|---|
| Title, footer, "4" | yes |
| "Order placed", "Picked at the warehouse", "Sorted at the regional hub", "Out for delivery", "Delivered" | yes |
| "checkout online, e-mail + tracking no." | yes |
| "aisle 14 · pack, label, scan out" | yes |
| "scanned, routed onto trucks by postcode" | yes |
| "local van with about 30 other stops" | yes |
| "signature collected, status: “Delivered”" | yes |
| "Typical lead time: about 28 hours from order to doorstep" | yes |

Untraceable: 0.

## Manual corrections before showing to an audience

These were not applied to the captured files.

### bare (3 needed)

1. Status pill wording is not in the source.
   - Line 206, current: `const pillText = ["Waiting for order", "Order placed", "Picked at the warehouse", "Sorted at regional hub",`
   - Fix: drop the pill until the last step, or label it as a stage instead of a status. For example, change line 95 from `Tracking status <span ...>` to `Stage <span ...>` and replace `"Waiting for order"` with `""`.
2. It loops. After the lead-time step it resets to the start, so the summary frame is on screen about 6 s of every 24 s.
   - Line 264, current: `timer = setTimeout(() => { if (step < LAST) go(step + 1); else go(0); }, DUR[step]);`
   - Fix: `timer = setTimeout(() => { if (step < LAST) go(step + 1); }, DUR[step]);`
   - The endless pulse on the active station (line 43, `animation: pulse 1.6s ease-out infinite`) also repeats. It is only on during the active step and stops at step 6.
3. Print or PDF export shows a mid-sequence step with the control buttons, without the lead time.
   - Fix: add a print rule that shows step 6 and hides `.ctrl`. For example, before `</style>` (line 88): `@media print { .ctrl { display: none } }`. Starting at step 6 for print also needs a `beforeprint` handler that calls `go(6)`.

Optional: the parcel touches the signature pad at rest (line 157 area, pad at `x="905"`); and the half-drawn stroke at step 1 (line 121).

### skill (0 needed, 2 optional)

1. Optional: the faint bracket. Line 52, current: `.anim-parcel-route .parcel-route-bracket{fill:none;stroke:var(--anim-line);` corrected: `.anim-parcel-route .parcel-route-bracket{fill:none;stroke:var(--anim-muted);` (about 5.75:1).
2. Optional: delete the `anim/frames/` folder the session left next to `result.html` (it is not part of `result.html`).

No replay control. Replaying needs a page reload. This is the skill's intended design (play once), so it is not counted as a correction.

## Limits

- One run per arm (n=1). There is no variance estimate, and a second run of either arm could differ.
- One slide, one prompt, one model (`claude-opus-5-5`), one harness (Claude Code 2.1.331), on one machine (macOS).
- The skill under test is commit 4034476 (0.13.0). In the copy used for this run, the pool had `parcel-route` removed (it is still in the repository's pool). Two reference lines still name `parcel-route`, as described above.
- Both arms used `--permission-mode bypassPermissions`, which does not confine file access to the project folder. The bare session wrote six screenshots to `/tmp`. Nothing confines either session to its folder other than its own choices.
- Built-in CLI skills (including `design` and `dataviz`) were visible in both arms. They could not be hidden without also hiding project skills.
- The user's `CLAUDE.md` exclusion is shown only by the haiku probe's self-report and by the documented meaning of `--setting-sources`. The init event does not list loaded memory files.
- Chrome's `--print-to-pdf` and `--force-prefers-reduced-motion` runs were stopped by `timeout` after writing their files. Printing was tested at two virtual-time budgets, not by printing from an open, live page at a chosen moment.
- Screenshots were taken at fixed times. Motion between those times was not inspected frame by frame, except through the sessions' own renders and the extra bare frames.
- The judgement of what counts as a needed correction is mine. It was not given to a second reviewer.
- `verify_facts.py` reads static HTML only. The bare arm's labels drawn by script were checked by hand, not by the script.
- The raw transcripts (`*/transcript.jsonl`) and probe transcripts are kept out of git (`.gitignore` in this folder) because they carry machine paths and session ids. In the files that are committed, the repository root is written as `<repo>`, the scratch folder as `<scratch>` and the CLI binary as `claude` (in `harness/runarm.py` it is read from `CLAUDE_BIN`). Byte-identical frames and the print PDFs were removed, as listed under Per-arm description. Nothing else was edited.
