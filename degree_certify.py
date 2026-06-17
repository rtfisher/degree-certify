#!/usr/bin/env python3
"""
degree_certify.py

Written by Robert Fisher, 060525

Description:
-------------
This script processes graduate transcript PDFs and certifies whether each student has met the M.S. Physics degree requirements.

It performs the following tasks:
1. Parses transcripts in PDF format using layout-based text extraction (supports two-column layouts).
2. Extracts student name, ID, and detailed course information.
3. Categorizes courses as Core, Elective, Research, or Exclude based on course codes and predefined rules.
4. Applies the following degree certification criteria:
    - At least 15 Core Credits
    - No more than 6 credits of Research courses may be applied
    - No more than 6 credits from 400-level (4XX) courses may be applied
    - Courses numbered below 400 (e.g., PHY 320) are excluded and do not count toward the 30-credit total
    - A minimum of 30 total graduate-level credits (500-level and above, including up to 6 credits of 400-level courses)
    - All non-PHY courses must be explicitly whitelisted as non-core electives (e.g., EAS 520); otherwise, certification fails

 These criteria may be adjusted for other programs; see the comment regarding "certification logic" below.

Interactive classification (--interactive):
-------------------------------------------
Many transcripts contain courses the static rules cannot classify on their own:
special-topics courses (PHY 510) whose topic determines whether they count as Core or
Elective, and graduate courses from other departments. By default the script is
NON-interactive: it applies the rulebook plus defaults (special topics -> Elective,
unknown external courses -> Exclude under EAS PhD, else Invalid). Passing --interactive
opens a cursor-driven terminal UI (see certify_tui.py): move between courses with the
Up/Down arrows and set the highlighted course's classification with a single keystroke
(c/e/r/x) or cycle it with Left/Right, with live credit totals and a PASS/FAIL banner.
Decisions are remembered in a local rulebook (course_classifications.json, gitignored)
keyed on "COURSE | Topic" for special topics and on the course code otherwise, so a
topic upgraded to Core (e.g. a special-topics offering later promoted to a core course)
is applied automatically on every future run.

EAS PhD students (auto-detected; --eas-phd / --no-eas-phd to override):
----------------------------------------------------------------------
EAS PhD students may earn the M.S. Physics "en route" to the doctorate and are
permitted to double-count up to 24 credits between the two degrees. EAS PhD mode is
auto-detected from the transcript's graduate Plan line (it names the Engineering &
Applied Science PhD program); use --eas-phd to force it on or --no-eas-phd to force it
off. In EAS PhD mode:
  - Unknown non-PHY courses are not auto-failed (they default to Exclude) so the PhD's
    research/seminar/minor courses do not block M.S. certification.
  - For a student who otherwise certifies, the fewest courses needed are reserved as
    SINGLE-counted (M.S.-only) so that no more than 24 credits are double-counted; in
    --interactive mode the certifier can adjust which ones (pick credits the PhD will
    not need). This is reported on the certificate, not enforced as a hard failure, and
    the single-counted courses are flagged in the per-student CSV. Selections are
    remembered per student in single_count.json (gitignored).

 Typical EAS PhD workflow (mode auto-detected; --interactive opens the editor):
     python3 degree_certify.py --interactive transcript.pdf

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
Pass/in-progress courses (grades "P", "IP", or blank, e.g. dissertation and seminar
research) do not match the course pattern and are therefore ignored automatically.

Transfer credits may appear just before the "Beginning of Graduate Record" marker, introduced by a line like:
    Transfer Credit from University of Massachusetts Dartmouth
These courses have a "T" grade (no GPA impact) and format:
    PHY 412 Elec & Magnt Fields II 3.00 3.00 T 0.000
Transfer credits in this location are included in the graduate degree course count.

 Only lines following this structure and occurring after the line:
     ---------- Beginning of Graduate Record ----------
 (or in the transfer credit section immediately preceding it)
 are considered valid for certification analysis.

Each semester appears as a line separated by whitespace, formatted as: "YYYY Fall|Spring". Program and plan are listed after each semester, prior to the text of the courses.

Outputs:
---------
- CSV for each student passing certification
- Terminal report for each transcript
- Summary CSV (`certification_summary.csv`) for all transcripts processed

Usage:
-------
    python3 degree_certify.py [--interactive] [--eas-phd | --no-eas-phd] [--output-dir DIR] <transcript1.pdf> [<transcript2.pdf> ...]
"""

