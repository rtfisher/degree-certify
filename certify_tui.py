#!/usr/bin/env python3
"""
certify_tui.py

Cursor-driven, rich-formatted terminal UI for degree_certify.py. Two screens:

  edit_classifications(...)   - one table of every parsed course. Move the cursor with
                                Up/Down and set the highlighted course's classification
                                with a single keystroke (c/e/r/x), or cycle it with
                                Left/Right. Live credit totals and a PASS/FAIL banner
                                update after every change.
  select_single_counted(...)  - for EAS PhD students, move the cursor and toggle which
                                applied courses are reserved as M.S.-only (Space).

Keys are read one at a time in raw mode (arrow keys decoded from their escape
sequences) by a small stdlib termios reader. The reader is injectable as `getch` so the
navigation/action logic is unit-testable without a real terminal (see test_tui.py);
`rich` rendering degrades gracefully on a non-TTY. This module is imported lazily by
degree_certify.py only under --interactive, so headless / CI runs never load it.
"""

import copy

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


CLASS_ORDER = ["Core", "Elective", "Research", "Exclude"]
CLASS_KEYS = {"c": "Core", "e": "Elective", "r": "Research", "x": "Exclude"}
CLASS_STYLES = {
    "Core": "bold green", "Elective": "cyan", "Research": "magenta",
    "Exclude": "dim", "Invalid": "bold red",
}


def make_getch():
    """Return a getch() reading one keypress in raw mode (Up/Down/Left/Right decoded)."""
    import sys
    import os
    import termios
    import tty
    import select

    def getch():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = os.read(fd, 1).decode(errors="ignore")
            if ch == "\x1b":  # escape: maybe an arrow-key sequence
                if select.select([fd], [], [], 0.05)[0]:
                    ch += os.read(fd, 2).decode(errors="ignore")
                    return {"\x1b[A": "UP", "\x1b[B": "DOWN",
                            "\x1b[C": "RIGHT", "\x1b[D": "LEFT"}.get(ch, "ESC")
                return "ESC"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    return getch


def _class_text(cls):
    return Text(cls, style=CLASS_STYLES.get(cls, ""))


def _passes(counts):
    return (counts["core"] >= 15 and counts["total"] >= 30
            and counts["four_xx"] <= 6 and not counts["has_invalid"])


def _totals_panel(counts):
    def stat(label, value, ok, cap):
        style = "green" if ok else "red"
        return f"[bold]{label}:[/bold] [{style}]{int(value)}[/{style}]/{cap}"

    line = "   ".join([
        stat("Core", counts["core"], counts["core"] >= 15, 15),
        stat("Total", counts["total"], counts["total"] >= 30, 30),
        f"[bold]Research applied:[/bold] {int(min(6, counts['research']))}/6",
        stat("400-level", counts["four_xx"], counts["four_xx"] <= 6, 6),
    ])
    verdict = "[bold green]✓ PASSES[/bold green]" if _passes(counts) else "[bold red]✗ FAILS[/bold red]"
    return Panel(f"{line}\n{verdict}", title="M.S. Physics requirements", expand=False)


def _render_classification(console, rows, counts, cursor, eas_phd):
    if console.is_terminal:
        console.clear()
    table = Table(title="Course Classification", expand=False, header_style="bold")
    table.add_column(" ", justify="center")
    table.add_column("Course")
    table.add_column("Title")
    table.add_column("Cr", justify="right")
    table.add_column("Grade")
    table.add_column("Class")
    table.add_column("")
    for i, v in enumerate(rows):
        if v["cached"]:
            flag = Text("✎ saved", style="cyan")
        elif v["kind"] in ("special_topic", "external"):
            flag = Text("● review", style="bold yellow")
        else:
            flag = Text("default", style="dim")
        title = v["title"] if len(v["title"]) <= 44 else v["title"][:43] + "…"
        marker = "▶" if i == cursor else " "
        table.add_row(marker, v["code"], title, f"{v['credits']:.0f}", v["grade"],
                      _class_text(v["classification"]), flag,
                      style="reverse" if i == cursor else None)
    console.print(table)
    console.print(_totals_panel(counts))
    review_n = sum(1 for v in rows if not v["cached"] and v["kind"] in ("special_topic", "external"))
    track = "EAS PhD (M.S. en route)" if eas_phd else "M.S. Physics"
    hint = f"Track: [bold]{track}[/bold]."
    if review_n:
        hint += f"  {review_n} course(s) marked [bold yellow]● review[/bold yellow]."
    console.print(hint)
    console.print(Text("↑/↓ move   c/e/r/x set   ←/→ cycle   s save   q quit", style="dim"))


