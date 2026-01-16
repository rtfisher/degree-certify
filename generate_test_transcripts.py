#!/usr/bin/env python3
"""
generate_test_transcripts.py

Generates synthetic PDF transcripts for testing degree_certify.py.
Creates 8 test cases: 4 passing and 4 failing certification scenarios.

Transcripts use a realistic two-column layout matching actual university transcripts.
"""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pathlib import Path


# Standard undergraduate curriculum (~120 credits over 8 semesters)
UNDERGRAD_SEMESTERS = [
    # Freshman Fall
    {
        'term': '2019 Fall',
        'courses': [
            {'dept': 'PHY', 'num': '151', 'title': 'General Physics I', 'credits': 4, 'grade': 'A'},
            {'dept': 'MTH', 'num': '151', 'title': 'Calculus I', 'credits': 4, 'grade': 'A'},
            {'dept': 'CHM', 'num': '111', 'title': 'General Chemistry I', 'credits': 4, 'grade': 'A-'},
            {'dept': 'ENG', 'num': '101', 'title': 'Composition I', 'credits': 3, 'grade': 'B+'},
        ]
    },
    # Freshman Spring
    {
        'term': '2020 Spring',
        'courses': [
            {'dept': 'PHY', 'num': '152', 'title': 'General Physics II', 'credits': 4, 'grade': 'A'},
            {'dept': 'MTH', 'num': '152', 'title': 'Calculus II', 'credits': 4, 'grade': 'A-'},
            {'dept': 'CHM', 'num': '112', 'title': 'General Chemistry II', 'credits': 4, 'grade': 'B+'},
            {'dept': 'ENG', 'num': '102', 'title': 'Composition II', 'credits': 3, 'grade': 'A'},
        ]
    },
    # Sophomore Fall
    {
        'term': '2020 Fall',
        'courses': [
            {'dept': 'PHY', 'num': '253', 'title': 'Modern Physics', 'credits': 3, 'grade': 'A'},
            {'dept': 'MTH', 'num': '251', 'title': 'Calculus III', 'credits': 4, 'grade': 'A'},
            {'dept': 'PHY', 'num': '271', 'title': 'Physics Lab I', 'credits': 2, 'grade': 'A'},
            {'dept': 'CSC', 'num': '101', 'title': 'Intro Programming', 'credits': 3, 'grade': 'B+'},
            {'dept': 'HIS', 'num': '101', 'title': 'World History I', 'credits': 3, 'grade': 'A-'},
        ]
    },
    # Sophomore Spring
    {
        'term': '2021 Spring',
        'courses': [
            {'dept': 'PHY', 'num': '254', 'title': 'Thermal Physics', 'credits': 3, 'grade': 'A-'},
            {'dept': 'MTH', 'num': '252', 'title': 'Differential Equations', 'credits': 4, 'grade': 'A'},
            {'dept': 'PHY', 'num': '272', 'title': 'Physics Lab II', 'credits': 2, 'grade': 'A'},
            {'dept': 'CSC', 'num': '102', 'title': 'Data Structures', 'credits': 3, 'grade': 'B'},
            {'dept': 'HIS', 'num': '102', 'title': 'World History II', 'credits': 3, 'grade': 'A'},
        ]
    },
    # Junior Fall
    {
        'term': '2021 Fall',
        'courses': [
            {'dept': 'PHY', 'num': '311', 'title': 'Mechanics', 'credits': 3, 'grade': 'A'},
            {'dept': 'PHY', 'num': '321', 'title': 'Electromagnetism I', 'credits': 3, 'grade': 'A-'},
            {'dept': 'MTH', 'num': '331', 'title': 'Linear Algebra', 'credits': 3, 'grade': 'A'},
            {'dept': 'PHY', 'num': '371', 'title': 'Physics Lab III', 'credits': 2, 'grade': 'A'},
            {'dept': 'PSY', 'num': '101', 'title': 'Intro Psychology', 'credits': 3, 'grade': 'A-'},
        ]
    },
    # Junior Spring
    {
        'term': '2022 Spring',
        'courses': [
            {'dept': 'PHY', 'num': '322', 'title': 'Electromagnetism II', 'credits': 3, 'grade': 'A'},
            {'dept': 'PHY', 'num': '341', 'title': 'Quantum Mechanics I', 'credits': 3, 'grade': 'A'},
            {'dept': 'MTH', 'num': '332', 'title': 'Complex Analysis', 'credits': 3, 'grade': 'B+'},
            {'dept': 'PHY', 'num': '372', 'title': 'Physics Lab IV', 'credits': 2, 'grade': 'A'},
            {'dept': 'SOC', 'num': '101', 'title': 'Intro Sociology', 'credits': 3, 'grade': 'A'},
        ]
    },
    # Senior Fall
    {
        'term': '2022 Fall',
        'courses': [
            {'dept': 'PHY', 'num': '342', 'title': 'Quantum Mechanics II', 'credits': 3, 'grade': 'A'},
            {'dept': 'PHY', 'num': '351', 'title': 'Statistical Mechanics', 'credits': 3, 'grade': 'A-'},
            {'dept': 'PHY', 'num': '411', 'title': 'Adv Mechanics', 'credits': 3, 'grade': 'A'},
            {'dept': 'PHY', 'num': '491', 'title': 'Senior Seminar', 'credits': 1, 'grade': 'A'},
            {'dept': 'PHL', 'num': '201', 'title': 'Ethics', 'credits': 3, 'grade': 'A-'},
        ]
    },
    # Senior Spring
    {
        'term': '2023 Spring',
        'courses': [
            {'dept': 'PHY', 'num': '412', 'title': 'Elec & Magnt Fields II', 'credits': 3, 'grade': 'A'},
            {'dept': 'PHY', 'num': '421', 'title': 'Optics', 'credits': 3, 'grade': 'A'},
            {'dept': 'PHY', 'num': '492', 'title': 'Senior Thesis', 'credits': 3, 'grade': 'A'},
            {'dept': 'PHY', 'num': '471', 'title': 'Adv Physics Lab', 'credits': 2, 'grade': 'A'},
            {'dept': 'ART', 'num': '101', 'title': 'Art Appreciation', 'credits': 3, 'grade': 'B+'},
        ]
    },
]


