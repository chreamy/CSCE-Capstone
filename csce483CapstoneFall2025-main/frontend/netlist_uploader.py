import os
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from .utils import open_executable_dialog, open_file_dialog
from .ui_theme import (
    COLORS,
    FONTS,
    create_card,
    create_primary_button,
    create_secondary_button,
)


class NetlistUploaderWindow(tk.Frame):
    """Window for uploading a netlist file."""

    def __init__(self, parent: tk.Tk, controller: "AppController"):
        super().__init__(parent, bg=COLORS["bg_primary"])
        self.controller = controller
        self.netlist_path: Optional[str] = None
        self.xyce_executable_path: Optional[str] = None

        # Layout: header
        header = tk.Frame(
            self,
            bg=COLORS["bg_secondary"],
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        header.pack(fill=tk.X, padx=32, pady=(32, 16))
        tk.Label(
            header,
            text="Upload Netlist",
            font=FONTS["title"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(anchor="w", padx=24, pady=(18, 4))
        tk.Label(
            header,
            text="Select the SPICE netlist file that will be used for optimization.",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_secondary"],
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=24, pady=(0, 18))

        # Content card
        card = create_card(self)
        card.pack(fill=tk.BOTH, expand=True, padx=32, pady=(0, 16))
        content = card.inner

        self.upload_button = create_primary_button(
            content, text="Upload Netlist", command=self.upload_netlist
        )
        self.upload_button.pack(pady=(0, 16))

        self.status_label = tk.Label(
            content,
            text="No file selected yet.",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_secondary"],
            wraplength=500,
            justify=tk.CENTER,
        )
        self.status_label.pack(fill=tk.X, pady=(0, 24))

        self.xyce_button = create_primary_button(
            content, text="Select Xyce Executable", command=self.select_xyce_executable
        )
        self.xyce_button.pack(pady=(0, 16))

        self.xyce_status_label = tk.Label(
            content,
            text="Using default 'Xyce' command from PATH",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_secondary"],
            wraplength=500,
            justify=tk.CENTER,
        )
        self.xyce_status_label.pack(fill=tk.X)

        # Navigation footer
        footer = tk.Frame(self, bg=COLORS["bg_primary"])
        footer.pack(fill=tk.X, padx=32, pady=(0, 32))

        self.cancel_button = create_secondary_button(
            footer, text="Exit", command=self.controller.root.quit
        )
        self.cancel_button.pack(side=tk.LEFT)

        self.continue_button = create_primary_button(
            footer, text="Continue", command=self.go_to_next_window
        )
        self.continue_button.configure(state=tk.DISABLED)
        self.continue_button.pack(side=tk.RIGHT)

    def upload_netlist(self) -> None:
        """Handles the netlist upload process."""
        file_path = open_file_dialog()
        if file_path:
            self.netlist_path = file_path
            self.controller.update_app_data("netlist_path", self.netlist_path)
            self.status_label.config(
                text=f"Netlist ready: {self.netlist_path}",
                fg=COLORS["success"],
            )
            self.continue_button.config(state=tk.NORMAL)
        else:
            self.status_label.config(
                text="File selection cancelled. Please choose a SPICE netlist.",
                fg=COLORS["warning"],
            )

    def select_xyce_executable(self) -> None:
        """Handles the Xyce executable selection."""
        file_path = open_executable_dialog()
        if file_path:
            normalized_path = os.path.abspath(file_path)
            if not os.path.isfile(normalized_path):
                messagebox.showerror(
                    "Invalid File",
                    "The selected path is not a file. Please choose a valid executable.",
                )
                self._refresh_xyce_status_label()
                return

            is_executable = os.access(normalized_path, os.X_OK)
            if os.name == "nt":
                # Windows may not mark executables with X_OK flags; allow common extensions
                is_executable = normalized_path.lower().endswith(".exe") or is_executable

            if not is_executable:
                messagebox.showerror(
                    "Invalid File",
                    "Please select a file that can be executed by Xyce.",
                )
                self._refresh_xyce_status_label()
                return

            self.xyce_executable_path = normalized_path
            self.controller.update_app_data(
                "xyce_executable_path", self.xyce_executable_path
            )
            self.xyce_status_label.config(
                text=f"Selected: {normalized_path}",
                fg=COLORS["success"],
            )
        else:
            # Keep existing selection if present; only reset the UI message
            self._refresh_xyce_status_label()

    def go_to_next_window(self) -> None:
        """Navigates to the next window (parameter selection)."""
        if self.netlist_path:
            self.controller.navigate("parameter_selection")
        else:
            messagebox.showwarning("Warning", "Please upload a netlist first.")

    def _refresh_xyce_status_label(self) -> None:
        """Update the status label based on the current executable selection."""
        if self.xyce_executable_path:
            self.xyce_status_label.config(
                text=f"Selected: {self.xyce_executable_path}",
                fg=COLORS["success"],
            )
        else:
            self.xyce_status_label.config(
                text="Using default 'Xyce' command from PATH",
                fg=COLORS["text_secondary"],
            )
