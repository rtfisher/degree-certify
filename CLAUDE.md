# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A single-purpose tool that certifies graduate (MS Physics) degree transcripts. It parses official PDF transcripts, classifies courses, applies degree-requirement rules, and emits per-student CSVs plus a cumulative summary. The whole certification engine lives in one script — `degree_certify.py` — with a separate synthetic-PDF generator and test runner used only for testing.

## Commands

```bash
pip install -r requirements.txt          # deps: pdfplumber, pandas, rich; reportlab (tests)

# Run certification on one or more transcripts (non-interactive by default)
python3 degree_certify.py transcript1.pdf transcript2.pdf
python3 degree_certify.py --interactive transcript.pdf   # opens the rich TUI editor

# Test workflow — generation step must run before the test runner
python generate_test_transcripts.py      # writes synthetic PDFs into tests/ (gitignored)
python run_tests.py                       # PDF cert tests + headless TUI tests; exit 0/1
python test_tui.py                        # run just the TUI logic tests
```

There is no per-PDF test command. To debug one case, run the script directly on its PDF, e.g. `python3 degree_certify.py --output-dir test_output tests/fail_invalid_course.pdf`. PDF cases are the `TEST_CASES` dict in `run_tests.py` (filename → expected pass/fail); TUI cases are assertions in `test_tui.py` (`run_tui_tests()`), which `run_tests.py` also runs.

CI (`.github/workflows/test.yml`) runs the same generate-then-test sequence on push/PR to `main` under Python 3.11.

## Architecture

**`degree_certify.py`** — the engine. Entry point is `main(argv)`, guarded by `if __name__ == "__main__"`. The pipeline is **parse → (optional TUI edit) → classify → certify**. Interactive editing is fully separated from the rest: the TUI only writes the rulebook/store, and classification/certification read them non-interactively, so the headless path is identical with or without `--interactive`.

- `extract_courses_and_student_info(pdf_path)` — PDF parsing only. Transcripts are assumed to be **two-column** layouts; the page is split at the horizontal midpoint and each column is extracted/concatenated (`extract_column_text`). Course lines are matched by `COURSE_RE` (`DEPT NUM Title AttemptedCr EarnedCr Grade Points`); each is buffered (`pending`) so a following `Course Topic:` line attaches as a `Topic` field. Also scans graduate `Program/Plan/Subplan` lines for the EAS PhD signature. Returns `(name, id, DataFrame, detected_eas_phd)` with **no** Classification yet.

- `classify_rows(df, eas_phd, class_map, interactive=False)` — **the single source of classification truth**, returning per-course view dicts (classification + `editable`/`section`/`key`/`cached`/`default`). Used by both the non-interactive resolver and the TUI's live recompute, so they always agree. **Branch order matters** (a fixed bug): Research → special-topics (rulebook key `COURSE | Topic`) → `NON_CORE_ELECTIVE` whitelist → generic `PHY → Core` → external. The whitelist must precede the generic PHY rule or a bare `PHY 510` wrongly becomes Core. `count_credits(rows)` tallies applicable credits over those views.
- `resolve_classifications(df, eas_phd, class_map)` — thin non-interactive wrapper over `classify_rows` that writes the `Classification` column. `certifies(counts)` is the shared pass/fail predicate.
- `generate_certification_csv_and_display(..., eas_phd, interactive, ...)` — certification, CSV, terminal report, summary dict; performs EAS PhD single-count designation (below).

**`certify_tui.py`** — the rich-based, **cursor-driven** interactive UI (imported lazily, only when `--interactive`, so headless runs never load `rich`). `edit_classifications(...)` shows all courses in one table with a movable cursor (↑/↓), single-key classification (c/e/r/x) or cycle (←/→), live totals + PASS/FAIL, and writes choices into `class_map`; `select_single_counted(...)` toggles reserved courses with Space. Keys are read one at a time in raw mode by `make_getch()` (stdlib `termios`/`tty`, decoding arrow escape sequences); `getch` is injectable so the navigation/action logic is unit-tested headlessly in `test_tui.py` (driving `"UP"`/`"DOWN"`/`"c"`/… sequences). Falls back to saved/default classifications when stdin isn't a TTY.

### Modes and rulebooks

- `--interactive` — opens the TUI to classify/revise every course (subsumes the old `--reclassify`); default is non-interactive (rulebook + defaults). Decisions persist in `course_classifications.json` (`special_topics` keyed `COURSE | Topic`, `courses` keyed by code), so later runs are deterministic.
- **EAS PhD mode is auto-detected** from the transcript's graduate `Plan:` line (`EAS_PHD_PLAN_SIGNATURE`); `--eas-phd` / `--no-eas-phd` force it on/off (mutually exclusive). `resolve_effective_eas_phd()` combines them; `main()` prints the track. In EAS mode unknown externals default to `Exclude` (not `Invalid`), and for a student who **otherwise certifies** the *fewest* courses are reserved as **single-counted** (M.S.-only) so ≤24 are double-counted — only `MS_MIN_TOTAL_CREDITS − cap = 6` credits, regardless of surplus. Reported (flagged with an `M.S.-only` CSV column), **not** a pass/fail gate. Persists per student in `single_count.json`.