def grade_to_points(grade):
    """Convert letter grade to grade points."""
    grade_map = {
        'A+': 4.0, 'A': 4.0, 'A-': 3.7,
        'B+': 3.3, 'B': 3.0, 'B-': 2.7,
        'C+': 2.3, 'C': 2.0, 'C-': 1.7,
        'D+': 1.3, 'D': 1.0, 'D-': 0.7,
        'F': 0.0, 'T': 0.0
    }
    return grade_map.get(grade, 0.0)


class TranscriptGenerator:
    """Generates two-column PDF transcripts."""

    def __init__(self, filename, student_name, student_id):
        self.filename = str(filename)
        self.student_name = student_name
        self.student_id = student_id
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        self.c = canvas.Canvas(self.filename, pagesize=letter)
        self.width, self.height = letter

        # Column positions
        self.left_col_x = 0.4 * inch
        self.right_col_x = self.width / 2 + 0.2 * inch
        self.col_width = self.width / 2 - 0.6 * inch

        # Track position in each column (start well below header area)
        self.left_y = self.height - 1.7 * inch
        self.right_y = self.height - 1.7 * inch
        self.current_col = 'left'  # Start with left column

        # Cumulative totals
        self.cum_attempted = 0.0
        self.cum_earned = 0.0
        self.cum_gpa_units = 0.0
        self.cum_points = 0.0

        # Draw header on first page
        self._draw_header()

    def _draw_header(self):
        """Draw the transcript header in a single-column area above the two-column content."""
        y = self.height - 0.5 * inch
        self.c.setFont("Helvetica-Bold", 14)
        self.c.drawCentredString(self.width / 2, y, "UNOFFICIAL ACADEMIC TRANSCRIPT")

        y -= 0.25 * inch
        self.c.setFont("Helvetica", 10)
        self.c.drawCentredString(self.width / 2, y, "Westbrook State University")

        y -= 0.35 * inch
        self.c.setFont("Helvetica", 10)
        self.c.drawString(0.5 * inch, y, f"Name: {self.student_name}")
        y -= 0.2 * inch
        self.c.drawString(0.5 * inch, y, f"Student ID: {self.student_id}")

        # Draw a separator line to clearly end the header area
        y -= 0.15 * inch
        self.c.line(0.5 * inch, y, self.width - 0.5 * inch, y)

    def _get_current_x(self):
        """Get x position for current column."""
        return self.left_col_x if self.current_col == 'left' else self.right_col_x

    def _get_current_y(self):
        """Get y position for current column."""
        return self.left_y if self.current_col == 'left' else self.right_y

    def _set_current_y(self, y):
        """Set y position for current column."""
        if self.current_col == 'left':
            self.left_y = y
        else:
            self.right_y = y

    def _advance_y(self, amount):
        """Move down by amount in current column."""
        if self.current_col == 'left':
            self.left_y -= amount
        else:
            self.right_y -= amount

    def _check_page_break(self, needed_height):
        """Check if we need to switch columns or pages."""
        current_y = self._get_current_y()

        if current_y - needed_height < 0.75 * inch:
            if self.current_col == 'left':
                # Switch to right column
                self.current_col = 'right'
            else:
                # Need new page
                self.c.showPage()
                self.left_y = self.height - 0.75 * inch
                self.right_y = self.height - 0.75 * inch
                self.current_col = 'left'

    def _draw_section_marker(self, text):
        """Draw a section marker like 'Beginning of Graduate Record'."""
        self._check_page_break(0.4 * inch)
        x = self._get_current_x()
        y = self._get_current_y()

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(x, y, f"---------- {text} ----------")
        self._advance_y(0.25 * inch)

    def _draw_semester_header(self, term):
        """Draw semester header with column labels."""
        self._check_page_break(0.5 * inch)
        x = self._get_current_x()
        y = self._get_current_y()

        # Term header
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(x, y, term)
        self._advance_y(0.18 * inch)

        # Column headers
        y = self._get_current_y()
        self.c.setFont("Helvetica", 7)
        self.c.drawString(x, y, "Course")
        self.c.drawString(x + 0.55 * inch, y, "Description")
        self.c.drawString(x + 2.0 * inch, y, "Atmpt")
        self.c.drawString(x + 2.4 * inch, y, "Earn")
        self.c.drawString(x + 2.75 * inch, y, "Grade")
        self.c.drawString(x + 3.1 * inch, y, "Points")
        self._advance_y(0.15 * inch)

    def _draw_course_line(self, course, is_transfer=False):
        """Draw a single course line."""
        self._check_page_break(0.18 * inch)
        x = self._get_current_x()
        y = self._get_current_y()

        grade = 'T' if is_transfer else course.get('grade', 'A')
        credits = course['credits']
        points = 0.0 if is_transfer else grade_to_points(grade) * credits

        self.c.setFont("Helvetica", 8)
        self.c.drawString(x, y, f"{course['dept']} {course['num']}")
        # Truncate title if too long
        title = course['title'][:18]
        self.c.drawString(x + 0.55 * inch, y, title)
        self.c.drawString(x + 2.0 * inch, y, f"{credits:.2f}")
        self.c.drawString(x + 2.4 * inch, y, f"{credits:.2f}")
        self.c.drawString(x + 2.75 * inch, y, grade)
        self.c.drawString(x + 3.1 * inch, y, f"{points:.3f}")
        self._advance_y(0.15 * inch)

        return credits, credits, points

    def _draw_term_totals(self, term_attempted, term_earned, term_points):
        """Draw term GPA and totals."""
        x = self._get_current_x()
        y = self._get_current_y()

        term_gpa = term_points / term_earned if term_earned > 0 else 0.0

        # Update cumulative
        self.cum_attempted += term_attempted
        self.cum_earned += term_earned
        self.cum_gpa_units += term_earned
        self.cum_points += term_points
        cum_gpa = self.cum_points / self.cum_gpa_units if self.cum_gpa_units > 0 else 0.0

        self.c.setFont("Helvetica", 7)

        # Term totals line
        self._advance_y(0.05 * inch)
        y = self._get_current_y()
        self.c.drawString(x, y, "Term Totals:")
        self.c.drawString(x + 2.0 * inch, y, f"{term_attempted:.2f}")
        self.c.drawString(x + 2.4 * inch, y, f"{term_earned:.2f}")
        self.c.drawString(x + 2.75 * inch, y, f"{term_gpa:.3f}")
        self.c.drawString(x + 3.1 * inch, y, f"{term_points:.3f}")
        self._advance_y(0.13 * inch)

        # Cum totals line
        y = self._get_current_y()
        self.c.drawString(x, y, "Cum Totals:")
        self.c.drawString(x + 2.0 * inch, y, f"{self.cum_attempted:.2f}")
        self.c.drawString(x + 2.4 * inch, y, f"{self.cum_earned:.2f}")
        self.c.drawString(x + 2.75 * inch, y, f"{cum_gpa:.3f}")
        self.c.drawString(x + 3.1 * inch, y, f"{self.cum_points:.3f}")
        self._advance_y(0.25 * inch)

    def draw_semester(self, term, courses, is_transfer=False):
        """Draw a complete semester block."""
        # Estimate height needed for this semester
        needed_height = 0.5 * inch + len(courses) * 0.15 * inch + 0.4 * inch
        self._check_page_break(needed_height)

        self._draw_semester_header(term)

        term_attempted = 0.0
        term_earned = 0.0
        term_points = 0.0

        for course in courses:
            atmpt, earn, pts = self._draw_course_line(course, is_transfer)
            term_attempted += atmpt
            term_earned += earn
            if not is_transfer:
                term_points += pts

        self._draw_term_totals(term_attempted, term_earned, term_points)

    def draw_degrees_awarded(self, degree="Bachelor of Science", confer_date="May 2023",
                               plan="Physics", honours=None):
        """Draw the Degrees Awarded section after undergraduate record."""
        self._check_page_break(0.9 * inch)
        x = self._get_current_x()
        y = self._get_current_y()

        # Calculate final undergrad GPA
        final_gpa = self.cum_points / self.cum_gpa_units if self.cum_gpa_units > 0 else 0.0

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(x, y, "---------- Degrees Awarded ----------")
        self._advance_y(0.2 * inch)

        self.c.setFont("Helvetica", 8)
        y = self._get_current_y()
        self.c.drawString(x, y, f"Degree: {degree}")
        self._advance_y(0.15 * inch)

        y = self._get_current_y()
        self.c.drawString(x, y, f"Confer Date: {confer_date}")
        self._advance_y(0.15 * inch)

        y = self._get_current_y()
        self.c.drawString(x, y, f"Degree GPA: {final_gpa:.3f}")
        self._advance_y(0.15 * inch)

        if honours:
            y = self._get_current_y()
            self.c.drawString(x, y, f"Degree Honours: {honours}")
            self._advance_y(0.15 * inch)

        y = self._get_current_y()
        self.c.drawString(x, y, f"Plan: {plan}")
        self._advance_y(0.25 * inch)

    def _reset_cumulative_totals(self):
        """Reset cumulative totals for a new academic career (e.g., entering graduate school)."""
        self.cum_attempted = 0.0
        self.cum_earned = 0.0
        self.cum_gpa_units = 0.0
        self.cum_points = 0.0

    def draw_transfer_section(self, institution, courses):
        """Draw transfer credit section."""
        self._check_page_break(0.6 * inch)
        x = self._get_current_x()
        y = self._get_current_y()

        self.c.setFont("Helvetica-Bold", 8)
        self.c.drawString(x, y, f"Transfer Credit from {institution}")
        self._advance_y(0.2 * inch)

        # Draw transfer courses without term structure
        self._draw_semester_header("Transfer")

        term_attempted = 0.0
        term_earned = 0.0

        for course in courses:
            atmpt, earn, _ = self._draw_course_line(course, is_transfer=True)
            term_attempted += atmpt
            term_earned += earn

        # Update cumulative for transfer (no GPA impact)
        self.cum_attempted += term_attempted
        self.cum_earned += term_earned
        self._advance_y(0.15 * inch)

    def draw_undergrad_record(self, semesters=None, award_degree=True,
                               confer_date="May 2023", honours=None):
        """Draw undergraduate academic record with optional degree awarded section."""
        if semesters is None:
            semesters = UNDERGRAD_SEMESTERS

        self._draw_section_marker("Beginning of Undergraduate Record")

        for sem_data in semesters:
            self.draw_semester(sem_data['term'], sem_data['courses'])

        if award_degree:
            self.draw_degrees_awarded(
                degree="Bachelor of Science",
                confer_date=confer_date,
                plan="Physics",
                honours=honours
            )

    def draw_graduate_record(self, semesters):
        """Draw graduate academic record. Resets cumulative totals for new career."""
        # Reset cumulative totals when entering graduate program
        self._reset_cumulative_totals()

        self._draw_section_marker("Beginning of Graduate Record")

        for sem_data in semesters:
            self.draw_semester(sem_data['term'], sem_data['courses'])

    def save(self):
        """Save the PDF."""
        self.c.save()
        print(f"Generated: {self.filename}")


