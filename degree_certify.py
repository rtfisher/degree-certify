#!/usr/bin/env python3
"""
degree_certify.py

Written by Robert Fisher, 060525

Description:
-------------
This script processes graduate transcript PDFs and certifies whether each student has met the degree requirements.

It performs the following tasks:
1. Parses transcripts in PDF format using layout-based text extraction (supports two-column layouts).
2. Extracts student name, ID, and detailed course information.
3. Categorizes courses as Core, Elective, or Research based on course codes and predefined rules.
4. Applies the following degree certification criteria:
    - At least 15 Core Credits
    - No more than 6 credits of Research courses may be applied
    - No more than 6 credits from 400-level (4XX) courses may be applied
    - Courses numbered below 400 (e.g., PHY 320) are excluded and do not count toward the 30-credit total
    - A minimum of 30 total graduate-level credits (500-level and above, including up to 6 credits of 400-level courses)
    - All non-PHY courses must be explicitly whitelisted as non-core electives (e.g., EAS 520); otherwise, certification fails

 These criteria may be adjusted for other programs; see the comment regarding "certification logic" below.

 Each line in the graduate section of the transcript is expected to follow a consistent format:

     <DEPT> <COURSE_NUM>   <COURSE TITLE>   <Attempted Cr>  <Earned Cr>  <Grade>  <Points>

 Example:
     PHY 543   Quantum Mechanics I   3.00   3.00   A   4.000

 - <DEPT> is a 3-letter department prefix (e.g., PHY, EAS)
 - <COURSE_NUM> is a 3-digit course number (e.g., 543)
 - <Description> is a text field, possibly containing spaces, with the course title (eg, "Quantum Mechanics I")
 - <Attempted Cr> and <Earned Cr> are both floating-point numbers (e.g., 3.00)
 - <Grade> is a letter grade (e.g., A, B+, C-)
 - <Points> is a floating point value with three decimals for the number of quality points earned (= numerical grade * Earned Cr, e.g., 12.000 for an A in a 3-credit course)

Special topics courses have a second following line with the format: "Course Topic: <topic description>".

 Only lines following this structure and occurring after the line:
     ---------- Beginning of Graduate Record ----------
 are considered valid for certification analysis.

Each semester appears as a line separated by whitespace, formatted as: "YYYY Fall|Spring". Program and plan are listed after each semester, prior to the text of the courses.

Outputs:
---------
- CSV for each student passing certification
- Terminal report for each transcript
- Summary CSV (`certification_summary.csv`) for all transcripts processed

Usage:
-------
    python3 degree_certify.py <transcript1.pdf> [<transcript2.pdf> ...]
"""

import pdfplumber
import pandas as pd
import re
import sys
import string
from pathlib import Path

RESEARCH_COURSES = {"PHY 680", "PHY 685", "PHY 690"}
NON_CORE_ELECTIVE = {"PHY 510", "EAS 502", "EAS 520", "MTH 573"}

if len(sys.argv) < 2:
    print("Usage: python3 degree_certify.py <transcript1.pdf> [<transcript2.pdf> ...]")
    sys.exit(1)

PDF_FILE_LIST = sys.argv[1:]
summary_records = []

def get_course_level(course_code):
    match = re.search(r"\b(\d{3})\b", course_code)
    return int(match.group(1)) if match else None

# The transcript is assumed to be have a two-column layout. We extract both.
def extract_column_text(page, left_col_bbox, right_col_bbox):
    left_lines = page.crop(left_col_bbox).extract_text().splitlines() if page.crop(left_col_bbox).extract_text() else []
    right_lines = page.crop(right_col_bbox).extract_text().splitlines() if page.crop(right_col_bbox).extract_text() else []
    return left_lines + right_lines

def extract_courses_and_student_info(pdf_path):
    course_records = []
    current_semester = ""
    buffer_special_topics = None
    student_name = None
    student_id = None
    in_graduate_section = False  # <-- initialize here, before the page loop

    with pdfplumber.open(pdf_path) as pdf:
        page_width = pdf.pages[0].width
        page_height = pdf.pages[0].height
        left_col_bbox = (0, 0, page_width / 2, page_height)
        right_col_bbox = (page_width / 2, 0, page_width, page_height)

        for page in pdf.pages:
            if not student_name or not student_id:
                full_text = page.extract_text()
                if full_text:
                    for line in full_text.splitlines():
                        if not student_name:
                            name_match = re.match(r"Name:\s+(.+)", line)
                            if name_match:
                                student_name = name_match.group(1).strip()
                        if not student_id:
                            id_match = re.match(r"Student ID:\s+(\d+)", line)
                            if id_match:
                                student_id = id_match.group(1).strip()

            lines = extract_column_text(page, left_col_bbox, right_col_bbox)

