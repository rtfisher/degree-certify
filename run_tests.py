#!/usr/bin/env python3
"""
run_tests.py

Runs degree_certify.py on all test transcripts and verifies expected outcomes.
Returns exit code 0 if all tests pass, 1 if any fail.
"""

import subprocess
import sys
import csv
import json
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
    "pass_undergrad_transfer_ignored.pdf": {
        "expected_pass": True,
        "description": "Undergrad transfer credits ignored, only grad transfer credits counted"
    },
    "pass_eas_phd.pdf": {
        "expected_pass": True,
        "description": "EAS PhD student earning M.S. Physics en route (auto-detected from Plan line, rulebook-upgraded core topics)",
        # Runs with NO --eas-phd flag: EAS mode must be auto-detected from the
        # transcript's graduate Plan line. A seeded rulebook upgrades two PHY 595
        # special topics to Core (the rest default to Elective; external PhD courses
        # default to Exclude).
        "rulebook": {
            "special_topics": {
                "PHY 595 | Topological Phases": "Core",
                "PHY 595 | Holographic Duality": "Core",
            },
            "courses": {},
        },
        # Confirm the rulebook-driven core upgrade and double-count accounting, not
        # just the pass/fail outcome. Assert on the stable summary-dict repr rather
        # than the formatted table (whose column widths shift with the glyphs).
        "stdout_contains": [
            # EAS mode came from the transcript, not a flag.
            "EAS PhD track auto-detected from transcript",
            "'Core Credits': 15",
            "'Total Credits': 33",
            "'Double-Counted Credits': 24",
            # Only 30 - 24 = 6 credits (2 courses) need reserving, not 33 - 24 = 9.
            "'Single-Counted Credits': 6",
        ],
    },
}


def clean_output_directory():
    """Remove any existing test output files to ensure clean test run."""
    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_certification(pdf_path, extra_args=None):
    """Run degree_certify.py on a single PDF and return the result.

    extra_args: optional list of additional CLI flags (e.g. ["--eas-phd", ...]).
    Runs with stdin closed so any unexpected interactive prompt fails loudly
    rather than hanging.
    """
    cmd = [sys.executable, "degree_certify.py", "--output-dir", str(TEST_OUTPUT_DIR)]
    if extra_args:
        cmd += extra_args
    cmd.append(str(pdf_path))
    result = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
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


def run_resume_test():
    """Round-trip: certify the EAS fixture, then re-run with an empty rulebook and
    confirm it resumes from the prior CSV (restoring classifications + single-count)."""
    results = []

    def check(name, cond, msg=""):
        results.append({"test": f"resume:{name}",
                        "status": "OK" if cond else "MISMATCH",
                        "message": "" if cond else msg})

    pdf = Path("tests") / "pass_eas_phd.pdf"
    if not pdf.exists():
        return [{"test": "resume:setup", "status": "SKIP", "message": "EAS fixture missing"}]

    outdir = TEST_OUTPUT_DIR / "resume"
    seed = TEST_OUTPUT_DIR / "resume_seed.json"
    empty = TEST_OUTPUT_DIR / "resume_empty.json"
    with open(seed, "w") as f:
        json.dump({"special_topics": {"PHY 595 | Topological Phases": "Core",
                                      "PHY 595 | Holographic Duality": "Core"}, "courses": {}}, f)
    with open(empty, "w") as f:
        json.dump({}, f)

    def run(rulebook, sc):
        return subprocess.run(
            [sys.executable, "degree_certify.py", "--output-dir", str(outdir),
             "--rulebook", str(rulebook), "--single-count-file", str(sc), str(pdf)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True)

    first = run(seed, TEST_OUTPUT_DIR / "resume_sc1.json")
    check("first_pass", "Certification PASSED" in first.stdout, first.stdout[-300:])
    # Re-run with an EMPTY rulebook: without resume this fails (topics -> Elective, core 9);
    # resuming from the prior CSV must restore Core classifications + single-count.
    second = run(empty, TEST_OUTPUT_DIR / "resume_sc2.json")
    check("resume_detected", "Resuming from existing certification" in second.stdout, second.stdout[-300:])
    check("resume_pass", "Certification PASSED" in second.stdout, second.stdout[-300:])
    check("resume_core_restored", "'Core Credits': 15" in second.stdout, second.stdout[-300:])
    check("resume_single_count_restored", "'Single-Counted Credits': 6" in second.stdout, second.stdout[-300:])
    return results


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

        print(f"\n[Test {test_num}/{len(TEST_CASES)}] {pdf_name}")
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

        # Build per-case extra args. Cases needing a seeded classification rulebook
        # and/or single-count store get isolated temp files so the run is fully
        # deterministic and never touches a real (gitignored) rulebook.
        extra_args = list(test_info.get("extra_args", []))
        if "rulebook" in test_info or extra_args:
            rulebook_path = TEST_OUTPUT_DIR / f"{pdf_path.stem}_rulebook.json"
            single_count_path = TEST_OUTPUT_DIR / f"{pdf_path.stem}_single_count.json"
            with open(rulebook_path, "w") as f:
                json.dump(test_info.get("rulebook", {"special_topics": {}, "courses": {}}), f)
            extra_args += ["--rulebook", str(rulebook_path),
                           "--single-count-file", str(single_count_path)]

        # Run certification
        run_result = run_certification(pdf_path, extra_args)

        # Optional content checks (e.g. credit breakdown for the EAS PhD path).
        missing = [s for s in test_info.get("stdout_contains", []) if s not in run_result.stdout]
        if missing:
            print(f"  ERROR: expected output not found: {missing}")
            results.append({
                "test": pdf_name,
                "status": "MISMATCH",
                "message": f"Missing expected output: {missing}"
            })
            continue

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

    # Interactive TUI logic tests (headless, via injected input). These run in CI
    # because rich is installed from requirements.txt; they skip if rich is absent.
    print("\n" + "-" * 60)
    print("TUI logic tests (certify_tui.py)")
    print("-" * 60)
    try:
        from test_tui import run_tui_tests
        tui_results = run_tui_tests()
    except Exception as e:
        tui_results = [{"test": "tui:harness", "status": "ERROR", "message": str(e)}]
    for r in tui_results:
        print(f"  [{r['status']}] {r['test']} {r['message']}")
    results.extend(tui_results)

    # Resume-from-CSV round trip
    print("\n" + "-" * 60)
    print("Resume-from-CSV test")
    print("-" * 60)
    resume_results = run_resume_test()
    for r in resume_results:
        print(f"  [{r['status']}] {r['test']} {r['message']}")
    results.extend(resume_results)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    ok_count = sum(1 for r in results if r["status"] == "OK")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    mismatch_count = sum(1 for r in results if r["status"] == "MISMATCH")
    skip_count = sum(1 for r in results if r["status"] == "SKIP")

    print(f"  Passed: {ok_count}/{ok_count + error_count + mismatch_count}")
    print(f"  Errors: {error_count}")
    print(f"  Mismatches: {mismatch_count}")
    if skip_count:
        print(f"  Skipped: {skip_count}")

    if error_count > 0 or mismatch_count > 0:
        print("\nFailed tests:")
        for r in results:
            if r["status"] in ("ERROR", "MISMATCH"):
                print(f"  - {r['test']}: {r['status']} - {r['message']}")
        print("\nTEST SUITE FAILED")
        return 1
    else:
        print("\nALL TESTS PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