import pdfplumber
import pandas as pd
import re
import sys
import string
import argparse
import json
import csv
from pathlib import Path
from datetime import datetime

RESEARCH_COURSES = {"PHY 680", "PHY 685", "PHY 690"}
NON_CORE_ELECTIVE = {"PHY 510", "EAS 502", "EAS 520", "MTH 573", "DSC 520"}

# Persistent, gitignored rulebooks for interactive decisions.
CLASSIFICATION_FILE = "course_classifications.json"
SINGLE_COUNT_FILE = "single_count.json"

# Minimum total credits required for the M.S. Physics degree.
MS_MIN_TOTAL_CREDITS = 30

# Maximum credits an EAS PhD student may double-count between the PhD and the M.S.
EAS_PHD_DOUBLE_COUNT_CAP = 24

# Normalized substring identifying an EAS PhD transcript from its graduate Plan line.
EAS_PHD_PLAN_SIGNATURE = "engineering & applied science phd"

# The classifications a course may be assigned.
CLASSIFICATIONS = ("Core", "Elective", "Research", "Exclude", "Invalid")


def get_course_level(course_code):
    match = re.search(r"\b(\d{3})\b", course_code)
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Persistent rulebook helpers
# ---------------------------------------------------------------------------

def load_classification_map(path=CLASSIFICATION_FILE):
    """Load the persisted course/special-topics classification rulebook."""
    data = {}
    if Path(path).exists():
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: could not read {path} ({e}); starting with an empty rulebook.")
            data = {}
    data.setdefault("special_topics", {})  # "COURSE | Topic" -> classification
    data.setdefault("courses", {})         # "COURSE" -> classification
    return data


def save_classification_map(data, path=CLASSIFICATION_FILE):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
    except OSError as e:
        print(f"Warning: could not save classification rulebook to {path} ({e}).")


def load_single_count_store(path=SINGLE_COUNT_FILE):
    if Path(path).exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: could not read {path} ({e}); starting fresh.")
    return {}


def save_single_count_store(data, path=SINGLE_COUNT_FILE):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
    except OSError as e:
        print(f"Warning: could not save single-count store to {path} ({e}).")


# ---------------------------------------------------------------------------
# PDF parsing
# ---------------------------------------------------------------------------

# The transcript is assumed to be have a two-column layout. We extract both.
def extract_column_text(page, left_col_bbox, right_col_bbox):
    left_lines = page.crop(left_col_bbox).extract_text().splitlines() if page.crop(left_col_bbox).extract_text() else []
    right_lines = page.crop(right_col_bbox).extract_text().splitlines() if page.crop(right_col_bbox).extract_text() else []
    return left_lines + right_lines


COURSE_RE = re.compile(
    r"([A-Z]{3}\s+\d+)\s+(.+?)\s+(\d\.\d{2})\s+(\d\.\d{2})\s+([A-FT][+-]?)\s+(\d+\.\d{3})"
)


