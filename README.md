# Graduate Degree Certification Tool

This Python-based tool automates the certification process for graduate degree transcripts by parsing official PDF records and verifying whether students meet programmatic graduation requirements.

Written by Robert Fisher, 060525

---

## Features

- Extracts and parses multi-column academic transcripts in PDF format  
- Dynamically adapts to two-column transcript PDF layouts of any size  
- Identifies semester, course codes, course titles, credits, grades, and classifications  
- Categorizes courses into **Core**, **Elective**, and **Research** types using customizable rules  
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

These thresholds can be customized in the script’s logic for use in any academic unit or graduate program.

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

---

## Requirements

- Python 3.7 or higher  
- [pdfplumber](https://github.com/jsvine/pdfplumber)  
- pandas  

### Install dependencies

```bash
pip install pdfplumber pandas
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
   F23    | ABC 543     | Advanced Topic A              |   3.00  | Core           | A
   S24    | ABC 690     | Graduate Research             |   6.00  | Research       | A-
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
├── degree_certify.py         # Main script to run
├── output/                   # Folder containing generated certification CSVs
├── README.md                 # This file
```

---

## Customization

To adapt this tool for another department or set of rules:

- Update the `RESEARCH_COURSES` and `NON_CORE_ELECTIVE` sets in the script  
- Adjust credit thresholds and classification logic as needed  
- Consider modularizing the logic if using in multiple programs  

---

## License

MIT License. See `LICENSE` for terms.