Both JSON rulebooks are gitignored per-installation state. Classification distinguishes **Exclude** (skip, no penalty) from **Invalid** (skip *and* fail) — only non-whitelisted externals in standard (non-EAS) mode are Invalid.

### Parsing state machine (the subtle part)

Courses only count when they fall in the **graduate section** (after the `Beginning of Graduate Record` marker) — *or* in a transfer-credit block that immediately precedes that marker. Undergraduate transfer credits must NOT be counted (regression fixed in commit 6e6830e; covered by `pass_undergrad_transfer_ignored.pdf`).

This is handled with a **buffer-and-commit** pattern: a `Transfer Credit from` line starts buffering courses into `transfer_buffer`. The buffer is only committed to the real record when `Beginning of Graduate Record` is reached next; if another transfer section appears first, the prior buffer is **discarded**. This is why transfer detection depends on ordering, not just the presence of a transfer line.

**Special-topics courses** span two lines (a course line followed by `Course Topic: ...`). Parsing holds each parsed course in `pending` so the next line's topic attaches as the `Topic` field; classification keys special topics on `COURSE | Topic`. Pass/in-progress lines (grades `P`/`IP`/blank) never match `COURSE_RE` and are dropped automatically.

### Classification rules (defaults; the rulebook overrides per course)

- `RESEARCH_COURSES` → `Research`
- a course with a `Topic` (special topics) → rulebook value, else `Elective`
- `NON_CORE_ELECTIVE` whitelist → `Elective`
- `PHY` prefix → `Core`
- other external → rulebook value, else `Exclude` (EAS PhD) or `Invalid` (standard, fails certification)

### Certification logic (in `generate_certification_csv_and_display`)

Credit counting **skips** Invalid/Exclude courses and anything below 400-level. Pass requires ALL of: ≥15 Core, ≥30 total, ≤6 Research applied (research is capped at 6 via `min`), ≤6 400-level credits, and zero Invalid courses. Adjust thresholds/sets here when adapting to another program.

### Output behavior

- A CSV is written for **every** student regardless of pass/fail. Filename: `{firstinitial}{lastname}_{studentid}_ms_phy_track.csv`.
- **Auto-resume:** if a student's per-student CSV already exists in the output dir, `main()` reads it (`read_prior_certification`) and restores each course's classification + single-counted selection before re-certifying. A resumed student uses a private classification map (global rulebook overlaid with the CSV) and does **not** write back to the shared rulebook — the CSV is that student's source of truth. Matching is by `(Course Code, displayed Title)`, so the title must round-trip (it carries the special-topics topic). `student_csv_filename()` is the shared filename helper. Round-trip covered by `run_resume_test()`.
- `certification_summary.csv` is opened in **append mode** — reruns accumulate rows rather than overwriting, and each row carries a certification timestamp. Delete it for a clean slate.
- Student ID is written as `="..."` to force text formatting in spreadsheets.

**`generate_test_transcripts.py`** — uses reportlab to render synthetic transcript PDFs mimicking the real two-column format. Test students use IDs `9999000N` (the 10th is `999900010`); `run_tests.py` derives the expected ID from each test's position in `TEST_CASES`, so ordering matters. All content is invented — **never copy courses, titles, or topics from a real student transcript into the test fixtures**. Fixtures can emit `Program/Plan/Subplan` blocks (`grad_program_plans`): `pass_eas_phd.pdf` carries the EAS plan so detection fires; `pass_grad_only.pdf` carries a Physics-only plan as a false-positive guard.

The EAS-PhD case (`pass_eas_phd.pdf`, test #10) runs **flagless** — EAS mode is auto-detected — with a `rulebook` dict seeded to a temp file (so the run is deterministic and the real gitignored rulebook is untouched; this is why `degree_certify.py` exposes `--rulebook` / `--single-count-file` path overrides) and `stdout_contains` assertions (incl. `EAS PhD track auto-detected`) checked against the stable summary-dict repr. Runs use `stdin=DEVNULL`, so an unexpected interactive prompt fails rather than hangs.

**`test_tui.py`** — headless tests for `certify_tui.py` using a synthetic in-memory DataFrame and an injected `input_fn` (no real terminal). `run_tests.py` calls `run_tui_tests()` after the PDF cases; they **SKIP** (not fail) if `rich` is missing, but CI installs it. Suite total is 10 PDF + 18 TUI checks.

## Conventions

- Output directories `output/`, `tests/`, and `test_output/` are gitignored. Production output goes to `output/`; tests use `test_output/` to stay isolated.
- `degree_certify.py.old` is a prior version kept untracked for reference — not part of the build.