def extract_courses_and_student_info(pdf_path):
    """Parse a transcript PDF into a DataFrame of courses (without final classification).

    Each record carries Semester, Course Code, Title, Credits Earned, Grade, and Topic
    (the special-topics description, or "" if none). Final Core/Elective/Research/Exclude
    classification is assigned later by resolve_classifications().
    """
    print(f"Opening PDF: {pdf_path}")
    course_records = []
    current_semester = ""
    pending = None  # last parsed course, held in case a "Course Topic:" line follows
    student_name = None
    student_id = None
    in_graduate_section = False
    in_potential_transfer_section = False  # Track potential transfer credits (buffered until confirmed)
    transfer_buffer = []  # Buffer to hold potential transfer courses until we confirm they precede graduate record
    detected_eas_phd = False  # Set if a graduate Plan line identifies the EAS PhD program

    def flush_pending(target):
        nonlocal pending
        if pending is not None:
            target.append(pending)
            pending = None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"PDF opened successfully, {len(pdf.pages)} pages")
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

                for line in lines:
                    # Beginning of graduate record - commit any buffered transfer credits.
                    if "Beginning of Graduate Record" in line:
                        flush_pending(transfer_buffer if in_potential_transfer_section else course_records)
                        if transfer_buffer:
                            print(f"Committing {len(transfer_buffer)} transfer courses to graduate record")
                            course_records.extend(transfer_buffer)
                            transfer_buffer = []
                        in_graduate_section = True
                        in_potential_transfer_section = False
                        print("Found graduate section marker")
                        continue

                    # Transfer credit section - buffer courses until confirmed (must precede graduate record).
                    if not in_graduate_section:
                        if "Transfer Credit from" in line:
                            flush_pending(transfer_buffer)
                            if transfer_buffer:
                                print(f"Discarding {len(transfer_buffer)} buffered courses (not followed by graduate record)")
                            transfer_buffer = []
                            in_potential_transfer_section = True
                            print(f"Found potential transfer credit section: {line}")
                            continue
                        if not in_potential_transfer_section:
                            continue

                    target_list = transfer_buffer if (in_potential_transfer_section and not in_graduate_section) else course_records

                    # Auto-detect EAS PhD from the graduate-record Program/Plan/Subplan blocks.
                    if in_graduate_section and not detected_eas_phd:
                        plan_match = re.match(r"\s*(?:Program|Plan|Subplan)\s*:\s*(.+)", line)
                        if plan_match and EAS_PHD_PLAN_SIGNATURE in re.sub(r"\s+", " ", plan_match.group(1)).lower():
                            detected_eas_phd = True
                            print("Detected EAS PhD program/plan in graduate record")

                    sem_match = re.match(r"\s*(\d{4})\s+(Fall|Spring|Sprng)", line)
                    if sem_match:
                        flush_pending(target_list)
                        year = sem_match.group(1)[-2:]
                        term = sem_match.group(2).replace("Sprng", "Spring")
                        current_semester = f"{'F' if term == 'Fall' else 'S'}{year}"
                        continue

                    course_match = COURSE_RE.search(line)
                    if course_match:
                        flush_pending(target_list)
                        course_code = course_match.group(1).strip()
                        title = course_match.group(2).strip()
                        earned_credits = float(course_match.group(4))
                        grade = course_match.group(5)
                        is_transfer = (grade == "T")
                        display_title = f"{title} (Transfer)" if is_transfer else title
                        pending = {
                            "Semester": current_semester,
                            "Course Code": course_code,
                            "Title": display_title,
                            "Credits Earned": earned_credits,
                            "Grade": grade,
                            "Topic": "",
                        }
                        continue

                    if "Course Topic:" in line and pending is not None:
                        topic = line.split("Course Topic:")[-1].strip()
                        pending["Topic"] = topic

            flush_pending(course_records)

        print(f"Found {len(course_records)} course records")
        return student_name, student_id, pd.DataFrame(course_records), detected_eas_phd

    except Exception as e:
        print(f"Error opening PDF: {e}")
        import traceback
        traceback.print_exc()
        return None, None, pd.DataFrame(), False


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_rows(df, eas_phd, class_map):
    """Build a per-course view with its resolved classification and edit metadata.

    Every course is keyed in the rulebook (special_topics["CODE | Topic"] if it has a
    topic line, else courses["CODE"]) and is editable, so the certifier can override
    ANY classification in the TUI. When no override exists the default rule applies
    (research set -> Research; special topic -> Elective when whitelisted/EAS, else the
    external default; whitelist -> Elective; PHY -> Core; other external -> Exclude under
    EAS PhD, else Invalid). This is the single source of truth used by both the
    non-interactive resolver and the TUI, so display and certification always agree.
    """
    rows = []
    for _, row in df.iterrows():
        code = row["Course Code"]
        topic = row.get("Topic", "") or ""
        base_title = row["Title"]
        title = f"{base_title}: {topic}" if topic else base_title
        prefix = code.split()[0]
        section, key = ("special_topics", f"{code} | {topic}") if topic else ("courses", code)
        cached_val = class_map[section].get(key)

        external_default = "Exclude" if eas_phd else "Invalid"
        if code in RESEARCH_COURSES:
            default, kind = "Research", "research"
        elif topic and (code in NON_CORE_ELECTIVE or eas_phd):
            default, kind = "Elective", "special_topic"
        elif code in NON_CORE_ELECTIVE:
            default, kind = "Elective", "whitelist"
        elif prefix == "PHY":
            default, kind = "Core", "phy_core"
        elif topic:
            # Standard-mode special topic outside the whitelist: historically external.
            default, kind = external_default, "special_topic"
        else:
            default, kind = external_default, "external"

        rows.append({
            "semester": row["Semester"], "code": code, "title": title, "topic": topic,
            "credits": row["Credits Earned"], "grade": row["Grade"],
            "id": applied_row_id(row), "level": get_course_level(code),
            "section": section, "key": key, "default": default, "kind": kind,
            "cached": cached_val is not None, "editable": True,
            "classification": cached_val if cached_val is not None else default,
        })
    return rows


