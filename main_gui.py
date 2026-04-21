from __future__ import annotations

import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from desktop.pipeline import DesktopBatchProcessor


class ASETDesktopGUI:
    COLORS = {
        "app_bg": "#F1F5F9",
        "header_bg": "#0F172A",
        "header_fg": "#F8FAFC",
        "panel_bg": "#FFFFFF",
        "text_primary": "#111827",
        "text_secondary": "#334155",
        "field_bg": "#FFFFFF",
        "button_primary": "#0284C7",
        "button_primary_active": "#0369A1",
        "button_secondary": "#E2E8F0",
        "button_secondary_active": "#CBD5E1",
        "status_info_bg": "#DBEAFE",
        "status_info_fg": "#1E3A8A",
        "status_success_bg": "#DCFCE7",
        "status_success_fg": "#166534",
        "status_error_bg": "#FEE2E2",
        "status_error_fg": "#991B1B",
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ASET Marker Desktop")
        self.root.geometry("1024x620")
        self.root.minsize(900, 560)
        self.root.configure(background=self.COLORS["app_bg"])

        self.repo_root = self._resolve_repo_root()
        self.output_root = self._resolve_output_root()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._setup_styles()

        self.scans_path_var = tk.StringVar()
        self.csv_path_var = tk.StringVar()
        self.reading_answer_key_path_var = tk.StringVar()
        self.qr_answer_key_path_var = tk.StringVar()
        self.ar_answer_key_path_var = tk.StringVar()
        self.concept_map_path_var = tk.StringVar()
        self.output_parent_path_var = tk.StringVar(value=str(self.output_root))
        self.output_folder_name_var = tk.StringVar(value=f"desktop_run_{datetime.now():%Y%m%d_%H%M%S}")
        self.status_var = tk.StringVar(
            value=(
                "Select scans, CSV, separate Reading/QR/AR keys, concept mapping, "
                "and output location."
            )
        )

        self.scroll_canvas = tk.Canvas(
            self.root,
            background=self.COLORS["app_bg"],
            highlightthickness=0,
            bd=0,
        )
        self.scrollbar = ttk.Scrollbar(
            self.root,
            orient="vertical",
            command=self.scroll_canvas.yview,
        )
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        container = ttk.Frame(self.scroll_canvas, style="App.TFrame", padding=(22, 18, 22, 16))
        self._canvas_window = self.scroll_canvas.create_window((0, 0), window=container, anchor="nw")
        container.columnconfigure(0, weight=1)

        header_frame = ttk.Frame(container, style="Header.TFrame", padding=(18, 16, 18, 16))
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(
            header_frame,
            text="ASET Marker Desktop",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header_frame,
            text="Upload files once, run locally, and send email-ready student outputs.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        form_frame = ttk.Frame(container, style="Card.TFrame", padding=(18, 16, 18, 12))
        form_frame.grid(row=1, column=0, sticky="nsew", pady=(14, 10))
        form_frame.columnconfigure(0, weight=1)
        form_frame.columnconfigure(1, weight=0)

        self._add_input_row(
            form_frame,
            row_base=0,
            label_text="Student Scans Directory",
            hint_text="Folder with one merged PDF per student in order: Reading, QR/AR, Writing.",
            variable=self.scans_path_var,
            button_text="Browse Folder",
            button_command=self.pick_scans_folder,
        )
        self._add_input_row(
            form_frame,
            row_base=3,
            label_text="Attendance & Scores CSV",
                hint_text="Headers are matched case-insensitively, in any order. 'Writing %' is used for report writing score.",
            variable=self.csv_path_var,
            button_text="Browse CSV",
            button_command=self.pick_csv,
        )
        self._add_input_row(
            form_frame,
            row_base=6,
            label_text="Reading Answer Key (.txt or .csv)",
            hint_text="35 Reading answers. Supports labeled rows (RC1/A, q1/A) or a single answer column.",
            variable=self.reading_answer_key_path_var,
            button_text="Browse Reading",
            button_command=self.pick_reading_answer_key,
        )
        self._add_input_row(
            form_frame,
            row_base=9,
            label_text="QR Answer Key (.txt or .csv)",
            hint_text="35 QR answers. Supports labeled rows or a single answer column.",
            variable=self.qr_answer_key_path_var,
            button_text="Browse QR",
            button_command=self.pick_qr_answer_key,
        )
        self._add_input_row(
            form_frame,
            row_base=12,
            label_text="AR Answer Key (.txt or .csv)",
            hint_text="35 AR answers. Supports labeled rows or a single answer column.",
            variable=self.ar_answer_key_path_var,
            button_text="Browse AR",
            button_command=self.pick_ar_answer_key,
        )
        self._add_input_row(
            form_frame,
            row_base=15,
            label_text="Concept Mapping JSON",
            hint_text="Maps questions to concepts used in analysis and report comments.",
            variable=self.concept_map_path_var,
            button_text="Browse JSON",
            button_command=self.pick_concept_mapping,
        )
        self._add_input_row(
            form_frame,
            row_base=18,
            label_text="Output Parent Folder",
            hint_text="Choose where the run folder should be created.",
            variable=self.output_parent_path_var,
            button_text="Browse Output",
            button_command=self.pick_output_parent_folder,
        )
        self._add_text_input_row(
            form_frame,
            row_base=21,
            label_text="Output Folder Name",
            hint_text=(
                "Name for this run folder (letters, numbers, spaces, underscore, hyphen). "
                "Must be unique in the selected parent folder."
            ),
            variable=self.output_folder_name_var,
        )

        action_frame = ttk.Frame(container, style="App.TFrame")
        action_frame.grid(row=2, column=0, sticky="ew", pady=(4, 4))
        action_frame.columnconfigure(0, weight=0)
        action_frame.columnconfigure(1, weight=1)

        self.start_btn = ttk.Button(
            action_frame,
            text="Start Marking",
            command=self.start_marking,
            style="Primary.TButton",
        )
        self.start_btn.grid(row=0, column=0, sticky="w")

        ttk.Label(
            action_frame,
            text="All processing runs locally on this machine.",
            style="Muted.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(14, 0))

        self.status_label = ttk.Label(
            container,
            textvariable=self.status_var,
            style="InfoStatus.TLabel",
            anchor="w",
            justify="left",
        )
        self.status_label.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        container.rowconfigure(1, weight=1)
        self.root.bind("<Configure>", self._on_window_resize)
        container.bind("<Configure>", self._on_scrollable_content_configure)
        self.scroll_canvas.bind("<Configure>", self._on_scroll_canvas_configure)
        self.scroll_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.scroll_canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.scroll_canvas.bind_all("<Button-5>", self._on_mousewheel)
        self._set_status(
            (
                "Select scans, CSV, separate Reading/QR/AR keys, concept mapping, "
                "and output location."
            ),
            level="info",
        )

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background=self.COLORS["app_bg"])
        style.configure("Header.TFrame", background=self.COLORS["header_bg"])
        style.configure("Card.TFrame", background=self.COLORS["panel_bg"])

        style.configure(
            "Title.TLabel",
            background=self.COLORS["header_bg"],
            foreground=self.COLORS["header_fg"],
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.COLORS["header_bg"],
            foreground="#D1D5DB",
            font=("Segoe UI", 10),
        )
        style.configure(
            "FieldLabel.TLabel",
            background=self.COLORS["panel_bg"],
            foreground=self.COLORS["text_primary"],
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Hint.TLabel",
            background=self.COLORS["panel_bg"],
            foreground=self.COLORS["text_secondary"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "Muted.TLabel",
            background=self.COLORS["app_bg"],
            foreground=self.COLORS["text_secondary"],
            font=("Segoe UI", 10),
        )

        style.configure(
            "Input.TEntry",
            fieldbackground=self.COLORS["field_bg"],
            foreground=self.COLORS["text_primary"],
            padding=(8, 6),
            font=("Segoe UI", 10),
        )

        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground="#FFFFFF",
            background=self.COLORS["button_primary"],
            borderwidth=0,
            padding=(16, 9),
        )
        style.map(
            "Primary.TButton",
            background=[
                ("pressed", self.COLORS["button_primary_active"]),
                ("active", self.COLORS["button_primary_active"]),
                ("disabled", "#94A3B8"),
            ],
            foreground=[("disabled", "#E2E8F0")],
        )

        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground=self.COLORS["text_primary"],
            background=self.COLORS["button_secondary"],
            padding=(12, 7),
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("pressed", self.COLORS["button_secondary_active"]),
                ("active", self.COLORS["button_secondary_active"]),
            ]
        )

        style.configure(
            "InfoStatus.TLabel",
            background=self.COLORS["status_info_bg"],
            foreground=self.COLORS["status_info_fg"],
            font=("Segoe UI", 10, "bold"),
            padding=(12, 10),
        )
        style.configure(
            "SuccessStatus.TLabel",
            background=self.COLORS["status_success_bg"],
            foreground=self.COLORS["status_success_fg"],
            font=("Segoe UI", 10, "bold"),
            padding=(12, 10),
        )
        style.configure(
            "ErrorStatus.TLabel",
            background=self.COLORS["status_error_bg"],
            foreground=self.COLORS["status_error_fg"],
            font=("Segoe UI", 10, "bold"),
            padding=(12, 10),
        )

    def _add_input_row(
        self,
        parent: ttk.Frame,
        row_base: int,
        label_text: str,
        hint_text: str,
        variable: tk.StringVar,
        button_text: str,
        button_command,
    ) -> None:
        ttk.Label(parent, text=label_text, style="FieldLabel.TLabel").grid(
            row=row_base,
            column=0,
            columnspan=2,
            sticky="w",
        )
        entry = ttk.Entry(parent, textvariable=variable, style="Input.TEntry")
        entry.grid(row=row_base + 1, column=0, sticky="ew", padx=(0, 10), pady=(3, 4), ipady=3)
        ttk.Button(
            parent,
            text=button_text,
            command=button_command,
            style="Secondary.TButton",
            width=14,
        ).grid(row=row_base + 1, column=1, sticky="ew", pady=(3, 4))
        ttk.Label(parent, text=hint_text, style="Hint.TLabel").grid(
            row=row_base + 2,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 8),
        )

    def _add_text_input_row(
        self,
        parent: ttk.Frame,
        row_base: int,
        label_text: str,
        hint_text: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label_text, style="FieldLabel.TLabel").grid(
            row=row_base,
            column=0,
            columnspan=2,
            sticky="w",
        )
        entry = ttk.Entry(parent, textvariable=variable, style="Input.TEntry")
        entry.grid(
            row=row_base + 1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(3, 4),
            ipady=3,
        )
        ttk.Label(parent, text=hint_text, style="Hint.TLabel").grid(
            row=row_base + 2,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 8),
        )

    def _set_status(self, message: str, level: str = "info") -> None:
        style_map = {
            "info": "InfoStatus.TLabel",
            "success": "SuccessStatus.TLabel",
            "error": "ErrorStatus.TLabel",
        }
        self.status_var.set(message)
        self.status_label.configure(style=style_map.get(level, "InfoStatus.TLabel"))

    def _on_window_resize(self, event: tk.Event) -> None:
        if event.widget is self.root:
            wrap_length = max(560, self.root.winfo_width() - 120)
            self.status_label.configure(wraplength=wrap_length)

    def _on_scrollable_content_configure(self, _: tk.Event) -> None:
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))

    def _on_scroll_canvas_configure(self, event: tk.Event) -> None:
        self.scroll_canvas.itemconfigure(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.widget is None:
            return

        widget = event.widget
        if widget is not self.root and not str(widget).startswith(str(self.root)):
            return

        # Linux often emits Button-4/5 instead of MouseWheel.
        if getattr(event, "num", None) == 4:
            self.scroll_canvas.yview_scroll(-1, "units")
            return
        if getattr(event, "num", None) == 5:
            self.scroll_canvas.yview_scroll(1, "units")
            return

        delta = getattr(event, "delta", 0)
        if delta == 0:
            return

        if sys.platform == "darwin":
            steps = -1 if delta > 0 else 1
        else:
            steps = int(-delta / 120)
            if steps == 0:
                steps = -1 if delta > 0 else 1
        self.scroll_canvas.yview_scroll(steps, "units")

    @staticmethod
    def _resolve_repo_root() -> Path:
        if getattr(sys, "frozen", False):
            mei_pass = getattr(sys, "_MEIPASS", None)
            if mei_pass:
                return Path(mei_pass)
        return Path(__file__).resolve().parent

    @staticmethod
    def _resolve_output_root() -> Path:
        if getattr(sys, "frozen", False):
            return Path.home() / "Documents" / "ASETmarker_outputs"
        return Path(__file__).resolve().parent / "outputs"

    @staticmethod
    def _validate_output_folder_name(name: str) -> str:
        if not name:
            return "Please enter an output folder name."
        if name in {".", ".."}:
            return "Output folder name cannot be '.' or '..'."
        if re.search(r"[<>:\"/\\|?*]", name):
            return "Output folder name contains invalid characters."
        return ""

    def pick_scans_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select Exam Folder")
        if selected:
            self.scans_path_var.set(selected)

    def pick_csv(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select Attendance CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if selected:
            self.csv_path_var.set(selected)

    def _pick_answer_key_file(self, target_var: tk.StringVar, title: str) -> None:
        selected = filedialog.askopenfilename(
            title=title,
            filetypes=[
                ("Answer Key Files", "*.txt *.csv"),
                ("Text Files", "*.txt"),
                ("CSV Files", "*.csv"),
                ("All Files", "*.*"),
            ],
        )
        if selected:
            target_var.set(selected)

    def pick_reading_answer_key(self) -> None:
        self._pick_answer_key_file(
            self.reading_answer_key_path_var,
            "Select Reading Answer Key (.txt or .csv)",
        )

    def pick_qr_answer_key(self) -> None:
        self._pick_answer_key_file(
            self.qr_answer_key_path_var,
            "Select QR Answer Key (.txt or .csv)",
        )

    def pick_ar_answer_key(self) -> None:
        self._pick_answer_key_file(
            self.ar_answer_key_path_var,
            "Select AR Answer Key (.txt or .csv)",
        )

    def pick_concept_mapping(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select Concept Mapping JSON",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if selected:
            self.concept_map_path_var.set(selected)

    def pick_output_parent_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select Output Parent Folder")
        if selected:
            self.output_parent_path_var.set(selected)

    def start_marking(self) -> None:
        scans_path = Path(self.scans_path_var.get().strip()) if self.scans_path_var.get().strip() else None
        csv_path = Path(self.csv_path_var.get().strip()) if self.csv_path_var.get().strip() else None
        reading_answer_key_path = (
            Path(self.reading_answer_key_path_var.get().strip())
            if self.reading_answer_key_path_var.get().strip()
            else None
        )
        qr_answer_key_path = (
            Path(self.qr_answer_key_path_var.get().strip())
            if self.qr_answer_key_path_var.get().strip()
            else None
        )
        ar_answer_key_path = (
            Path(self.ar_answer_key_path_var.get().strip())
            if self.ar_answer_key_path_var.get().strip()
            else None
        )
        concept_map_path = (
            Path(self.concept_map_path_var.get().strip())
            if self.concept_map_path_var.get().strip()
            else None
        )
        output_parent_raw = self.output_parent_path_var.get().strip()
        output_parent_path = Path(output_parent_raw) if output_parent_raw else self.output_root
        output_folder_name = self.output_folder_name_var.get().strip()

        if scans_path is None or not scans_path.exists():
            messagebox.showerror("Invalid Input", "Please select a valid scans directory.")
            return
        if not scans_path.is_dir():
            messagebox.showerror("Invalid Input", "Scans input must be a directory containing merged PDFs.")
            return

        if csv_path is None or not csv_path.exists():
            messagebox.showerror("Invalid Input", "Please select a valid student CSV file.")
            return

        if reading_answer_key_path is None or not reading_answer_key_path.exists():
            messagebox.showerror("Invalid Input", "Please select a valid Reading answer key (.txt or .csv) file.")
            return

        if qr_answer_key_path is None or not qr_answer_key_path.exists():
            messagebox.showerror("Invalid Input", "Please select a valid QR answer key (.txt or .csv) file.")
            return

        if ar_answer_key_path is None or not ar_answer_key_path.exists():
            messagebox.showerror("Invalid Input", "Please select a valid AR answer key (.txt or .csv) file.")
            return

        if concept_map_path is None or not concept_map_path.exists():
            messagebox.showerror("Invalid Input", "Please select a valid concept mapping JSON file.")
            return

        name_error = self._validate_output_folder_name(output_folder_name)
        if name_error:
            messagebox.showerror("Invalid Output Name", name_error)
            return

        try:
            output_parent_path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror(
                "Invalid Output Folder",
                f"Could not create/access output parent folder:\n{output_parent_path}\n\n{exc}",
            )
            return

        run_output_dir = output_parent_path / output_folder_name
        if run_output_dir.exists():
            messagebox.showerror(
                "Output Folder Exists",
                f"The output folder already exists:\n{run_output_dir}\n\nChoose a different folder name.",
            )
            return

        self.start_btn.configure(state="disabled")
        self._set_status("Marking in progress. Please wait...", level="info")

        worker = threading.Thread(
            target=self._run_marking,
            args=(
                scans_path,
                csv_path,
                reading_answer_key_path,
                qr_answer_key_path,
                ar_answer_key_path,
                concept_map_path,
                run_output_dir,
            ),
            daemon=True,
        )
        worker.start()

    def _run_marking(
        self,
        scans_path: Path,
        csv_path: Path,
        reading_answer_key_path: Path,
        qr_answer_key_path: Path,
        ar_answer_key_path: Path,
        concept_map_path: Path,
        run_output_dir: Path,
    ) -> None:
        try:
            processor = DesktopBatchProcessor(
                repo_root=self.repo_root,
                reading_answer_key_path=reading_answer_key_path,
                qr_answer_key_path=qr_answer_key_path,
                ar_answer_key_path=ar_answer_key_path,
                concept_mapping_path=concept_map_path,
            )
            summary = processor.run(scans_path=scans_path, csv_path=csv_path, output_dir=run_output_dir)
            success_count = sum(1 for row in summary.results if row.status == "Success")
            total_count = len(summary.results)
            failed_rows = [row for row in summary.results if row.status != "Success"]

            if failed_rows:
                issue_lines = []
                for row in failed_rows:
                    note = row.notes.strip() if row.notes else "Unknown error"
                    issue_lines.append(f"- {row.name}: {note}")
                issues_text = "\n".join(issue_lines)
                done_message = (
                    f"Completed: {success_count}/{total_count} students succeeded. "
                    f"Skipped/failed: {len(failed_rows)}. "
                    f"Debug log: {summary.output_dir / 'debug_run.log'}\n"
                    f"Issues:\n{issues_text}"
                )
            else:
                done_message = (
                    f"Completed: {success_count}/{total_count} students succeeded. "
                    f"Output folder: {summary.output_dir}"
                )
            self.root.after(0, lambda: self._on_success(done_message))
        except Exception as exc:
            error_message = str(exc)
            self.root.after(0, lambda error_message=error_message: self._on_error(error_message))

    def _on_success(self, message: str) -> None:
        self.start_btn.configure(state="normal")
        self._set_status(message, level="success")
        messagebox.showinfo("Marking Complete", message)

    def _on_error(self, error: str) -> None:
        self.start_btn.configure(state="normal")
        self._set_status(f"Error: {error}", level="error")
        messagebox.showerror("Marking Failed", error)


def main() -> None:
    root = tk.Tk()
    app = ASETDesktopGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