# Each line in the graduate section of the transcript is expected to follow a consistent format,
# typically structured as:
#
#     <DEPT> <COURSE_NUM>   <COURSE TITLE>   <Attempted Cr>  <Earned Cr>  <Grade>  <Points>
#
# Example:
#     PHY 543   Quantum Mechanics I   3.00   3.00   A   4.000
#
# - <DEPT> is a 3-letter department prefix (e.g., PHY, EAS)
# - <COURSE_NUM> is a 3-digit course number (e.g., 543)
# - <Description> is a text field, possibly containing spaces, with the course title (eg, "Quantum Mechanics I")
# - <Attempted Cr> and <Earned Cr> are both floating-point numbers (e.g., 3.00)
# - <Grade> is a letter grade (e.g., A, B+, C-)
# - <Points> is a floating point value with three decimals for the number of quality points earned (= numerical grade * Earned Cr, e.g., 12.000 for an A in a 3-credit course)
#
# Only lines following this structure and occurring after the line:
#     ---------- Beginning of Graduate Record ----------
# are considered valid for certification analysis.


# Track whether we're past the undergraduate section (commented out, as it doesn't maintain state across pages)
#            if 'in_graduate_section' not in locals():
#                in_graduate_section = False

            for line in lines:
                if not in_graduate_section:
                    if "Beginning of Graduate Record" in line:
                        in_graduate_section = True
                    continue  # Skip everything before the marker

                sem_match = re.match(r"\s*(\d{4})\s+(Fall|Spring|Sprng)", line)
                if sem_match:
                    if buffer_special_topics:
                        course_records.append(buffer_special_topics)
                        buffer_special_topics = None
                    year = sem_match.group(1)[-2:]
                    term = sem_match.group(2).replace("Sprng", "Spring")
                    current_semester = f"{'F' if term == 'Fall' else 'S'}{year}"

                course_match = re.search(
                    r"([A-Z]{3}\s+\d+)\s+(.+?)\s+(\d\.\d{2})\s+(\d\.\d{2})\s+([A-F][+-]?)\s+(\d+\.\d{3})", line
                )
                if course_match:
                    if buffer_special_topics:
                        course_records.append(buffer_special_topics)
                        buffer_special_topics = None

                    course_code = course_match.group(1).strip()
                    title = course_match.group(2).strip()
                    earned_credits = float(course_match.group(4))
                    grade = course_match.group(5)

                    prefix = course_code.split()[0]

                    if course_code in NON_CORE_ELECTIVE:
                        buffer_special_topics = {
                            "Semester": current_semester,
                            "Course Code": course_code,
                            "Title": "Special Topics in Physics",
                            "Credits Earned": earned_credits,
                            "Grade": grade,
                            "Classification": "Elective"
                        }
                    elif prefix == "PHY":
                        classification = "Research" if course_code in RESEARCH_COURSES else "Core"
                        course_records.append({
                            "Semester": current_semester,
                            "Course Code": course_code,
                            "Title": title,
                            "Credits Earned": earned_credits,
                            "Grade": grade,
                            "Classification": classification
                        })
                    else:
                        course_records.append({
                            "Semester": current_semester,
                            "Course Code": course_code,
                            "Title": title,
                            "Credits Earned": earned_credits,
                            "Grade": grade,
                            "Classification": "Invalid"
                        })

                elif "Course Topic:" in line and buffer_special_topics:
                    topic = line.split("Course Topic:")[-1].strip()
                    buffer_special_topics["Title"] = f"Special Topics: {topic}"
                    course_records.append(buffer_special_topics)
                    buffer_special_topics = None

    if buffer_special_topics:
        course_records.append(buffer_special_topics)

    return student_name, student_id, pd.DataFrame(course_records)