def count_credits(rows):
    """Tally applicable credits over classified course views (see classify_rows).

    Mirrors the certification credit rules: Invalid/Exclude and sub-400-level courses
    do not count. Returns totals plus the list of applied courses.
    """
    total = core = research = four_xx = 0.0
    has_invalid = False
    applied = []
    for v in rows:
        cls = v["classification"]
        level = v["level"]
        credits = v["credits"]
        if cls == "Invalid":
            has_invalid = True
        if cls in ("Invalid", "Exclude") or level is None or level < 400:
            continue
        total += credits
        if cls == "Core":
            core += credits
        if cls == "Research":
            research += credits
        if 400 <= level < 500:
            four_xx += credits
        applied.append({"id": v["id"], "code": v["code"], "title": v["title"],
                        "credits": credits, "classification": cls})
    return {"total": total, "core": core, "research": research, "four_xx": four_xx,
            "has_invalid": has_invalid, "applied": applied}


def resolve_classifications(df, eas_phd, class_map):
    """Apply Core/Elective/Research/Exclude/Invalid to each course (non-interactive).

    Decisions come from the rulebook; unknown courses fall back to defaults (special
    topics -> Elective; external -> Exclude under EAS PhD, else Invalid). Any interactive
    editing happens earlier in the TUI, which writes the rulebook this reads.
    """
    if df.empty:
        df = df.copy()
        df["Classification"] = []
        return df
    rows = classify_rows(df, eas_phd, class_map)
    df = df.copy()
    df["Classification"] = [v["classification"] for v in rows]
    df["Title"] = [v["title"] for v in rows]
    return df


def certifies(counts):
    """Return True if the applied-credit totals meet the M.S. Physics requirements."""
    return (counts["core"] >= 15 and counts["total"] >= MS_MIN_TOTAL_CREDITS
            and min(6, counts["research"]) <= 6 and counts["four_xx"] <= 6
            and not counts["has_invalid"])


# ---------------------------------------------------------------------------
# EAS PhD double-count designation
# ---------------------------------------------------------------------------

def applied_row_id(row):
    return f"{row['Semester']}|{row['Course Code']}|{row.get('Topic', '')}"


def single_count_required(total_credits):
    """Minimum credits that must be single-counted (reserved for the M.S. only).

    The M.S. needs MS_MIN_TOTAL_CREDITS and at most EAS_PHD_DOUBLE_COUNT_CAP of those
    may be shared with the PhD, so only (MS_MIN_TOTAL_CREDITS - cap) credits must be
    M.S.-only -- regardless of how many surplus credits the student earned. Surplus
    credits beyond the M.S. minimum need not be reserved.
    """
    return max(0.0, min(total_credits, MS_MIN_TOTAL_CREDITS) - EAS_PHD_DOUBLE_COUNT_CAP)


def minimal_single_count(applied, required):
    """Fewest applied courses covering `required` credits.

    Largest-credit first (minimizes the course count), and among equal credits prefer
    non-core courses (electives/research), which are least likely to be needed for the
    PhD's core requirements.
    """
    order = sorted(applied, key=lambda c: (-c["credits"], c["classification"] == "Core"))
    selected, running = [], 0.0
    for c in order:
        if running >= required:
            break
        selected.append(c)
        running += c["credits"]
    return selected


