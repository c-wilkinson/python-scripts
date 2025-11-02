#!/usr/bin/env python3
"""
Scramble Pad Trainer

Tiny desktop app to practise entering a fixed 4-digit PIN on a scrambled keypad.
Keyboard input is by *position* (like a numpad / phone keypad), not by the digit
printed on the key. Clicks work too. Tracks speed/accuracy to a CSV for bragging
rights or self-loathing, depending on the day.
"""

from __future__ import annotations

import configparser
import csv
import random
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import messagebox

APP_TITLE = "Scramble Pad Trainer"
CONF_FILE = Path(__file__).with_name("scramblepad.conf")
STATS_FILE = Path(__file__).with_name("scramblepad_stats.csv")

# Module-level maps: fixed positions for keyboard -> grid coordinates.
NUMPAD_POS = {
    "KP_7": (0, 0),
    "KP_8": (0, 1),
    "KP_9": (0, 2),
    "KP_4": (1, 0),
    "KP_5": (1, 1),
    "KP_6": (1, 2),
    "KP_1": (2, 0),
    "KP_2": (2, 1),
    "KP_3": (2, 2),
    "KP_0": (3, 1),
}

KEYPOS_POS = {
    "1": (2, 0),
    "2": (2, 1),
    "3": (2, 2),
    "4": (1, 0),
    "5": (1, 1),
    "6": (1, 2),
    "7": (0, 0),
    "8": (0, 1),
    "9": (0, 2),
    "0": (3, 1),
}


@dataclass
class RoundResult:
    """
    Result for a single PIN attempt.
    One round = one attempt to enter the PIN
    """

    duration_ms: int
    correct: int
    total: int

    @property
    def accuracy_pct(self) -> float:
        """Percentage of digits correct in position."""
        return 100.0 * self.correct / max(1, self.total)


def load_or_create_pin() -> str:
    """
    Grab a 4-digit PIN from scramblepad.conf. If missing/invalid, create one.
    I’m not storing state anywhere clever—local file is fine for this.
    """
    cfg = configparser.ConfigParser()

    if CONF_FILE.exists():
        cfg.read(CONF_FILE)
        pin = cfg.get("settings", "pin", fallback="")
        if pin.isdigit() and len(pin) == 4:
            return pin

    # Fall back to a new random PIN and persist it for next time.
    pin = f"{random.randint(0, 9999):04d}"
    cfg["settings"] = {"pin": pin}

    with open(CONF_FILE, "w", encoding="utf-8") as f:
        cfg.write(f)

    return pin


