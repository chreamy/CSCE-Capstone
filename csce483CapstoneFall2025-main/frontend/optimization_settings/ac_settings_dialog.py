import tkinter as tk
from tkinter import ttk, messagebox

from ..ui_theme import (
    COLORS,
    FONTS,
    apply_modern_theme,
    create_card,
    create_primary_button,
    create_secondary_button,
)


class AcSettingsDialog(tk.Toplevel):

    def __init__(self, parent, initial_settings):
        super().__init__(parent)
        apply_modern_theme(self)
        self.configure(bg=COLORS["bg_primary"])
        self.title("AC Analysis Settings")
        self.resizable(False, False)
        self.result = None

        settings = initial_settings or {}
        self.sweep_var = tk.StringVar(value=settings.get("sweep_type", "DEC").upper())
        self.points_var = tk.StringVar(value=str(settings.get("points", 10)))
        self.start_var = tk.StringVar(value=str(settings.get("start_frequency", 1.0)))
        self.stop_var = tk.StringVar(value=str(settings.get("stop_frequency", 1_000_000.0)))
        self.response_value = (settings.get("response") or "magnitude")

        self._build_ui()
        self.grab_set()
        self.transient(parent)
        self.wait_visibility()
        self.focus_set()

    def _build_ui(self):
        container = create_card(self)
        container.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)
        body = container.inner

        tk.Label(
            body,
            text="Sweep Type",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=0, column=0, sticky=tk.W, pady=6)
        sweep_dropdown = ttk.Combobox(
            body,
            textvariable=self.sweep_var,
            values=["DEC", "LIN", "OCT"],
            state="readonly",
            width=12,
        )
        sweep_dropdown.grid(row=0, column=1, sticky=tk.W, pady=6)

        tk.Label(
            body,
            text="Points",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=1, column=0, sticky=tk.W, pady=6)
        ttk.Entry(body, textvariable=self.points_var, width=15).grid(
            row=1, column=1, sticky=tk.W, pady=6
        )

        tk.Label(
            body,
            text="Start Frequency (Hz)",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=2, column=0, sticky=tk.W, pady=6)
        ttk.Entry(body, textvariable=self.start_var, width=20).grid(
            row=2, column=1, sticky=tk.W, pady=6
        )

        tk.Label(
            body,
            text="Stop Frequency (Hz)",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=3, column=0, sticky=tk.W, pady=6)
        ttk.Entry(body, textvariable=self.stop_var, width=20).grid(
            row=3, column=1, sticky=tk.W, pady=6
        )

        buttons = tk.Frame(body, bg=COLORS["bg_secondary"])
        buttons.grid(row=4, column=0, columnspan=2, pady=(14, 0), sticky=tk.E)

        create_secondary_button(buttons, text="Cancel", command=self._on_cancel).pack(
            side=tk.RIGHT, padx=(0, 10)
        )
        create_primary_button(buttons, text="Save", command=self._on_save).pack(
            side=tk.RIGHT
        )

        for child in body.winfo_children():
            if isinstance(child, ttk.Entry) or isinstance(child, ttk.Combobox):
                child.bind("<Return>", lambda _: self._on_save())

    def _on_save(self):
        try:
            points = int(float(self.points_var.get()))
            start_freq = float(self.start_var.get())
            stop_freq = float(self.stop_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please provide numeric values for points and frequencies.")
            return

        if points <= 0:
            messagebox.showerror("Invalid Input", "Points must be greater than zero.")
            return
        if start_freq <= 0 or stop_freq <= 0:
            messagebox.showerror("Invalid Input", "Frequencies must be greater than zero.")
            return
        if stop_freq <= start_freq:
            messagebox.showerror("Invalid Input", "Stop frequency must be greater than start frequency.")
            return

        self.result = {
            "sweep_type": self.sweep_var.get().upper(),
            "points": points,
            "start_frequency": start_freq,
            "stop_frequency": stop_freq,
            "response": self.response_value,
        }
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