def create_transcript(filename, student_name, student_id, grad_semesters,
                      include_undergrad=True, transfer_courses=None,
                      transfer_institution=None, undergrad_honours=None,
                      undergrad_confer_date="May 2023"):
    """Create a complete transcript PDF."""
    gen = TranscriptGenerator(filename, student_name, student_id)

    if include_undergrad:
        gen.draw_undergrad_record(
            confer_date=undergrad_confer_date,
            honours=undergrad_honours
        )

    if transfer_courses and transfer_institution:
        gen.draw_transfer_section(transfer_institution, transfer_courses)

    gen.draw_graduate_record(grad_semesters)
    gen.save()


def generate_all_test_transcripts():
    """Generate all 8 test transcript PDFs."""

    output_dir = Path("tests")

    # ==== PASSING CASES ====

    # 1. pass_standard.pdf - Full undergrad + grad record, meets all requirements
    # 18 core credits, 6 elective, 6 research = 30 total
    grad_1 = [
        {
            'term': '2023 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '543', 'title': 'Quantum Mechanics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '561', 'title': 'Classical Mechanics', 'credits': 3, 'grade': 'A-'},
            ]
        },
        {
            'term': '2024 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '544', 'title': 'Quantum Mechanics II', 'credits': 3, 'grade': 'B+'},
                {'dept': 'PHY', 'num': '521', 'title': 'Electrodynamics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '510', 'title': 'Mathematical Methods', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '522', 'title': 'Electrodynamics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '571', 'title': 'Statistical Mechanics', 'credits': 3, 'grade': 'A-'},
                {'dept': 'EAS', 'num': '520', 'title': 'Earth System Science', 'credits': 3, 'grade': 'B+'},
            ]
        },
        {
            'term': '2025 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '690', 'title': 'Graduate Thesis', 'credits': 6, 'grade': 'A'},
            ]
        },
    ]
    create_transcript(
        output_dir / "pass_standard.pdf",
        "Test Student 001", "99990001",
        grad_1, include_undergrad=True,
        undergrad_honours="Magna Cum Laude",
        undergrad_confer_date="May 2023"
    )

    # 2. pass_grad_only.pdf - Graduate record only (no undergrad section)
    # 15 core + 3 400-level + 9 elective + 3 research = 30 total
    grad_2 = [
        {
            'term': '2023 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '543', 'title': 'Quantum Mechanics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '561', 'title': 'Classical Mechanics', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '412', 'title': 'Elec & Magnt Fields II', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '544', 'title': 'Quantum Mechanics II', 'credits': 3, 'grade': 'A-'},
                {'dept': 'PHY', 'num': '521', 'title': 'Electrodynamics I', 'credits': 3, 'grade': 'B+'},
                {'dept': 'PHY', 'num': '510', 'title': 'Mathematical Methods', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '522', 'title': 'Electrodynamics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'EAS', 'num': '502', 'title': 'Earth Science', 'credits': 3, 'grade': 'A'},
                {'dept': 'EAS', 'num': '520', 'title': 'Earth System Science', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2025 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '680', 'title': 'Independent Study', 'credits': 3, 'grade': 'A'},
            ]
        },
    ]
    create_transcript(
        output_dir / "pass_grad_only.pdf",
        "Test Student 002", "99990002",
        grad_2, include_undergrad=False
    )

    # 3. pass_with_transfer.pdf - Includes transfer credits section
    # 15 core + 3 transfer core + 6 elective + 6 research = 30 total
    grad_3 = [
        {
            'term': '2023 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '543', 'title': 'Quantum Mechanics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '561', 'title': 'Classical Mechanics', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '544', 'title': 'Quantum Mechanics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '521', 'title': 'Electrodynamics I', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '522', 'title': 'Electrodynamics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '510', 'title': 'Mathematical Methods', 'credits': 3, 'grade': 'A'},
                {'dept': 'EAS', 'num': '520', 'title': 'Earth System Science', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2025 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '690', 'title': 'Graduate Thesis', 'credits': 6, 'grade': 'A'},
            ]
        },
    ]
    transfer_3 = [
        {'dept': 'PHY', 'num': '571', 'title': 'Statistical Mechanics', 'credits': 3},
    ]
    create_transcript(
        output_dir / "pass_with_transfer.pdf",
        "Test Student 003", "99990003",
        grad_3, include_undergrad=True,
        transfer_courses=transfer_3,
        transfer_institution="Riverside Community College"
    )

    # 4. pass_excess_research.pdf - More than 6 research credits (only 6 applied)
    # 18 core + 6 elective + 9 research = 33 total
    grad_4 = [
        {
            'term': '2023 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '543', 'title': 'Quantum Mechanics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '561', 'title': 'Classical Mechanics', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '544', 'title': 'Quantum Mechanics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '521', 'title': 'Electrodynamics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '510', 'title': 'Mathematical Methods', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '522', 'title': 'Electrodynamics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '571', 'title': 'Statistical Mechanics', 'credits': 3, 'grade': 'A'},
                {'dept': 'EAS', 'num': '520', 'title': 'Earth System Science', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2025 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '690', 'title': 'Graduate Thesis', 'credits': 6, 'grade': 'A'},
                {'dept': 'PHY', 'num': '680', 'title': 'Independent Study', 'credits': 3, 'grade': 'A'},
            ]
        },
    ]
    create_transcript(
        output_dir / "pass_excess_research.pdf",
        "Test Student 004", "99990004",
        grad_4, include_undergrad=True
    )

    # ==== FAILING CASES ====

    # 5. fail_insufficient_core.pdf - Less than 15 core credits
    # 12 core + 12 elective + 6 research = 30 total
    grad_5 = [
        {
            'term': '2023 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '543', 'title': 'Quantum Mechanics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '561', 'title': 'Classical Mechanics', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '544', 'title': 'Quantum Mechanics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '521', 'title': 'Electrodynamics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '510', 'title': 'Mathematical Methods', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Fall',
            'courses': [
                {'dept': 'EAS', 'num': '520', 'title': 'Earth System Science', 'credits': 3, 'grade': 'A'},
                {'dept': 'EAS', 'num': '502', 'title': 'Earth Science', 'credits': 3, 'grade': 'A'},
                {'dept': 'MTH', 'num': '573', 'title': 'Numerical Analysis', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2025 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '690', 'title': 'Graduate Thesis', 'credits': 6, 'grade': 'A'},
            ]
        },
    ]
    create_transcript(
        output_dir / "fail_insufficient_core.pdf",
        "Test Student 005", "99990005",
        grad_5, include_undergrad=True
    )

    # 6. fail_insufficient_total.pdf - Less than 30 total credits
    # 15 core + 6 elective + 6 research = 27 total
    grad_6 = [
        {
            'term': '2023 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '543', 'title': 'Quantum Mechanics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '561', 'title': 'Classical Mechanics', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '544', 'title': 'Quantum Mechanics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '521', 'title': 'Electrodynamics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '510', 'title': 'Mathematical Methods', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '522', 'title': 'Electrodynamics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'EAS', 'num': '520', 'title': 'Earth System Science', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2025 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '690', 'title': 'Graduate Thesis', 'credits': 6, 'grade': 'A'},
            ]
        },
    ]
    create_transcript(
        output_dir / "fail_insufficient_total.pdf",
        "Test Student 006", "99990006",
        grad_6, include_undergrad=True
    )

    # 7. fail_excess_400level.pdf - More than 6 400-level credits
    # 15 core + 6 elective + 9 400-level = 30 total
    grad_7 = [
        {
            'term': '2023 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '543', 'title': 'Quantum Mechanics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '561', 'title': 'Classical Mechanics', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '412', 'title': 'Elec & Magnt Fields II', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '544', 'title': 'Quantum Mechanics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '521', 'title': 'Electrodynamics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '415', 'title': 'Advanced Lab I', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '522', 'title': 'Electrodynamics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '510', 'title': 'Mathematical Methods', 'credits': 3, 'grade': 'A'},
                {'dept': 'EAS', 'num': '520', 'title': 'Earth System Science', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '416', 'title': 'Advanced Lab II', 'credits': 3, 'grade': 'A'},
            ]
        },
    ]
    create_transcript(
        output_dir / "fail_excess_400level.pdf",
        "Test Student 007", "99990007",
        grad_7, include_undergrad=True
    )

    # 8. fail_invalid_course.pdf - Contains non-whitelisted external course
    # 15 core + 6 elective + 6 research + 3 invalid = 30 total
    grad_8 = [
        {
            'term': '2023 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '543', 'title': 'Quantum Mechanics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '561', 'title': 'Classical Mechanics', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '544', 'title': 'Quantum Mechanics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '521', 'title': 'Electrodynamics I', 'credits': 3, 'grade': 'A'},
                {'dept': 'PHY', 'num': '510', 'title': 'Mathematical Methods', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2024 Fall',
            'courses': [
                {'dept': 'PHY', 'num': '522', 'title': 'Electrodynamics II', 'credits': 3, 'grade': 'A'},
                {'dept': 'EAS', 'num': '520', 'title': 'Earth System Science', 'credits': 3, 'grade': 'A'},
                {'dept': 'BIO', 'num': '520', 'title': 'Advanced Biology', 'credits': 3, 'grade': 'A'},
            ]
        },
        {
            'term': '2025 Spring',
            'courses': [
                {'dept': 'PHY', 'num': '690', 'title': 'Graduate Thesis', 'credits': 6, 'grade': 'A'},
            ]
        },
    ]
    create_transcript(
        output_dir / "fail_invalid_course.pdf",
        "Test Student 008", "99990008",
        grad_8, include_undergrad=True
    )

    print(f"\nGenerated 8 test transcripts in {output_dir}/")


if __name__ == "__main__":
    generate_all_test_transcripts()