def designate_single_counted(applied, total_credits, student_id, store):
    """Resolve the single-counted courses for an EAS PhD student (non-interactive).

    Honors a saved per-student selection when it still covers the requirement (e.g. an
    explicit choice made earlier in the TUI); otherwise reserves the fewest courses
    automatically and records that. Returns the selected applied-course dicts.
    """
    required = single_count_required(total_credits)
    if required <= 0:
        return []
    saved_ids = store.get(student_id)
    if saved_ids:
        saved_sel = [c for c in applied if c["id"] in saved_ids]
        if saved_sel and sum(c["credits"] for c in saved_sel) >= required:
            return saved_sel
    minimal = minimal_single_count(applied, required)
    store[student_id] = [c["id"] for c in minimal]
    return minimal


# ---------------------------------------------------------------------------
# Resuming from a prior per-student certification CSV
# ---------------------------------------------------------------------------

def student_csv_filename(student_name, student_id):
    """The per-student certification CSV name: {firstinitial}{lastname}_{id}_ms_phy_track.csv."""
    names = student_name.lower().split()
    first_initial = names[0][0]
    clean = [n.strip(string.punctuation) for n in names if n.strip(string.punctuation).isalpha()]
    last_name = clean[-1] if clean else names[-1]
    return f"{first_initial}{last_name}_{student_id}_ms_phy_track.csv"


def read_prior_certification(csv_path):
    """Parse a prior per-student certification CSV.

    Returns ({(course_code, display_title): classification}, {(course_code, display_title)
    that were single-counted}). Keyed on (code, displayed title) so the rows can be matched
    back to freshly-parsed courses (the title carries the special-topics topic). Returns
    empties if the file is missing/unreadable or has no recognizable course table.
    """
    classifications, single = {}, set()
    try:
        with open(csv_path, newline="") as f:
            rows = list(csv.reader(f))
    except OSError:
        return classifications, single

    header = has_sc = None
    for i, r in enumerate(rows):
        if len(r) >= 6 and r[1] == "Course Code" and r[4] == "Classification":
            header = i
            has_sc = len(r) > 6 and r[6] == "Single-Counted"
            break
    if header is None:
        return classifications, single

    for r in rows[header + 1:]:
        if not any(cell.strip() for cell in r) or len(r) < 5 or not r[1].strip():
            break  # blank line or the "Total Credits Applied" summary row ends the courses
        key = (r[1].strip(), r[2].strip())
        classifications[key] = r[4].strip()
        if has_sc and len(r) > 6 and r[6].strip() == "M.S.-only":
            single.add(key)
    return classifications, single


# ---------------------------------------------------------------------------
# Certification
# ---------------------------------------------------------------------------

