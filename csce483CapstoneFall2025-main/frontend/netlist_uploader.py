import tkinter as tk
from tkinter import ttk, messagebox
from .utils import open_file_dialog
from typing import Optional


class NetlistUploaderWindow(tk.Frame):
    """Window for uploading a netlist file."""

    def __init__(
        self, parent: tk.Tk, controller: "AppController"
    ):  # Use string annotation for type hint
        super().__init__(parent)
        self.controller = controller
        self.netlist_path: Optional[str] = None

        self.upload_button = ttk.Button(
            self, text="Upload Netlist", command=self.upload_netlist
        )
        self.upload_button.pack(pady=20)

        self.status_label = ttk.Label(self, text="")
        self.status_label.pack()

        self.continue_button_frame = tk.Frame(self)
        self.continue_button_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.continue_button = ttk.Button(
            self.continue_button_frame,
            text="Continue",
            command=self.go_to_next_window,
            state=tk.DISABLED,
        )
        self.continue_button.pack(side=tk.RIGHT, padx=10, pady=10)

    def upload_netlist(self) -> None:
        """Handles the netlist upload process."""
        file_path = open_file_dialog()
        if file_path:
            self.netlist_path = file_path
            self.controller.update_app_data("netlist_path", self.netlist_path)
            self.status_label.config(text=f"Netlist uploaded: {self.netlist_path}")
            self.continue_button.config(state=tk.NORMAL)

    def go_to_next_window(self) -> None:
        """Navigates to the next window (parameter selection)."""
        if self.netlist_path:
            self.controller.navigate("parameter_selection")
        else:
            messagebox.showwarning("Warning", "Please upload a netlist first.")