def append_stats(result: RoundResult) -> None:
    """
    Append the latest result to a CSV with a header if it's the first run.
    Keeping it simple: timestamp, duration, accuracy, correct/total.
    """
    header = ["timestamp", "duration_ms", "accuracy_pct", "correct", "total"]
    row = [
        datetime.now().isoformat(timespec="seconds"),
        result.duration_ms,
        f"{result.accuracy_pct:.2f}",
        result.correct,
        result.total,
    ]

    new_file = not STATS_FILE.exists()
    with open(STATS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(header)
        writer.writerow(row)


def read_stats_last_n(n: int = 50) -> list[dict]:
    """
    Read the last N rows from the CSV. If the file doesn’t exist yet, shrug.
    Any malformed rows are quietly skipped because life is short.
    """
    if not STATS_FILE.exists():
        return []

    rows: list[dict] = []
    with open(STATS_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rows.append(
                    {
                        "timestamp": row["timestamp"],
                        "duration_ms": int(row["duration_ms"]),
                        "accuracy_pct": float(row["accuracy_pct"]),
                        "correct": int(row["correct"]),
                        "total": int(row["total"]),
                    }
                )
            except (KeyError, ValueError):
                # If someone hand-edited the CSV, we don't want to crash here.
                continue

    return rows[-n:]


class ScramblePad(tk.Tk):
    """
    Tkinter app:
    - 3x3 grid plus a bottom-middle '0' (i.e., phone/numpad layout)
    - Digits are shuffled each round, but *positions* stay fixed
    - Keyboard entries use positions (7/8/9 is the top row, etc.)
    """

    def __init__(self, pin: str) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.configure(padx=14, pady=14, bg="#1a1a1a")
        self.pin = pin
        self.entry: list[str] = []
        self.inputs: list[str] = []
        self.started_at: float | None = None
        self.coord_to_digit: dict[tuple[int, int], str] = {}
        self.digit_to_coord: dict[str, tuple[int, int]] = {}
        self.ui: SimpleNamespace = SimpleNamespace(
            display=None, grid_frame=None, entry_label=None, cells=[]
        )
        self._build_ui()
        self._shuffle_digits()
        self.bind_all("<Key>", self._on_key)

    def _build_ui(self) -> None:
        """Create widgets and layout."""
        outer = tk.Frame(self, bg="#1a1a1a")
        outer.grid(row=0, column=0)

        self.ui.display = tk.Label(
            outer,
            text="Use keyboard as POSITIONS (like numpad) or click cells.",
            fg="#e6e6e6",
            bg="#1a1a1a",
            font=("Segoe UI", 12),
        )
        self.ui.display.grid(row=0, column=0, columnspan=3, pady=(0, 10))

        self.ui.grid_frame = tk.Frame(outer, bg="#0f0f0f", bd=4)
        self.ui.grid_frame.grid(row=1, column=0)

        self.ui.cells = []
        for r in range(4):
            for c in range(3):
                btn = tk.Button(
                    self.ui.grid_frame,
                    text="",
                    width=4,
                    height=2,
                    font=("Consolas", 20, "bold"),
                    fg="#ff3d3d",
                    bg="#101010",
                    activebackground="#262626",
                    relief=tk.RIDGE,
                    bd=2,
                    command=lambda br=r, bc=c: self._on_click_cell(br, bc),
                )
                btn.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                self.ui.cells.append(btn)

        controls = tk.Frame(outer, bg="#1a1a1a")
        controls.grid(row=2, column=0, pady=(10, 0))
        tk.Button(controls, text="START", width=10, command=self.start_round).grid(
            row=0, column=0, padx=4
        )
        tk.Button(controls, text="CLEAR", width=10, command=self.clear_entry).grid(
            row=0, column=1, padx=4
        )
        tk.Button(controls, text="STATS (S)", width=10, command=self.show_stats).grid(
            row=0, column=2, padx=4
        )

        self.ui.entry_label = tk.Label(
            outer, text="", fg="#cfcfcf", bg="#1a1a1a", font=("Consolas", 14)
        )
        self.ui.entry_label.grid(row=3, column=0, pady=(10, 0))

    def _shuffle_digits(self) -> None:
        """
        Randomise which digit is printed in each cell, but keep coordinates stable.
        The trick is that you *enter by position*, so your muscle memory is tested.
        """
        digits = [str(d) for d in range(10)]
        random.shuffle(digits)

        positions = [(r, c) for r in range(3) for c in range(3)] + [(3, 1)]
        self.coord_to_digit.clear()
        self.digit_to_coord.clear()

        for idx, (r, c) in enumerate(positions):
            digit = digits[idx]
            btn_index = r * 3 + c
            self.ui.cells[btn_index].config(text=digit)
            self.coord_to_digit[(r, c)] = digit
            self.digit_to_coord[digit] = (r, c)

    def start_round(self) -> None:
        """Reset state and reshuffle the board."""
        self.entry.clear()
        self.inputs.clear()
        self.started_at = None
        self.ui.entry_label.config(text="")
        self.ui.display.config(text="Follow the grid layout visually.")
        self._shuffle_digits()

    def clear_entry(self) -> None:
        """
        Panic button: wipe current attempt without reshuffling.
        """
        self.entry.clear()
        self.inputs.clear()
        self.started_at = None
        self.ui.entry_label.config(text="")

    def _on_click_cell(self, row: int, col: int) -> None:
        """
        Mouse click handler: accept the digit currently printed at r,c.
        We still store the *digit* we saw, because that’s what we’ll compare to the PIN.
        """
        digit = self.coord_to_digit.get((row, col))
        if digit:
            self._accept_digit(digit)
            self.inputs.append(f"btn({row},{col})")

    def _on_key(self, event: tk.Event) -> None:  # type: ignore[override]
        """
        Keyboard handler. Important bits:
        - Enter/KP_Enter finishes early if you’ve decided you’re done lying to yourself.
        - Backspace clears.
        - Number keys and numpad keys map to *positions*, not digits.
        - 'S' pops stats because I will absolutely forget the button exists.
        """
        key = event.keysym

        if key in {"Return", "KP_Enter"}:
            self._finish_if_ready(force=True)
            return

        if key == "BackSpace":
            self.clear_entry()
            return

        if key in NUMPAD_POS:
            coord = NUMPAD_POS[key]
            digit = self.coord_to_digit.get(coord)
            if digit:
                self._accept_digit(digit)
                self.inputs.append(key)
            return

        if key in KEYPOS_POS:
            coord = KEYPOS_POS[key]
            digit = self.coord_to_digit.get(coord)
            if digit:
                self._accept_digit(digit)
                self.inputs.append(key)
            return

        if key.lower() == "s":
            self.show_stats()

    def _accept_digit(self, digit: str) -> None:
        """Accept one digit and mask the entry. Start timer on first input."""
        if self.started_at is None:
            self.started_at = time.perf_counter()

        if len(self.entry) >= len(self.pin):
            return

        self.entry.append(digit)
        self.ui.entry_label.config(text="•" * len(self.entry))
        self._finish_if_ready(force=False)

    def _finish_if_ready(self, force: bool) -> None:
        """
        Lightweight stats: all-time averages, last-10 trend, and latest result.
        This is not Power BI; it’s a nudge to see if you’re actually improving.
        """
        if not self.entry:
            return

        if not force and len(self.entry) < len(self.pin):
            return

        start = self.started_at or time.perf_counter()
        duration_ms = int(1000 * (time.perf_counter() - start))

        entered = (self.entry + [""] * len(self.pin))[: len(self.pin)]
        correct = sum(1 for i, ch in enumerate(entered) if ch == self.pin[i])

        result = RoundResult(duration_ms, correct, len(self.pin))
        append_stats(result)
        self._show_result(result)
        self.start_round()

    def _show_result(self, result: RoundResult) -> None:
        """Show the verdict and timing/accuracy details."""
        interpreted = "".join(self.entry[: len(self.pin)])
        verdict = "Correct" if interpreted == self.pin else "Incorrect"

        message = (
            f"{verdict}\n\n"
            f"PIN: {self.pin}\n"
            f"Interpreted: {interpreted}\n\n"
            f"Time: {result.duration_ms} ms\n"
            f"Accuracy: {result.accuracy_pct:.0f}% "
            f"({result.correct}/{result.total})"
        )
        messagebox.showinfo("Result", message, parent=self)

    def show_stats(self) -> None:
        """Show all-time and last-10 averages, plus the latest result."""
        rows = read_stats_last_n(100)

        if not rows:
            messagebox.showinfo("Stats", "No stats yet.", parent=self)
            return

        last10 = rows[-10:]
        avg_time = statistics.fmean(r["duration_ms"] for r in rows)
        avg_acc = statistics.fmean(r["accuracy_pct"] for r in rows)
        last_time = statistics.fmean(r["duration_ms"] for r in last10)
        last_acc = statistics.fmean(r["accuracy_pct"] for r in last10)

        latest = rows[-1]
        msg = (
            f"Results stored: {len(rows)}\n\n"
            f"All-time avg: {avg_time:.0f} ms, {avg_acc:.1f}%\n"
            f"Last 10 avg: {last_time:.0f} ms, {last_acc:.1f}%\n"
            f"Latest: {latest['timestamp']} "
            f"({latest['duration_ms']} ms, {latest['accuracy_pct']:.0f}%)"
        )
        messagebox.showinfo("Stats", msg, parent=self)


def main() -> None:
    """
    Main orchestration flow.
    """
    pin = load_or_create_pin()
    app = ScramblePad(pin)
    app.mainloop()


if __name__ == "__main__":
    main()
