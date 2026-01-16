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

---

## Requirements

- Python 3.7 or higher
- [pdfplumber](https://github.com/jsvine/pdfplumber)
- pandas
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
python generate_test_transcripts.py   # Generate 8 synthetic PDF transcripts
python run_tests.py                   # Run certification and validate results
```

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
