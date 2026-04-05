from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from desktop.pipeline import DesktopBatchProcessor


class ASETDesktopGUI:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("ASET Marker Desktop")
        self.root.geometry("900x540")
        self.root.minsize(860, 500)

        self.repo_root = Path(__file__).resolve().parent

        self.mode_var = ctk.StringVar(value="batch")

        self.single_doc_var = ctk.StringVar()
        self.single_name_var = ctk.StringVar()
        self.single_writing_var = ctk.StringVar(value="0")

        self.batch_scans_var = ctk.StringVar()
        self.batch_roster_var = ctk.StringVar()

        self.status_var = ctk.StringVar(value="Select a workflow and provide inputs, then start marking.")

        container = ctk.CTkFrame(self.root, corner_radius=8)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        header = ctk.CTkLabel(
            container,
            text="ASET Marker Desktop",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        header.pack(anchor="w", padx=16, pady=(16, 8))

        mode_switch = ctk.CTkSegmentedButton(
            container,
            values=["single", "batch"],
            variable=self.mode_var,
            command=self._on_mode_change,
        )
        mode_switch.pack(anchor="w", padx=16, pady=(0, 14))

        self.single_frame = ctk.CTkFrame(container, corner_radius=8)
        self.single_frame.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(self.single_frame, text="Single Student: Merged Exam Document").grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        ctk.CTkEntry(self.single_frame, textvariable=self.single_doc_var).grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=(12, 8), pady=(0, 8)
        )
        ctk.CTkButton(self.single_frame, text="Pick File", command=self.pick_single_doc).grid(
            row=1, column=3, sticky="ew", padx=(0, 12), pady=(0, 8)
        )

        ctk.CTkLabel(self.single_frame, text="Student Name").grid(
            row=2, column=0, sticky="w", padx=12, pady=(6, 4)
        )
        ctk.CTkLabel(self.single_frame, text="Writing Score").grid(
            row=2, column=1, sticky="w", padx=8, pady=(6, 4)
        )

        ctk.CTkEntry(self.single_frame, textvariable=self.single_name_var).grid(
            row=3, column=0, sticky="ew", padx=12, pady=(0, 12)
        )
        ctk.CTkEntry(self.single_frame, textvariable=self.single_writing_var).grid(
            row=3, column=1, sticky="ew", padx=8, pady=(0, 12)
        )

        self.batch_frame = ctk.CTkFrame(container, corner_radius=8)
        self.batch_frame.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(self.batch_frame, text="Batch Processing: Exam Folder or Single File").grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        ctk.CTkEntry(self.batch_frame, textvariable=self.batch_scans_var).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=(12, 8), pady=(0, 8)
        )
        ctk.CTkButton(self.batch_frame, text="Pick Folder", command=self.pick_scans_folder).grid(
            row=1, column=2, sticky="ew", padx=(0, 6), pady=(0, 8)
        )
        ctk.CTkButton(self.batch_frame, text="Pick File", command=self.pick_scans_file).grid(
            row=1, column=3, sticky="ew", padx=(0, 12), pady=(0, 8)
        )

        ctk.CTkLabel(self.batch_frame, text="Master Roster (.csv/.xlsx/.xls)").grid(
            row=2, column=0, sticky="w", padx=12, pady=(6, 6)
        )
        ctk.CTkEntry(self.batch_frame, textvariable=self.batch_roster_var).grid(
            row=3, column=0, columnspan=3, sticky="ew", padx=(12, 8), pady=(0, 12)
        )
        ctk.CTkButton(self.batch_frame, text="Pick Roster", command=self.pick_roster).grid(
            row=3, column=3, sticky="ew", padx=(0, 12), pady=(0, 12)
        )

        action_row = ctk.CTkFrame(container, fg_color="transparent")
        action_row.pack(fill="x", padx=16, pady=(0, 6))

        self.start_btn = ctk.CTkButton(action_row, text="Start Marking", command=self.start_marking)
        self.start_btn.pack(side="left")

        ctk.CTkLabel(container, textvariable=self.status_var, justify="left", wraplength=840).pack(
            anchor="w", padx=16, pady=(8, 16)
        )

        self.single_frame.columnconfigure(0, weight=3)
        self.single_frame.columnconfigure(1, weight=1)
        self.single_frame.columnconfigure(2, weight=1)
        self.single_frame.columnconfigure(3, weight=0)

        self.batch_frame.columnconfigure(0, weight=3)
        self.batch_frame.columnconfigure(1, weight=1)
        self.batch_frame.columnconfigure(2, weight=0)
        self.batch_frame.columnconfigure(3, weight=0)

        self._on_mode_change(self.mode_var.get())

    def pick_scans_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select Exam Folder")
        if selected:
            self.batch_scans_var.set(selected)

    def pick_single_doc(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select Merged Exam File",
            filetypes=[
                ("Supported Scans", "*.pdf *.tif *.tiff *.png *.jpg *.jpeg"),
                ("All Files", "*.*"),
            ],
        )
        if selected:
            self.single_doc_var.set(selected)

    def pick_scans_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select Merged Exam File",
            filetypes=[
                ("Supported Scans", "*.pdf *.tif *.tiff *.png *.jpg *.jpeg"),
                ("All Files", "*.*"),
            ],
        )
        if selected:
            self.batch_scans_var.set(selected)

    def pick_roster(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select Master Roster",
            filetypes=[("Roster Files", "*.csv *.xlsx *.xls"), ("All Files", "*.*")],
        )
        if selected:
            self.batch_roster_var.set(selected)

    def _on_mode_change(self, mode: str) -> None:
        if mode == "single":
            self.single_frame.pack(fill="x", padx=16, pady=(0, 10))
            self.batch_frame.pack_forget()
            self.status_var.set("Single Student mode: choose one 3-page merged document, then enter name and writing score.")
            return

        self.batch_frame.pack(fill="x", padx=16, pady=(0, 10))
        self.single_frame.pack_forget()
        self.status_var.set("Batch mode: choose exam folder/file and a roster spreadsheet with student name + writing score.")

    def start_marking(self) -> None:
        mode = self.mode_var.get()
        self.start_btn.configure(state="disabled")
        self.status_var.set("Marking in progress. Please wait...")

        if mode == "single":
            doc_path = Path(self.single_doc_var.get().strip()) if self.single_doc_var.get().strip() else None
            student_name = self.single_name_var.get().strip()
            writing_raw = self.single_writing_var.get().strip()

            if doc_path is None or not doc_path.exists():
                self.start_btn.configure(state="normal")
                messagebox.showerror("Invalid Input", "Please select a valid merged exam file.")
                return
            if not student_name:
                self.start_btn.configure(state="normal")
                messagebox.showerror("Invalid Input", "Please enter a student name.")
                return
            try:
                writing_score = float(writing_raw)
            except ValueError:
                self.start_btn.configure(state="normal")
                messagebox.showerror("Invalid Input", "Writing score must be a number.")
                return

            worker = threading.Thread(
                target=self._run_single_marking,
                args=(doc_path, student_name, writing_score),
                daemon=True,
            )
            worker.start()
            return

        scans_path = Path(self.batch_scans_var.get().strip()) if self.batch_scans_var.get().strip() else None
        roster_path = Path(self.batch_roster_var.get().strip()) if self.batch_roster_var.get().strip() else None

        if scans_path is None or not scans_path.exists():
            self.start_btn.configure(state="normal")
            messagebox.showerror("Invalid Input", "Please select a valid exam file or folder.")
            return
        if roster_path is None or not roster_path.exists():
            self.start_btn.configure(state="normal")
            messagebox.showerror("Invalid Input", "Please select a valid roster file.")
            return

        worker = threading.Thread(
            target=self._run_batch_marking,
            args=(scans_path, roster_path),
            daemon=True,
        )
        worker.start()

    def _run_single_marking(self, doc_path: Path, student_name: str, writing_score: float) -> None:
        try:
            processor = DesktopBatchProcessor(repo_root=self.repo_root)
            summary = processor.run_single(
                merged_doc_path=doc_path,
                student_name=student_name,
                writing_score=writing_score,
            )
            done_message = (
                f"Completed single-student marking for {summary.result.name}. "
                f"Output folder: {summary.result.output_dir}"
            )
            self.root.after(0, lambda: self._on_success(done_message))
        except Exception as exc:
            self.root.after(0, lambda: self._on_error(str(exc)))

    def _run_batch_marking(self, scans_path: Path, roster_path: Path) -> None:
        try:
            processor = DesktopBatchProcessor(repo_root=self.repo_root)
            summary = processor.run_batch(scans_path=scans_path, roster_path=roster_path)
            success_count = sum(1 for row in summary.results if row.status == "Success")
            total_count = len(summary.results)
            done_message = (
                f"Completed: {success_count}/{total_count} students succeeded. "
                f"Output folder: {summary.output_dir}"
            )
            self.root.after(0, lambda: self._on_success(done_message))
        except Exception as exc:
            self.root.after(0, lambda: self._on_error(str(exc)))

    def _on_success(self, message: str) -> None:
        self.start_btn.configure(state="normal")
        self.status_var.set(message)
        messagebox.showinfo("Marking Complete", message)

    def _on_error(self, error: str) -> None:
        self.start_btn.configure(state="normal")
        self.status_var.set(f"Error: {error}")
        messagebox.showerror("Marking Failed", error)


def main() -> None:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()

    app = ASETDesktopGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
