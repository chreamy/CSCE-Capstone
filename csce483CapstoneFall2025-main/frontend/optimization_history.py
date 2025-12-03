import os
import shutil
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk
from typing import Optional
import traceback

from .ui_theme import COLORS, FONTS, create_primary_button, create_secondary_button


class OptimizationHistoryWindow(tk.Frame):
    """Window for viewing optimization history."""

    def __init__(self, parent: tk.Tk, controller: "AppController"):
        super().__init__(parent, bg=COLORS["bg_primary"])
        self.controller = controller
        self.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(
            self,
            bg=COLORS["bg_secondary"],
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        header.pack(fill=tk.X, padx=32, pady=(32, 16))

        header_content = tk.Frame(header, bg=COLORS["bg_secondary"])
        header_content.pack(fill=tk.X, padx=24, pady=18)

        header_left = tk.Frame(header_content, bg=COLORS["bg_secondary"])
        header_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(
            header_left,
            text="Optimization History",
            font=FONTS["title"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(anchor="w")
        tk.Label(
            header_left,
            text="Browse and review previous optimization runs",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_secondary"],
            wraplength=400,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(4, 0))

        header_right = tk.Frame(header_content, bg=COLORS["bg_secondary"])
        header_right.pack(side=tk.RIGHT, padx=(10, 0))
        self.header_back_button = create_secondary_button(
            header_right,
            text="< Back",
            command=self.go_back,
        )
        self.header_back_button.pack(side=tk.LEFT, padx=(0, 10))
        self.clear_history_button = tk.Button(
            header_right,
            text="Clear History",
            font=FONTS["button"],
            bg=COLORS["error"],
            fg="#ffffff",
            bd=0,
            relief=tk.FLAT,
            padx=20,
            pady=10,
            command=self.clear_all_sessions,
            cursor="hand2",
        )
        self.clear_history_button.pack(side=tk.LEFT)

        # Content area
        content_frame = tk.Frame(self, bg=COLORS["bg_primary"])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=32, pady=(0, 16))

        list_frame = tk.Frame(
            content_frame,
            bg=COLORS["bg_secondary"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        details_frame = tk.Frame(
            content_frame,
            bg=COLORS["bg_secondary"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        tk.Label(
            list_frame,
            text="Optimization Runs",
            font=FONTS["heading"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(pady=(20, 10), padx=20)

        tree_container = tk.Frame(list_frame, bg=COLORS["bg_secondary"])
        tree_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        scrollbar = ttk.Scrollbar(tree_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(
            tree_container,
            columns=("Date", "Time", "Status"),
            show="tree headings",
            yscrollcommand=scrollbar.set,
            selectmode="browse",
        )
        scrollbar.config(command=self.tree.yview)
        self.tree.heading("#0", text="Session")
        self.tree.heading("Date", text="Date")
        self.tree.heading("Time", text="Time")
        self.tree.heading("Status", text="Status")
        self.tree.column("#0", width=120, minwidth=100)
        self.tree.column("Date", width=100, minwidth=80)
        self.tree.column("Time", width=100, minwidth=80)
        self.tree.column("Status", width=100, minwidth=80)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_session_select)

        tk.Label(
            details_frame,
            text="Session Details",
            font=FONTS["heading"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(pady=(20, 10), padx=20)

        details_container = tk.Frame(details_frame, bg=COLORS["bg_secondary"])
        details_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        self.details_text = scrolledtext.ScrolledText(
            details_container,
            bg=COLORS["log_bg"],
            fg=COLORS["text_primary"],
            font=("Consolas", 10),
            wrap=tk.WORD,
            bd=1,
            relief=tk.FLAT,
            padx=15,
            pady=15,
            state=tk.DISABLED,
        )
        self.details_text.pack(fill=tk.BOTH, expand=True)

        button_frame = tk.Frame(details_frame, bg=COLORS["bg_secondary"])
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        self.open_folder_button = create_secondary_button(
            button_frame,
            text="Open Folder",
            command=self.open_session_folder,
        )
        self.open_folder_button.pack(side=tk.LEFT, padx=(0, 10))
        self.open_folder_button.config(state=tk.DISABLED)

        self.view_log_button = create_secondary_button(
            button_frame,
            text="View Full Log",
            command=self.view_full_log,
        )
        self.view_log_button.pack(side=tk.LEFT)
        self.view_log_button.config(state=tk.DISABLED)

        footer = tk.Frame(self, bg=COLORS["bg_primary"])
        footer.pack(fill=tk.X, padx=32, pady=(0, 32))
        self.refresh_button = create_primary_button(
            footer,
            text="Refresh",
            command=self.load_sessions,
        )
        self.refresh_button.pack(side=tk.RIGHT)

        self.current_session_path: Optional[str] = None
        self.load_sessions()

    def _runs_root(self) -> str:
        """Mirror backend workspace resolution so history finds the same runs."""
        return os.path.abspath(os.environ.get("XYCLOPS_WORKSPACE") or "runs")

    def load_sessions(self) -> None:
        """Scan runs directory and populate the tree."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        runs_root = self._runs_root()
        results_root = os.path.join(runs_root, "netlist-results")
        if not os.path.exists(results_root):
            self.tree.insert("", "end", text="No runs found", values=("", "", ""))
            return

        try:
            netlist_folders = [
                folder
                for folder in os.listdir(results_root)
                if os.path.isdir(os.path.join(results_root, folder))
            ]
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to read optimization history:\n{e}")
            self.tree.insert("", "end", text=f"Error: {type(e).__name__}", values=("", "", ""))
            return

        if not netlist_folders:
            self.tree.insert("", "end", text="No runs found", values=("", "", ""))
            return

        netlist_folders.sort()

        for netlist_folder in netlist_folders:
            group_path = os.path.join(results_root, netlist_folder)
            group_node = self.tree.insert("", "end", text=netlist_folder, values=("", "", ""), open=False)

            try:
                session_dirs = []
                for name in os.listdir(group_path):
                    session_path = os.path.join(group_path, name)
                    if os.path.isdir(session_path):
                        try:
                            session_num = int(name)
                        except ValueError:
                            continue
                        session_dirs.append((session_num, session_path))

                session_dirs.sort(key=lambda x: x[0])

                for session_num, session_path in session_dirs:
                    log_file = os.path.join(session_path, "session.log")
                    date_str = ""
                    time_str = ""
                    status = "No Log"

                    if os.path.exists(log_file):
                        try:
                            mod_time = os.path.getmtime(log_file)
                            dt = datetime.fromtimestamp(mod_time)
                            date_str = dt.strftime("%Y-%m-%d")
                            time_str = dt.strftime("%H:%M:%S")

                            with open(log_file, "r", encoding="utf-8") as f:
                                content = f.read()

                            status = "Incomplete"
                            if "END OF OPTIMIZATION SESSION" in content:
                                if "Optimization completed" in content:
                                    status = "Complete"
                                elif "Optimization failed" in content:
                                    status = "Failed"
                                else:
                                    status = "Complete"
                        except Exception as e:
                            traceback.print_exc()
                            status = f"Error: {type(e).__name__}"

                    self.tree.insert(
                        group_node,
                        "end",
                        text=f"Session {session_num}",
                        values=(date_str, time_str, status),
                        tags=(session_path,),
                    )
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", f"Failed to load session group '{netlist_folder}':\n{e}")
                self.tree.insert(group_node, "end", text=f"Error: {type(e).__name__}", values=("", "", ""))

    def on_session_select(self, event) -> None:
        """Handle session selection."""
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        tags = self.tree.item(item, "tags")

        if tags and len(tags) > 0:
            session_path = tags[0]
            self.current_session_path = session_path
            self.load_session_details(session_path)
            self.open_folder_button.config(state=tk.NORMAL)
            self.view_log_button.config(state=tk.NORMAL)
        else:
            self.current_session_path = None
            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, "Select a session to view details")
            self.details_text.config(state=tk.DISABLED)
            self.open_folder_button.config(state=tk.DISABLED)
            self.view_log_button.config(state=tk.DISABLED)

    def load_session_details(self, session_path: str) -> None:
        """Load and display session details."""
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)

        log_file = os.path.join(session_path, "session.log")
        if not os.path.exists(log_file):
            self.details_text.insert(1.0, "No session log found")
            self.details_text.config(state=tk.DISABLED)
            return

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()

            lines = content.split("\n")
            summary = []

            for line in lines[:50]:
                if any(
                    keyword in line
                    for keyword in [
                        "Session started at:",
                        "Target value:",
                        "Netlist file:",
                        "Analysis type:",
                        "X-axis variable:",
                        "AC response:",
                        "Noise quantity:",
                        "xtol:",
                        "gtol:",
                        "ftol:",
                        "Total Xyce runs:",
                        "Least squares iterations:",
                        "Initial cost:",
                        "Final cost:",
                        "Optimality:",
                        "Optimization completed",
                        "Optimization failed",
                    ]
                ):
                    summary.append(line)

            for i, line in enumerate(lines):
                if "Optimization metrics:" in line:
                    summary.extend(lines[i : i + 7])
                    break

            if summary:
                self.details_text.insert(1.0, "\n".join(summary))
            else:
                self.details_text.insert(1.0, "No summary information found\n\n")
                self.details_text.insert(
                    tk.END,
                    content[:2000] + "\n...\n(Use 'View Full Log' to see complete log)",
                )
        except Exception as e:
            traceback.print_exc()
            self.details_text.insert(1.0, f"Error loading session details: {e}")

        self.details_text.config(state=tk.DISABLED)

    def open_session_folder(self) -> None:
        """Open the session folder in file explorer."""
        if not self.current_session_path:
            return

        try:
            if sys.platform == "win32":
                os.startfile(self.current_session_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.current_session_path])
            else:
                subprocess.Popen(["xdg-open", self.current_session_path])
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def view_full_log(self) -> None:
        """Open full log in a new window."""
        if not self.current_session_path:
            return

        log_file = os.path.join(self.current_session_path, "session.log")
        if not os.path.exists(log_file):
            messagebox.showerror("Error", "No session log found.")
            return

        log_window = tk.Toplevel(self)
        log_window.title(f"Session Log - {os.path.basename(self.current_session_path)}")
        log_window.geometry("900x700")

        text_frame = tk.Frame(log_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            yscrollcommand=scrollbar.set,
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
            text_widget.insert(1.0, content)
            text_widget.config(state=tk.DISABLED)
        except Exception as e:
            traceback.print_exc()
            text_widget.insert(1.0, f"Error loading log: {e}")
            text_widget.config(state=tk.DISABLED)

        close_btn = tk.Button(
            log_window,
            text="Close",
            command=log_window.destroy,
            padx=20,
            pady=10,
        )
        close_btn.pack(pady=(0, 10))

    def clear_all_sessions(self) -> None:
        """Delete all sessions with confirmation."""
        result = messagebox.askyesno(
            "Confirm Clear All",
            "WARNING: This will permanently delete ALL optimization history.\n\n"
            "Are you sure you want to continue?",
            icon="warning",
        )
        if not result:
            return

        result2 = messagebox.askyesno(
            "Final Confirmation",
            "This is your last chance to cancel.\n\nDelete ALL optimization runs?",
            icon="warning",
        )
        if not result2:
            return

        try:
            runs_dir = self._runs_root()
            if os.path.exists(runs_dir):
                for item in os.listdir(runs_dir):
                    item_path = os.path.join(runs_dir, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)

            self.current_session_path = None
            self.load_sessions()

            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, "All sessions cleared")
            self.details_text.config(state=tk.DISABLED)

            self.open_folder_button.config(state=tk.DISABLED)
            self.view_log_button.config(state=tk.DISABLED)

            messagebox.showinfo("Success", "All optimization history has been cleared.")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to clear history:\n{e}")

    def go_back(self) -> None:
        """Navigate back to optimization summary."""
        self.controller.navigate("optimization_summary")
