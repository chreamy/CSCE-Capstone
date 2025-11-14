import tkinter as tk
from tkinter import ttk, messagebox
from typing import Iterable, Optional

from ..ui_theme import (
    COLORS,
    FONTS,
    apply_modern_theme,
    create_card,
    create_primary_button,
    create_secondary_button,
)


class NoiseSettingsDialog(tk.Toplevel):
    """Lightweight dialog for configuring noise sweeps."""

    QUANTITY_OPTIONS = {
        "onoise": "Output noise density (V/√Hz)",
        "onoise_db": "Output noise density (dB/√Hz)",
        "inoise": "Input-referred noise density (V/√Hz)",
        "inoise_db": "Input-referred noise density (dB/√Hz)",
    }

    def __init__(
        self,
        parent: tk.Misc,
        nodes: Iterable[str],
        sources: Iterable[str],
        initial_settings: Optional[dict],
    ) -> None:
        super().__init__(parent)
        apply_modern_theme(self)
        self.configure(bg=COLORS["bg_primary"])
        self.title("Noise Analysis Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result: Optional[dict] = None

        normalized_nodes = sorted(
            [node for node in (nodes or []) if node and str(node).strip()],
            key=lambda token: str(token).lower(),
        )
        # Ground node (0) is implicit for single-ended voltages
        self.available_nodes = [node for node in normalized_nodes if str(node).strip() != "0"]
        self.available_sources = list(sources or [])

        settings = initial_settings or {}
        self.output_node_var = tk.StringVar(value=settings.get("output_node", ""))
        self.input_source_var = tk.StringVar(value=settings.get("input_source", ""))
        selected_quantity = settings.get("quantity", "onoise")
        quantity_label = self.QUANTITY_OPTIONS.get(selected_quantity, self.QUANTITY_OPTIONS["onoise"])
        self.quantity_var = tk.StringVar(value=quantity_label)
        self.sweep_var = tk.StringVar(value=str(settings.get("sweep_type", "DEC")).upper())
        self.points_var = tk.StringVar(value=str(settings.get("points", 10)))
        self.start_var = tk.StringVar(value=str(settings.get("start_frequency", 1.0)))
        self.stop_var = tk.StringVar(value=str(settings.get("stop_frequency", 1_000_000.0)))

        self._build_ui()
        self.wait_visibility()
        self.focus_set()

    def _build_ui(self) -> None:
        container = create_card(self)
        container.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)
        body = container.inner

        # Output node + quantity selectors
        tk.Label(
            body,
            text="Measure noise at node",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=0, column=0, sticky=tk.W, pady=6)
        self.output_dropdown = ttk.Combobox(
            body,
            textvariable=self.output_node_var,
            values=self.available_nodes,
            state="readonly" if self.available_nodes else "disabled",
            width=20,
        )
        self.output_dropdown.grid(row=0, column=1, sticky=tk.W, pady=6, padx=(0, 10))

        tk.Label(
            body,
            text="Noise quantity",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=1, column=0, sticky=tk.W, pady=6)
        self.quantity_dropdown = ttk.Combobox(
            body,
            textvariable=self.quantity_var,
            values=list(self.QUANTITY_OPTIONS.values()),
            state="readonly",
            width=32,
        )
        self.quantity_dropdown.grid(row=1, column=1, sticky=tk.W, pady=6, padx=(0, 10))

        tk.Label(
            body,
            text="Driven by source",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=2, column=0, sticky=tk.W, pady=6)
        self.source_dropdown = ttk.Combobox(
            body,
            textvariable=self.input_source_var,
            values=self.available_sources,
            state="readonly" if self.available_sources else "disabled",
            width=20,
        )
        self.source_dropdown.grid(row=2, column=1, sticky=tk.W, pady=6, padx=(0, 10))

        # Sweep controls
        tk.Label(
            body,
            text="Sweep type",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=3, column=0, sticky=tk.W, pady=6)
        ttk.Combobox(
            body,
            textvariable=self.sweep_var,
            values=["DEC", "LIN", "OCT"],
            state="readonly",
            width=12,
        ).grid(row=3, column=1, sticky=tk.W, pady=6)

        tk.Label(
            body,
            text="Points per interval",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=4, column=0, sticky=tk.W, pady=6)
        ttk.Entry(body, textvariable=self.points_var, width=15).grid(row=4, column=1, sticky=tk.W, pady=6)

        tk.Label(
            body,
            text="Start frequency (Hz)",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=5, column=0, sticky=tk.W, pady=6)
        ttk.Entry(body, textvariable=self.start_var, width=20).grid(row=5, column=1, sticky=tk.W, pady=6)

        tk.Label(
            body,
            text="Stop frequency (Hz)",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=6, column=0, sticky=tk.W, pady=6)
        ttk.Entry(body, textvariable=self.stop_var, width=20).grid(row=6, column=1, sticky=tk.W, pady=6)

        for child in body.winfo_children():
            if isinstance(child, ttk.Entry) or isinstance(child, ttk.Combobox):
                child.bind("<Return>", lambda _: self._on_save())

        buttons = tk.Frame(body, bg=COLORS["bg_secondary"])
        buttons.grid(row=7, column=0, columnspan=2, pady=(16, 0), sticky=tk.E)
        create_secondary_button(buttons, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=(0, 10))
        create_primary_button(buttons, text="Save", command=self._on_save).pack(side=tk.RIGHT)

        if not self.available_sources:
            tk.Label(
                body,
                text="No independent voltage or current sources detected in the top-level netlist. "
                "Add a source before running noise analysis.",
                font=FONTS["caption"],
                wraplength=360,
                justify=tk.LEFT,
                bg=COLORS["bg_secondary"],
                fg=COLORS["warning"],
            ).grid(row=8, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)

    def _on_save(self) -> None:
        if not self.available_nodes:
            messagebox.showerror("Missing Node", "No top-level nodes found for noise measurement.")
            return
        if not self.available_sources:
            messagebox.showerror("Missing Source", "Noise analysis requires at least one independent source.")
            return

        node = self.output_node_var.get().strip()
        source = self.input_source_var.get().strip()
        if not node:
            messagebox.showerror("Invalid Node", "Select the node where noise will be measured.")
            return
        if not source:
            messagebox.showerror("Invalid Source", "Select the driving source for noise analysis.")
            return

        try:
            points = int(float(self.points_var.get()))
            start_freq = float(self.start_var.get())
            stop_freq = float(self.stop_var.get())
        except ValueError:
            messagebox.showerror("Invalid Sweep", "Provide numeric values for noise sweep points and frequencies.")
            return

        if points <= 0:
            messagebox.showerror("Invalid Sweep", "Points per interval must be greater than zero.")
            return
        if start_freq <= 0 or stop_freq <= 0:
            messagebox.showerror("Invalid Sweep", "Frequencies must be greater than zero.")
            return
        if stop_freq <= start_freq:
            messagebox.showerror("Invalid Sweep", "Stop frequency must be greater than start frequency.")
            return
        # Ensure the frequency range is not too small
        MIN_FREQ_DIFF = 1e-9
        if (stop_freq - start_freq) < MIN_FREQ_DIFF:
            messagebox.showerror(
                "Invalid Sweep",
                f"Stop frequency and start frequency are too close. Please ensure they differ by at least {MIN_FREQ_DIFF}."
            )
            return

        sweep = (self.sweep_var.get() or "DEC").upper()
        if sweep not in {"DEC", "LIN", "OCT"}:
            sweep = "DEC"

        quantity_label = self.quantity_var.get()
        quantity_key = next(
            (key for key, label in self.QUANTITY_OPTIONS.items() if label == quantity_label),
            "onoise",
        )

        self.result = {
            "output_node": node,
            "input_source": source,
            "quantity": quantity_key,
            "sweep_type": sweep,
            "points": points,
            "start_frequency": start_freq,
            "stop_frequency": stop_freq,
        }
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()
