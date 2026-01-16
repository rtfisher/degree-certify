#!/usr/bin/env python3
"""
run_tests.py

Runs degree_certify.py on all test transcripts and verifies expected outcomes.
Returns exit code 0 if all tests pass, 1 if any fail.
"""

import subprocess
import sys
import csv
from pathlib import Path
import shutil

# Test output directory (separate from production output)
TEST_OUTPUT_DIR = Path("test_output")

# Define expected outcomes for each test case
TEST_CASES = {
    "pass_standard.pdf": {
        "expected_pass": True,
        "description": "Standard passing case with full undergrad + grad record"
    },
    "pass_grad_only.pdf": {
        "expected_pass": True,
        "description": "Graduate record only (no undergrad section)"
    },
    "pass_with_transfer.pdf": {
        "expected_pass": True,
        "description": "Includes transfer credits section"
    },
    "pass_excess_research.pdf": {
        "expected_pass": True,
        "description": "More than 6 research credits (only 6 applied)"
    },
    "fail_insufficient_core.pdf": {
        "expected_pass": False,
        "description": "Less than 15 core credits"
    },
    "fail_insufficient_total.pdf": {
        "expected_pass": False,
        "description": "Less than 30 total credits"
    },
    "fail_excess_400level.pdf": {
        "expected_pass": False,
        "description": "More than 6 400-level credits"
    },
    "fail_invalid_course.pdf": {
        "expected_pass": False,
        "description": "Contains non-whitelisted external course (BIO 520)"
    },
}


def clean_output_directory():
    """Remove any existing test output files to ensure clean test run."""
    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_certification(pdf_path):
    """Run degree_certify.py on a single PDF and return the result."""
    result = subprocess.run(
        [sys.executable, "degree_certify.py", "--output-dir", str(TEST_OUTPUT_DIR), str(pdf_path)],
        capture_output=True,
        text=True
    )
    return result


def parse_certification_result(student_id):
    """
    Parse the certification_summary.csv to find the result for a given student ID.
    Returns True if passed, False if failed, None if not found.
    """
    summary_path = TEST_OUTPUT_DIR / "certification_summary.csv"
    if not summary_path.exists():
        return None

    with open(summary_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Student ID") == student_id:
                cert_status = row.get("Certification", "")
                return cert_status == "Passed"

    return None


def run_all_tests():
    """Run all test cases and verify expected outcomes."""
    print("=" * 60)
    print("Degree Certification Test Suite")
    print("=" * 60)

    tests_dir = Path("tests")
    if not tests_dir.exists():
        print(f"ERROR: Test directory '{tests_dir}' not found.")
        print("Run 'python generate_test_transcripts.py' first.")
        return 1

    # Clean output directory for fresh run
    clean_output_directory()

    results = []
    test_num = 0

    for pdf_name, test_info in TEST_CASES.items():
        test_num += 1
        pdf_path = tests_dir / pdf_name
        expected_pass = test_info["expected_pass"]
        description = test_info["description"]

        # Extract student ID from filename (last 3 digits of test number -> 9999000X)
        student_id = f"9999000{test_num}"

        print(f"\n[Test {test_num}/8] {pdf_name}")
        print(f"  Description: {description}")
        print(f"  Expected: {'PASS' if expected_pass else 'FAIL'}")

        if not pdf_path.exists():
            print(f"  ERROR: PDF not found at {pdf_path}")
            results.append({
                "test": pdf_name,
                "status": "ERROR",
                "message": "PDF not found"
            })
            continue

        # Run certification
        run_result = run_certification(pdf_path)

        # Check for errors in execution
        if run_result.returncode != 0 and "Error" in run_result.stderr:
            print(f"  ERROR: Certification script failed")
            print(f"  stderr: {run_result.stderr[:200]}")
            results.append({
                "test": pdf_name,
                "status": "ERROR",
                "message": "Script execution failed"
            })
            continue

        # Parse result from summary CSV
        actual_pass = parse_certification_result(student_id)

        if actual_pass is None:
            # Try to determine from stdout
            if "Certification PASSED" in run_result.stdout:
                actual_pass = True
            elif "Certification FAILED" in run_result.stdout:
                actual_pass = False
            else:
                print(f"  ERROR: Could not determine certification result")
                results.append({
                    "test": pdf_name,
                    "status": "ERROR",
                    "message": "Could not parse result"
                })
                continue

        # Compare expected vs actual
        if actual_pass == expected_pass:
            print(f"  Result: {'PASS' if actual_pass else 'FAIL'} (as expected)")
            print(f"  Status: OK")
            results.append({
                "test": pdf_name,
                "status": "OK",
                "message": f"Correctly {'passed' if expected_pass else 'failed'}"
            })
        else:
            print(f"  Result: {'PASS' if actual_pass else 'FAIL'}")
            print(f"  Status: MISMATCH - expected {'PASS' if expected_pass else 'FAIL'}")
            results.append({
                "test": pdf_name,
                "status": "MISMATCH",
                "message": f"Expected {'PASS' if expected_pass else 'FAIL'}, got {'PASS' if actual_pass else 'FAIL'}"
            })

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    ok_count = sum(1 for r in results if r["status"] == "OK")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    mismatch_count = sum(1 for r in results if r["status"] == "MISMATCH")

    print(f"  Passed: {ok_count}/8")
    print(f"  Errors: {error_count}")
    print(f"  Mismatches: {mismatch_count}")

    if error_count > 0 or mismatch_count > 0:
        print("\nFailed tests:")
        for r in results:
            if r["status"] != "OK":
                print(f"  - {r['test']}: {r['status']} - {r['message']}")
        print("\nTEST SUITE FAILED")
        return 1
    else:
        print("\nALL TESTS PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
