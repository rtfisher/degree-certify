![Tests](https://github.com/rtfisher/degree-certify/actions/workflows/test.yml/badge.svg)

# Graduate Degree Certification Tool

This Python-based tool automates the certification process for graduate degree transcripts by parsing official PDF records and verifying whether students meet programmatic graduation requirements.

Written by Robert Fisher, 060525

---

## Features

- Extracts and parses multi-column academic transcripts in PDF format  
- Dynamically adapts to two-column transcript PDF layouts of any size  
- Identifies semester, course codes, course titles, credits, grades, and classifications  
- Categorizes courses into **Core**, **Elective**, and **Research** types using customizable rules
- Supports **transfer credits** (grade "T") from other institutions when appearing just before the graduate record
- Flags non-whitelisted courses from external departments  
- Excludes any courses numbered below a specified threshold (e.g., 400-level minimum)  
- Limits the number of applied credits from specific course types (e.g., Research or 400-level)  
- Verifies minimum total credit requirements  
- Generates detailed certification `.csv` files and a master tracking summary  
- Outputs results clearly to both terminal and csv files  

---

## Certification Criteria (Customizable)

By default, a student transcript is certified if **all** of the following are met:

1. **Core Credits**: Minimum number of credits in core departmental coursework (e.g., ≥15 credits)  
2. **Research Credit Cap**: No more than 6 credits from Research courses are applied toward the total  
3. **400-Level Credit Cap**: No more than 6 credits from 400-level courses (if allowed)  
4. **Graduate Credit Requirement**: A minimum of 30 credits from valid graduate-level courses  
5. **Valid Courses Only**: All non-departmental courses must be explicitly whitelisted; others are excluded  

These thresholds can be customized in the script's logic for use in any academic unit or graduate program.

---

## Transfer Credits

The tool supports transfer credits from other institutions. Transfer credits are detected when they appear **immediately before** the "Beginning of Graduate Record" marker in the transcript, introduced by a line such as:

```
Transfer Credit from Swiss Federal Polytechnic School in Zurich 
```

Transfer courses have a grade of "T" (no GPA impact) and follow the format:

```
PHY 412 Elec & Magnt Fields II 3.00 3.00 T 0.000
```

These credits are:
- Included in the total credit count for degree certification
- Marked with "(Transfer)" suffix in the output CSV
- Classified as Core, Elective, or Research based on course code (same rules as regular courses)

---

## Interactive classification (`--interactive`)

By default the tool runs **non-interactively**, classifying courses from the saved rulebook plus defaults. Pass `--interactive` to open a cursor-driven terminal UI that shows every course in one table:

- **↑/↓** — move the cursor between courses
- **c / e / r / x** — set the highlighted course to Core / Elective / Research / Exclude
- **←/→** — cycle the highlighted course's classification
- **s** — save and continue, **q** — quit without saving

The Core/Total/Research/400-level credits and a PASS/FAIL banner update live after every change. Every course is editable (including PHY-core and whitelisted electives); special-topics and external courses still on their default are flagged `● review`, and courses with a saved decision show `✎ saved`. For EAS PhD students a second screen lets you toggle (Space) which applied courses are single-counted.

Decisions persist to `course_classifications.json`, keyed on `COURSE | Topic` for special topics (e.g. `PHY 510 | Quantum Field` → Core) and on the course code otherwise, so a topic later upgraded to a core course is applied automatically on every future run. The file is plain JSON and can be edited by hand. Courses graded `P`, `IP`, or blank (dissertation/seminar/research) are ignored automatically and never appear as editable.

## EAS PhD Students (M.S. Physics en route)

EAS PhD students may earn the M.S. Physics on the way to the doctorate and are permitted to **double-count up to 24 credits** between the two degrees. **EAS PhD mode is auto-detected** from the transcript's graduate `Plan:` line (the Engineering & Applied Science PhD program); use `--eas-phd` to force it on or `--no-eas-phd` to force it off. The detected/forced track is printed for each transcript.

```bash
python3 degree_certify.py --interactive transcript.pdf   # EAS mode auto-detected; opens the editor
```

In EAS PhD mode:
- **Lenient externals.** Non-PHY PhD courses (research/seminar/minor) default to *Exclude* instead of failing certification.
- **Single-count designation.** For a student who otherwise certifies, the **fewest** courses needed are reserved as **single-counted** (M.S.-only) so that no more than 24 credits are double-counted (with a 30-credit M.S., that's just 6 credits / 2 courses). In `--interactive` mode you can adjust which courses — reserve credits the PhD will not need. This is **reported on the certificate, not enforced as a failure**, and the single-counted courses are flagged with an `M.S.-only` column in the per-student CSV. Selections persist per student in `single_count.json`.

Both rulebook files are gitignored (per-installation state). A non-interactive run reproduces a prior interactive run's decisions with no prompts.

## Resuming from a prior certification

If a per-student certification CSV already exists in the output directory (`{initial}{lastname}_{id}_ms_phy_track.csv`), the tool **automatically resumes from it**: each course's classification and the single-counted (M.S.-only) selection are restored from that file before re-certifying. This makes the CSV the durable per-student record — re-running picks up exactly where you left off even if the shared rulebook has since changed. A resumed student uses a private classification map and does **not** write back to the shared `course_classifications.json`. Delete the student's CSV to start that student fresh.

## Usage

### Command-Line

```bash
python3 degree_certify.py transcript1.pdf transcript2.pdf transcript3.pdf
```

- Pass one or more transcript PDF files as input.
- Outputs will be saved in the `output/` directory:
  - One `.csv` per student summarizing coursework and graduation checks
  - One cumulative `certification_summary.csv` listing all certification outcomes

### Options

```bash
python3 degree_certify.py --output-dir custom_output transcript.pdf
```

- `--output-dir`: Specify a custom output directory (default: `output/`)
- `--interactive`: Open the rich TUI to classify/revise courses (and choose single-counted credits for EAS PhD). Decisions are saved to the rulebook (`course_classifications.json`) and reused automatically on later runs.
- `--eas-phd` / `--no-eas-phd`: Force EAS PhD mode on/off. By default it is auto-detected from the transcript's graduate `Plan:` line (see below).

---

## Requirements

- Python 3.7 or higher
- [pdfplumber](https://github.com/jsvine/pdfplumber)
- pandas
- [rich](https://github.com/Textualize/rich) (for the `--interactive` TUI)
- reportlab (for test suite only)

### Install dependencies

```bash
pip install -r requirements.txt
```

---

## Example Terminal Output

```
Prepared by: Robert Fisher
Student Name: Albert Einstein
Student ID: 3141592654
Certification PASSED. CSV saved to: output/aeinstein_ms_phy_track.csv

Course Record:
 Semester | Course Code | Title                         | Credits | Classification | Grade
----------|-------------|-------------------------------|---------|----------------|-------
   F23    | ABC 543     | Quantum Mechanics             |   3.00  | Core           | B-
   S24    | ABC 690     | Graduate Thesis               |   6.00  | Research       | A+
...

Graduation Requirements:
 Requirement                          | Value | Status
-------------------------------------|-------|---------
 ≥15 Core Credits                    |   18  | Verified
 ≤6 Research Credits Applied         |    6  | Verified
 ≤6 400-Level Credits Applied        |    3  | Verified
 ≥30 Total Credits                   |   33  | Verified
```

---

## File Structure

```
.
├── degree_certify.py              # Main certification script
├── generate_test_transcripts.py   # Generates synthetic test PDFs
├── run_tests.py                   # Test runner and validator
├── requirements.txt               # Python dependencies
├── .github/workflows/test.yml     # CI/CD workflow
├── output/                        # Production certification output
├── tests/                         # Generated test transcripts (gitignored)
├── test_output/                   # Test certification output (gitignored)
└── README.md                      # This file
```

---

## Testing

The project includes a comprehensive test suite with synthetic transcripts covering all certification scenarios.

### Running Tests Locally

```bash
python generate_test_transcripts.py   # Generate 10 synthetic PDF transcripts
python run_tests.py                   # Run certification and validate results
```

All test transcripts are wholly synthetic (invented students, course numbers, and titles) with no connection to any real student record.

### Test Cases

| Test | Description | Expected |
|------|-------------|----------|
| pass_standard.pdf | Full undergrad + grad record | PASS |
| pass_grad_only.pdf | Graduate record only | PASS |
| pass_with_transfer.pdf | Includes transfer credits | PASS |
| pass_excess_research.pdf | 9 research credits (6 applied) | PASS |
| fail_insufficient_core.pdf | Only 12 core credits | FAIL |
| fail_insufficient_total.pdf | Only 27 total credits | FAIL |
| fail_excess_400level.pdf | 9 400-level credits | FAIL |
| fail_invalid_course.pdf | Non-whitelisted BIO 520 | FAIL |
| pass_undergrad_transfer_ignored.pdf | Undergrad transfer credits ignored | PASS |
| pass_eas_phd.pdf | EAS PhD M.S.-en-route; `--eas-phd` with rulebook-upgraded core topics, P/blank research ignored | PASS |

### Continuous Integration

Tests run automatically on push and pull request via GitHub Actions. The badge at the top of this README shows the current test status.

---

## Customization

To adapt this tool for another department or set of rules:

- Modify the parsing of the transcript file for other institutions as necessary
- Update the `RESEARCH_COURSES` and `NON_CORE_ELECTIVE` sets in the script  
- Adjust credit thresholds and classification logic as needed  
- Consider modularizing the logic if using in multiple programs  

---

## License

MIT License. See `LICENSE` for terms.