def edit_classifications(df, class_map, eas_phd, classify_rows, count_credits,
                         getch=None, console=None):
    """Cursor-driven classification editor. Mutates `class_map` with the user's choices.

    `classify_rows`/`count_credits` are passed in from degree_certify (avoids a circular
    import) and recompute after every keystroke. Returns True if the rulebook changed.
    """
    import sys
    console = console or Console()
    if getch is None:
        if not sys.stdin.isatty():
            print("Interactive editing needs a terminal; using saved/default classifications.")
            return False
        getch = make_getch()

    original = copy.deepcopy({"special_topics": class_map["special_topics"],
                              "courses": class_map["courses"]})
    cursor = 0

    def set_class(row, cls):
        class_map[row["section"]][row["key"]] = cls

    while True:
        rows = classify_rows(df, eas_phd, class_map)
        if not rows:
            break
        cursor = max(0, min(cursor, len(rows) - 1))
        counts = count_credits(rows)
        _render_classification(console, rows, counts, cursor, eas_phd)

        try:
            key = getch()
        except (EOFError, KeyboardInterrupt):
            break
        if key is None:
            break

        if key in ("UP", "k"):
            cursor = (cursor - 1) % len(rows)
        elif key in ("DOWN", "j"):
            cursor = (cursor + 1) % len(rows)
        elif key and key.lower() in CLASS_KEYS:
            set_class(rows[cursor], CLASS_KEYS[key.lower()])
        elif key in ("LEFT", "RIGHT"):
            cur = rows[cursor]["classification"]
            i = CLASS_ORDER.index(cur) if cur in CLASS_ORDER else 0
            set_class(rows[cursor], CLASS_ORDER[(i + (1 if key == "RIGHT" else -1)) % len(CLASS_ORDER)])
        elif key in ("s", "S", "\r", "\n"):
            break
        elif key in ("q", "Q", "ESC", "\x03"):
            class_map["special_topics"].clear()
            class_map["special_topics"].update(original["special_topics"])
            class_map["courses"].clear()
            class_map["courses"].update(original["courses"])
            return False

    return ({"special_topics": class_map["special_topics"],
             "courses": class_map["courses"]} != original)


def _render_single_count(console, applied, selected_ids, cursor, required):
    if console.is_terminal:
        console.clear()
    table = Table(title="Single-Counted Courses (reserved for the M.S. only)",
                  expand=False, header_style="bold")
    table.add_column(" ", justify="center")
    table.add_column("Course")
    table.add_column("Title")
    table.add_column("Cr", justify="right")
    table.add_column("Class")
    table.add_column("Reserved")
    for i, c in enumerate(applied):
        reserved = c["id"] in selected_ids
        mark = Text("✓ M.S.-only", style="bold green") if reserved else Text("", style="dim")
        title = c["title"] if len(c["title"]) <= 44 else c["title"][:43] + "…"
        marker = "▶" if i == cursor else " "
        table.add_row(marker, c["code"], title, f"{c['credits']:.0f}",
                      _class_text(c["classification"]), mark,
                      style="reverse" if i == cursor else None)
    console.print(table)
    reserved_cr = sum(c["credits"] for c in applied if c["id"] in selected_ids)
    ok = reserved_cr >= required
    style = "green" if ok else "red"
    console.print(Panel(
        f"Reserved [{style}]{int(reserved_cr)}[/{style}] of [bold]{int(required)}[/bold] "
        f"required single-counted credits.\n"
        f"At least {int(required)} cr must be M.S.-only; reserve as FEW courses as "
        f"possible — credits the PhD will not need.",
        title="EAS PhD double-count rule", expand=False))
    console.print(Text("↑/↓ move   space toggle   a auto (fewest)   s save   q quit", style="dim"))


def select_single_counted(applied, required, store, student_id, minimal_single_count,
                          getch=None, console=None):
    """Cursor-driven toggle of which applied courses are single-counted (M.S.-only).

    Pre-seeds the fewest courses (or a still-valid saved selection), lets the certifier
    adjust, and writes the chosen ids to `store[student_id]`. Returns the selected
    applied-course dicts.
    """
    import sys
    console = console or Console()
    if getch is None:
        if not sys.stdin.isatty():
            selected = minimal_single_count(applied, required)
            store[student_id] = [c["id"] for c in selected]
            return selected
        getch = make_getch()

    saved = store.get(student_id)
    if saved and sum(c["credits"] for c in applied if c["id"] in saved) >= required:
        selected_ids = [c["id"] for c in applied if c["id"] in saved]
    else:
        selected_ids = [c["id"] for c in minimal_single_count(applied, required)]
    selected_ids = list(dict.fromkeys(selected_ids))
    cursor = 0

    while True:
        cursor = max(0, min(cursor, len(applied) - 1))
        _render_single_count(console, applied, set(selected_ids), cursor, required)
        try:
            key = getch()
        except (EOFError, KeyboardInterrupt):
            break
        if key is None:
            break

        if key in ("UP", "k"):
            cursor = (cursor - 1) % len(applied)
        elif key in ("DOWN", "j"):
            cursor = (cursor + 1) % len(applied)
        elif key in (" ", "\r", "\n"):
            cid = applied[cursor]["id"]
            if cid in selected_ids:
                selected_ids.remove(cid)
            else:
                selected_ids.append(cid)
        elif key in ("a", "A"):
            selected_ids = [c["id"] for c in minimal_single_count(applied, required)]
        elif key in ("s", "S"):
            if sum(c["credits"] for c in applied if c["id"] in set(selected_ids)) >= required:
                break
        elif key in ("q", "Q", "ESC", "\x03"):
            break

    selected_set = set(selected_ids)
    if sum(c["credits"] for c in applied if c["id"] in selected_set) < required:
        selected_ids = [c["id"] for c in minimal_single_count(applied, required)]
        selected_set = set(selected_ids)
    selected = [c for c in applied if c["id"] in selected_set]
    store[student_id] = [c["id"] for c in selected]
    return selected