def generate_certification_csv_and_display(student_name, student_id, df, eas_phd, interactive,
                                           single_count_store, output_dir="output"):
    print(f"Processing certification for {student_name}")

    # Check for invalid courses but continue processing
    has_invalid_courses = any(df["Classification"] == "Invalid")

    df = df[["Semester", "Course Code", "Title", "Credits Earned", "Classification", "Grade", "Topic"]]
    df = df.sort_values(by=["Classification", "Semester", "Course Code"])

    total_credits = 0
    core_credits = 0
    research_credits = 0
    four_xx_credits = 0
    applied = []  # courses that count toward the M.S. (for EAS PhD single-count designation)

    for _, row in df.iterrows():
        course_code = row["Course Code"]
        credits = row["Credits Earned"]
        classification = row["Classification"]
        level = get_course_level(course_code)

        # Skip non-counting courses and courses below 400 level for credit counting.
        if classification in ("Invalid", "Exclude") or level is None or level < 400:
            continue

        total_credits += credits
        if classification == "Core":
            core_credits += credits
        if classification == "Research":
            research_credits += credits
        if 400 <= level < 500:
            four_xx_credits += credits

        applied.append({
            "id": applied_row_id(row),
            "code": course_code,
            "title": row["Title"],
            "credits": credits,
            "classification": classification,
        })

    # This is where the certification logic is applied
    research_applied = min(6, research_credits)
    core_ok = core_credits >= 15
    total_ok = total_credits >= MS_MIN_TOTAL_CREDITS
    research_ok = research_applied <= 6
    four_xx_ok = four_xx_credits <= 6
    certification_ok = all([core_ok, total_ok, research_ok, four_xx_ok]) and not has_invalid_courses

    # EAS PhD: reserve the fewest courses as single-counted (reported, not a failure gate).
    # Only designate when the student otherwise certifies -- single-counting credits is
    # moot if the degree requirements are not met, and prompting for it would be confusing.
    eas_designated = eas_phd and certification_ok
    single_counted = []
    required_single = double_counted_credits = single_counted_credits = 0
    if eas_designated:
        required_single = single_count_required(total_credits)
        # In interactive mode, let the certifier pick which courses are reserved (TUI
        # writes the per-student store); designate then honors that selection.
        if interactive and required_single > 0:
            import certify_tui
            certify_tui.select_single_counted(
                applied, required_single, single_count_store, student_id, minimal_single_count
            )
        single_counted = designate_single_counted(
            applied, total_credits, student_id, single_count_store
        )
        single_counted_credits = sum(c["credits"] for c in single_counted)
        # Up to the cap may be shared with the PhD; surplus beyond the M.S. minimum
        # is neither single- nor double-counted.
        double_counted_credits = min(EAS_PHD_DOUBLE_COUNT_CAP, total_credits - single_counted_credits)
        # Flag each single-counted course inline in the course-record table.
        single_ids = {c["id"] for c in single_counted}
        df = df.copy()
        df["Single-Counted"] = ["M.S.-only" if applied_row_id(r) in single_ids else ""
                                for _, r in df.iterrows()]

    summary_dict = {
        "Semester": "",
        "Course Code": "",
        "Title": "Total Credits Applied",
        "Credits Earned": total_credits,
        "Classification": "",
        "Grade": "",
        "Topic": "",
    }
    if eas_designated:
        summary_dict["Single-Counted"] = ""
    summary_row = pd.DataFrame([summary_dict])
    df_display = df.drop(columns=["Topic"])
    df_final = pd.concat([df_display, summary_row.drop(columns=["Topic"])], ignore_index=True)

    quoted_id = f'="{student_id}"'
    output_path = Path(output_dir) / student_csv_filename(student_name, student_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Add certification status to header
    certification_status = "CERTIFICATION PASSED" if certification_ok else "CERTIFICATION FAILED"

    header_lines = [
        ["STATUS", certification_status],  # Add clear status at the top
        ["Prepared by", "Robert Fisher"],
        ["Student Name", student_name],
        ["Student ID", quoted_id],
    ]
    if eas_phd:
        header_lines.append(["Track", "EAS PhD (M.S. Physics en route)"])

    requirements = pd.DataFrame([
        ["**Graduation Requirement**", "≥15 Core Credits", int(core_credits), "Verified" if core_ok else "Not Met"],
        ["", "≤6 Research Credits Applied", int(research_applied), "Verified" if research_ok else "Not Met"],
        ["", "≤6 400-Level Credits Applied", int(four_xx_credits), "Verified" if four_xx_ok else "Not Met"],
        ["", "≥30 Total Credits", int(total_credits), "Verified" if total_ok else "Not Met"]
    ], columns=["", "Requirement", "Value", "Status"])

    # Add invalid course requirement if applicable
    if has_invalid_courses:
        invalid_row = pd.DataFrame([
            ["", "No Invalid External Courses", "FOUND", "Not Met"]
        ], columns=["", "Requirement", "Value", "Status"])
        requirements = pd.concat([requirements, invalid_row], ignore_index=True)

    # EAS PhD double-count reporting (informational, not a pass/fail gate).
    single_count_ok = single_counted_credits >= required_single
    if eas_designated:
        dc_rows = pd.DataFrame([
            ["", f"≥{int(required_single)} Credits Single-Counted (M.S. only)", int(single_counted_credits),
             "Verified" if single_count_ok else "Not Met"],
            ["", f"≤{EAS_PHD_DOUBLE_COUNT_CAP} Credits Double-Counted with PhD", int(double_counted_credits),
             "Verified"],
        ], columns=["", "Requirement", "Value", "Status"])
        requirements = pd.concat([requirements, dc_rows], ignore_index=True)

    # Always generate CSV file regardless of certification status
    try:
        with open(output_path, "w", newline='') as f:
            for row in header_lines:
                f.write(",".join(row) + "\n")
            df_final.to_csv(f, index=False)
            f.write("\n")
            requirements.to_csv(f, index=False, header=False)

            if eas_designated and single_counted:
                f.write("\nSingle-Counted Courses (reserved for M.S. Physics only)\n")
                for c in single_counted:
                    f.write(f",{c['code']},{c['title']},{c['credits']:.2f}\n")

            # Add final status line at the bottom for extra clarity
            f.write(f"\nFINAL STATUS,{certification_status}\n")

        if certification_ok:
            print(f"Certification PASSED. CSV saved to: {output_path.resolve()}")
        else:
            failure_reason = "contains unapproved external courses" if has_invalid_courses else "does not meet degree requirements"
            print(f"Certification FAILED for {student_name}: {failure_reason}")
            print(f"CSV saved to: {output_path.resolve()}")

        print("\nCourse Record:")
        print(df_final.to_string(index=False))
        print("\nGraduation Requirements:")
        print(requirements.to_string(index=False))
        if eas_designated:
            if single_counted:
                print("\nSingle-Counted Courses (reserved for M.S. Physics only):")
                for c in single_counted:
                    print(f"  {c['code']:<8} {c['title']:<40} {c['credits']:.2f} cr")
            print(f"\nSingle-counted (M.S. only): {int(single_counted_credits)} cr "
                  f"(minimum {int(required_single)}); up to {int(double_counted_credits)} cr "
                  f"may be double-counted with the EAS PhD (cap {EAS_PHD_DOUBLE_COUNT_CAP}).")
            if not single_count_ok:
                print("  NOTE: fewer than the required single-counted credits were reserved.")
        elif eas_phd:
            print("\nEAS PhD: single-count designation skipped — the M.S. requirements are not "
                  "yet met, so there is nothing to certify or reserve.")

    except Exception as e:
        print(f"Error writing CSV file for {student_name}: {e}")
        import traceback
        traceback.print_exc()

    record = {
        "Student Name": student_name,
        "Student ID": student_id,
        "Core Credits": int(core_credits),
        "Research Applied": int(research_applied),
        "400-Level Credits": int(four_xx_credits),
        "Total Credits": int(total_credits),
        "Certification": "Passed" if certification_ok else ("Failed (Invalid External Course)" if has_invalid_courses else "Failed"),
        "Certification Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    if eas_phd:
        record["Double-Counted Credits"] = int(double_counted_credits)
        record["Single-Counted Credits"] = int(single_counted_credits)
    return record


def resolve_effective_eas_phd(args, detected):
    """Combine auto-detection with the explicit override flags into one boolean."""
    if args.no_eas_phd:
        return False
    if args.eas_phd:
        return True
    return detected


def announce_track(detected, effective, args):
    """Print what EAS PhD track was used and warn on any override mismatch."""
    if args.no_eas_phd and detected:
        print("EAS PhD plan detected in transcript, but overridden OFF by --no-eas-phd.")
    elif args.eas_phd and not detected:
        print("EAS PhD mode forced ON by --eas-phd (no EAS PhD plan detected in transcript).")
    elif effective and detected:
        print("EAS PhD track auto-detected from transcript.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Process graduate transcript PDFs and certify degree requirements.")
    parser.add_argument("transcripts", nargs="+", help="PDF transcript files to process")
    parser.add_argument("--output-dir", default="output", help="Output directory for certification results (default: output)")
    parser.add_argument("--interactive", action="store_true",
                        help="Open the interactive TUI to classify/revise courses (and choose single-counted credits for EAS PhD); decisions are saved to the rulebook")
    parser.add_argument("--eas-phd", action="store_true",
                        help="Force EAS PhD mode on (it is auto-detected from the transcript's graduate Plan by default)")
    parser.add_argument("--no-eas-phd", action="store_true",
                        help="Force EAS PhD mode off even if the transcript's plan is auto-detected as EAS PhD")
    parser.add_argument("--rulebook", default=CLASSIFICATION_FILE,
                        help=f"Path to the classification rulebook JSON (default: {CLASSIFICATION_FILE})")
    parser.add_argument("--single-count-file", default=SINGLE_COUNT_FILE,
                        help=f"Path to the EAS PhD single-count store JSON (default: {SINGLE_COUNT_FILE})")
    args = parser.parse_args(argv)
    if args.eas_phd and args.no_eas_phd:
        parser.error("--eas-phd and --no-eas-phd are mutually exclusive")

    class_map = load_classification_map(args.rulebook)
    single_count_store = load_single_count_store(args.single_count_file)
    summary_records = []
    any_eas = False

    for pdf_path in args.transcripts:
        print(f"Processing: {pdf_path}")
        try:
            student_name, student_id, course_df, detected_eas = extract_courses_and_student_info(pdf_path)
            eas_phd = resolve_effective_eas_phd(args, detected_eas)
            any_eas = any_eas or eas_phd
            announce_track(detected_eas, eas_phd, args)
            print(f"Extracted - Name: {student_name}, ID: {student_id}")
            print(f"Course dataframe shape: {course_df.shape}")

            if student_name and student_id and not course_df.empty:
                # Resume from this student's prior certification CSV if one exists. A
                # resumed student uses a private classification map (the global rulebook
                # overlaid with the CSV) and never writes back to the global rulebook --
                # the per-student CSV is that student's source of truth.
                work_map, resumed = class_map, False
                csv_path = Path(args.output_dir) / student_csv_filename(student_name, student_id)
                if csv_path.exists():
                    prior_cls, prior_single = read_prior_certification(csv_path)
                    if prior_cls:
                        work_map = {"special_topics": dict(class_map["special_topics"]),
                                    "courses": dict(class_map["courses"])}
                        seeded = classify_rows(course_df, eas_phd, work_map)
                        for v in seeded:
                            cls = prior_cls.get((v["code"], v["title"]))
                            if cls:
                                work_map[v["section"]][v["key"]] = cls
                        single_ids = [v["id"] for v in seeded
                                      if (v["code"], v["title"]) in prior_single]
                        if single_ids:
                            single_count_store[student_id] = single_ids
                        resumed = True
                        print(f"Resuming from existing certification {csv_path.name} "
                              f"({len(prior_cls)} courses, {len(prior_single)} single-counted)")

                if args.interactive:
                    import certify_tui
                    if certify_tui.edit_classifications(course_df, work_map, eas_phd,
                                                        classify_rows, count_credits) and not resumed:
                        save_classification_map(work_map, args.rulebook)
                course_df = resolve_classifications(course_df, eas_phd, work_map)
                print("Calling generate_certification_csv_and_display...")
                summary_row = generate_certification_csv_and_display(
                    student_name, student_id, course_df, eas_phd, args.interactive,
                    single_count_store, output_dir=args.output_dir
                )
                print(f"Generated summary: {summary_row}")
                summary_records.append(summary_row)
            else:
                print(f"Could not extract student name or ID from: {pdf_path}")
                if course_df.empty:
                    print("No course records found - check if 'Beginning of Graduate Record' marker exists")
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            import traceback
            traceback.print_exc()

    if any_eas:
        save_single_count_store(single_count_store, args.single_count_file)

    if summary_records:
        summary_df = pd.DataFrame(summary_records)
        summary_output_path = Path(args.output_dir) / "certification_summary.csv"
        summary_output_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to existing file or create new one with headers
        file_exists = summary_output_path.exists()
        summary_df.to_csv(summary_output_path, mode='a', index=False, header=not file_exists)

        action = "appended to" if file_exists else "created"
        print(f"\nSummary CSV {action}: {summary_output_path.resolve()}")
    else:
        print("No records processed successfully.")


if __name__ == "__main__":
    main()
