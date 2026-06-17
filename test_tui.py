#!/usr/bin/env python3
"""
test_tui.py

Headless tests for the cursor-driven TUI (certify_tui.py). The TUI reads keystrokes
through an injectable `getch` and renders to an in-memory rich Console, so its
navigation/action logic is exercisable without a real terminal. These run as part of
`run_tests.py` (and therefore in CI, where `rich` is installed from requirements.txt).

Returns a list of result dicts shaped like run_tests.py's PDF cases:
{"test", "status" in {OK, MISMATCH, SKIP}, "message"}.
"""


def _synthetic_df():
    import pandas as pd
    rows = [
        # index, code, title, topic  (all 3 credits, grade A)
        ("PHY 543", "Statistical Mechanics", ""),                       # 0  PHY -> Core
        ("PHY 561", "Classical Mechanics", ""),                         # 1  PHY -> Core
        ("PHY 612", "Electrodynamics", ""),                             # 2  PHY -> Core
        ("PHY 595", "Selected Topics", "Quantum Field Theory"),         # 3  special topic
        ("PHY 595", "Selected Topics", "General Relativity"),           # 4  special topic
        ("PHY 595", "Selected Topics", "Cosmology"),                    # 5  special topic
        ("EAS 520", "Earth System Science", ""),                        # 6  whitelist -> Elective
        ("MTH 573", "Numerical Analysis", ""),                          # 7  whitelist -> Elective
        ("GEO 610", "Geodynamics", ""),                                 # 8  external
        ("PHY 690", "Graduate Thesis", ""),                             # 9  research
    ]
    return pd.DataFrame([
        {"Semester": "F23", "Course Code": c, "Title": t, "Credits Earned": 3.0,
         "Grade": "A", "Topic": tp}
        for c, t, tp in rows
    ])


def _keyseq(actions):
    """Build a getch() that navigates the cursor (from 0) and presses keys.

    actions: list of (target_index, key) — moves with UP/DOWN to target_index then
    sends `key`. A trailing 's' (save) is appended.
    """
    seq, cur = [], 0
    for idx, key in actions:
        while cur < idx:
            seq.append("DOWN"); cur += 1
        while cur > idx:
            seq.append("UP"); cur -= 1
        seq.append(key)
    seq.append("s")
    it = iter(seq)
    return lambda: next(it)