def generate_certification_csv_and_display(student_name, student_id, df, output_dir="output"):

    if any(df["Classification"] == "Invalid"):
        print(f"Certification FAILED for {student_name}: contains unapproved external courses.")
        return {
            "Student Name": student_name,
            "Student ID": student_id,
            "Certification": "Failed (Invalid External Course)"
        }

    df = df[["Semester", "Course Code", "Title", "Credits Earned", "Classification", "Grade"]]
    df = df.sort_values(by=["Classification", "Semester", "Course Code"])

    total_credits = 0
    core_credits = 0
    research_credits = 0
    four_xx_credits = 0

    for _, row in df.iterrows():
        course_code = row["Course Code"]
        credits = row["Credits Earned"]
        classification = row["Classification"]
        level = get_course_level(course_code)

        if level is None or level < 400:
            continue  # Skip <400-level courses

        total_credits += credits
        if classification == "Core":
            core_credits += credits
        if classification == "Research":
            research_credits += credits
        if 400 <= level < 500:
            four_xx_credits += credits

# This is where the certification logic is applied

    research_applied = min(6, research_credits)
    core_ok = core_credits >= 15
    total_ok = total_credits >= 30
    research_ok = research_applied <= 6
    four_xx_ok = four_xx_credits <= 6
    certification_ok = all([core_ok, total_ok, research_ok, four_xx_ok])

    summary_row = pd.DataFrame([{
        "Semester": "",
        "Course Code": "",
        "Title": "Total Credits Applied",
        "Credits Earned": total_credits,
        "Classification": "",
        "Grade": ""
    }])
    df_final = pd.concat([df, summary_row], ignore_index=True)

    quoted_id = f'="{student_id}"'
    names = student_name.lower().split()
    first_initial = names[0][0]
    clean_names = [n.strip(string.punctuation) for n in names if n.strip(string.punctuation).isalpha()]
    last_name = clean_names[-1] if clean_names else names[-1]
    filename = f"{first_initial}{last_name}_ms_phy_track.csv"

    output_path = Path(output_dir) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header_lines = [
        ["Prepared by", "Robert Fisher"],
        ["Student Name", student_name],
        ["Student ID", quoted_id]
    ]

    requirements = pd.DataFrame([
        ["**Graduation Requirement**", "≥15 Core Credits", int(core_credits), "Verified" if core_ok else "Not Met"],
        ["", "≤6 Research Credits Applied", int(research_applied), "Verified" if research_ok else "Not Met"],
        ["", "≤6 400-Level Credits Applied", int(four_xx_credits), "Verified" if four_xx_ok else "Not Met"],
        ["", "≥30 Total Credits", int(total_credits), "Verified" if total_ok else "Not Met"]
    ], columns=["", "Requirement", "Value", "Status"])

    if certification_ok:
        with open(output_path, "w", newline='') as f:
            for row in header_lines:
                f.write(",".join(row) + "\n")
            df_final.to_csv(f, index=False)
            f.write("\n")
            requirements.to_csv(f, index=False, header=False)

        print(f"Certification PASSED. CSV saved to: {output_path.resolve()}")
    else:
        print("Certification FAILED. Requirements not met.")

    print("\nCourse Record:")
    print(df_final.to_string(index=False))
    print("\nGraduation Requirements:")
    print(requirements.to_string(index=False))

    return {
        "Student Name": student_name,
        "Student ID": student_id,
        "Core Credits": int(core_credits),
        "Research Applied": int(research_applied),
        "400-Level Credits": int(four_xx_credits),
        "Total Credits": int(total_credits),
        "Certification": "Passed" if certification_ok else "Failed"
    }

for pdf_path in PDF_FILE_LIST:
    student_name, student_id, course_df = extract_courses_and_student_info(pdf_path)
    if student_name and student_id:
        summary_row = generate_certification_csv_and_display(student_name, student_id, course_df)
        summary_records.append(summary_row)
    else:
        print(f"Could not extract student name or ID from: {pdf_path}")

if summary_records:
    summary_df = pd.DataFrame(summary_records)
    summary_output_path = Path("output") / "certification_summary.csv"
    summary_df.to_csv(summary_output_path, index=False)
    print(f"\nSummary CSV saved to: {summary_output_path.resolve()}")