def run_tui_tests():
    results = []

    def check(name, cond, msg=""):
        results.append({"test": f"tui:{name}",
                        "status": "OK" if cond else "MISMATCH",
                        "message": "" if cond else (msg or "assertion failed")})

    try:
        import io
        from rich.console import Console
        import degree_certify as dc
        import certify_tui as tui
    except ImportError as e:
        results.append({"test": "tui:import", "status": "SKIP",
                        "message": f"rich/deps unavailable ({e})"})
        return results

    def console():
        return Console(file=io.StringIO(), width=110)

    df = _synthetic_df()

    # --- classify_rows: every course editable; defaults applied (EAS PhD) ---
    rows = dc.classify_rows(df, True, {"special_topics": {}, "courses": {}})
    by = {(r["code"], r["topic"]): r for r in rows}
    check("all_editable", all(r["editable"] for r in rows))
    phy = by[("PHY 543", "")]
    check("phy_core_default", phy["classification"] == "Core" and phy["kind"] == "phy_core"
          and phy["section"] == "courses" and phy["key"] == "PHY 543", str(phy))
    check("research_default", by[("PHY 690", "")]["classification"] == "Research"
          and by[("PHY 690", "")]["kind"] == "research")
    check("whitelist_default", by[("EAS 520", "")]["classification"] == "Elective"
          and by[("EAS 520", "")]["kind"] == "whitelist")
    st = by[("PHY 595", "Quantum Field Theory")]
    check("special_topic_default", st["section"] == "special_topics"
          and st["key"] == "PHY 595 | Quantum Field Theory"
          and st["classification"] == "Elective" and st["kind"] == "special_topic", str(st))
    ext = by[("GEO 610", "")]
    check("external_default_exclude_eas", ext["section"] == "courses"
          and ext["classification"] == "Exclude" and ext["kind"] == "external", str(ext))
    rows_std = dc.classify_rows(df, False, {"special_topics": {}, "courses": {}})
    check("external_default_invalid_standard",
          next(r for r in rows_std if r["code"] == "GEO 610")["classification"] == "Invalid")
    rows_ovr = dc.classify_rows(df, True, {"special_topics": {}, "courses": {"PHY 543": "Exclude"}})
    check("override_wins", next(r for r in rows_ovr if r["code"] == "PHY 543")["classification"] == "Exclude")

    # --- edit_classifications via keystrokes: cursor to rows 3 & 4, press 'c', save ---
    cm = {"special_topics": {}, "courses": {}}
    changed = tui.edit_classifications(df, cm, True, dc.classify_rows, dc.count_credits,
                                       getch=_keyseq([(3, "c"), (4, "c")]), console=console())
    check("edit_returns_changed", changed is True)
    check("edit_persists_core",
          cm["special_topics"].get("PHY 595 | Quantum Field Theory") == "Core"
          and cm["special_topics"].get("PHY 595 | General Relativity") == "Core", str(cm))

    # cycle with Right arrow on a special topic (Elective -> Research)
    cm_cyc = {"special_topics": {}, "courses": {}}
    tui.edit_classifications(df, cm_cyc, True, dc.classify_rows, dc.count_credits,
                             getch=_keyseq([(3, "RIGHT")]), console=console())
    check("cycle_right", cm_cyc["special_topics"].get("PHY 595 | Quantum Field Theory") == "Research", str(cm_cyc))

    # any row editable, including a PHY-core course (row 0) -> writes courses["PHY 543"]
    cm2 = {"special_topics": {}, "courses": {}}
    tui.edit_classifications(df, cm2, True, dc.classify_rows, dc.count_credits,
                             getch=_keyseq([(0, "x")]), console=console())
    check("edit_phy_override", cm2["courses"].get("PHY 543") == "Exclude", str(cm2))

    # quit ('q') discards changes
    cm3 = {"special_topics": {}, "courses": {}}
    qseq = iter(["DOWN", "DOWN", "DOWN", "c", "q"])
    ch3 = tui.edit_classifications(df, cm3, True, dc.classify_rows, dc.count_credits,
                                   getch=lambda: next(qseq), console=console())
    check("edit_quit_discards", ch3 is False and cm3 == {"special_topics": {}, "courses": {}}, str(cm3))

    # --- select_single_counted ---
    applied = [{"id": f"id{i}", "code": f"PHY {600 + i}", "title": f"Course {i}",
                "credits": 3.0, "classification": "Core" if i < 5 else "Elective"}
               for i in range(11)]
    required = 6.0

    store = {}
    sel = tui.select_single_counted(applied, required, store, "S1", dc.minimal_single_count,
                                    getch=lambda: "s", console=console())
    check("single_count_minimal", len(sel) == 2 and sum(c["credits"] for c in sel) == 6.0, str(sel))
    check("single_count_prefers_noncore", all(c["classification"] != "Core" for c in sel), str(sel))
    check("single_count_persisted", store.get("S1") == [c["id"] for c in sel], str(store))

    # toggle: minimal pre-selects id5,id6; move to 5 -> space (off), to 7 -> space (on), save
    store2 = {}
    tseq = iter(["DOWN"] * 5 + [" "] + ["DOWN"] * 2 + [" ", "s"])
    sel2 = tui.select_single_counted(applied, required, store2, "S2", dc.minimal_single_count,
                                     getch=lambda: next(tseq), console=console())
    ids2 = {c["id"] for c in sel2}
    check("single_count_toggle", ids2 == {"id6", "id7"} and sum(c["credits"] for c in sel2) >= required, str(sel2))

    return results


if __name__ == "__main__":
    import sys
    res = run_tui_tests()
    for r in res:
        print(f"  [{r['status']}] {r['test']} {r['message']}")
    bad = [r for r in res if r["status"] not in ("OK", "SKIP")]
    print(f"\n{sum(1 for r in res if r['status']=='OK')} passed, {len(bad)} failed, "
          f"{sum(1 for r in res if r['status']=='SKIP')} skipped")
    sys.exit(1 if bad else 0)
