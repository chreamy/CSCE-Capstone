import tkinter as tk

from tkinter import ttk, messagebox
from typing import List, Dict, Any, Optional
from .add_constraint_dialog import AddConstraintDialog
from .edit_constraint_dialog import EditConstraintDialog
from .constraint_table import ConstraintTable
from .curve_fit_settings import CurveFitSettings
from .ac_settings_dialog import AcSettingsDialog
from .noise_settings_dialog import NoiseSettingsDialog
from ..utils import import_constraints_from_file, export_constraints_to_file
from ..ui_theme import (
    COLORS,
    FONTS,
    create_primary_button,
    create_secondary_button,
    create_card,
)


class OptimizationSettingsWindow(tk.Frame):
    def validate_float(self, var_name):
        try:
            val = float(getattr(self, var_name).get())
            return True
        except ValueError:
            messagebox.showerror(
                "Invalid Input",
                f"Please enter a valid number for {var_name.replace('_var', '')}",
            )
            getattr(self, var_name).set("1e-12")  # Reset to default if invalid
            return False

    def __init__(self, parent: tk.Tk, controller: "AppController"):
        super().__init__(parent, bg=COLORS["bg_primary"])
        self.controller = controller  # Assign controller first

        # --- Get data needed to build the lists ---
        self.selected_parameters = (
            self.controller.get_app_data("selected_parameters") or []
        )  # Ensure it's a list
        self.nodes = self.controller.get_app_data("nodes") or []  # Ensure it's a list

        stored_analysis_type = (
            self.controller.get_app_data("analysis_type") or "transient"
        ).lower()
        stored_ac_settings = self.controller.get_app_data("ac_settings") or {}
        stored_tran_settings = self.controller.get_app_data("tran_settings") or {}
        stored_noise_settings = self.controller.get_app_data("noise_settings") or {}
        self.source_names = list(self.controller.get_app_data("source_names") or [])
        def _as_float(value, default):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def _as_int(value, default):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return default

        def _as_str(value, default=""):
            if value is None:
                return default
            text = str(value).strip()
            return text if text else default

        if stored_analysis_type == "ac":
            self.analysis_type = "ac"
        elif stored_analysis_type == "noise":
            self.analysis_type = "noise"
        else:
            self.analysis_type = "transient"
        self.ac_settings = {
            "sweep_type": str(stored_ac_settings.get("sweep_type", "DEC")).upper(),
            "points": _as_int(stored_ac_settings.get("points"), 10),
            "start_frequency": _as_float(stored_ac_settings.get("start_frequency"), 1.0),
            "stop_frequency": _as_float(stored_ac_settings.get("stop_frequency"), 1_000_000.0),
            "response": str(stored_ac_settings.get("response", "magnitude")).lower(),
        }
        self.noise_settings = {
            "sweep_type": str(stored_noise_settings.get("sweep_type", "DEC")).upper(),
            "points": _as_int(stored_noise_settings.get("points"), 10),
            "start_frequency": _as_float(stored_noise_settings.get("start_frequency"), 1.0),
            "stop_frequency": _as_float(stored_noise_settings.get("stop_frequency"), 1_000_000.0),
            "output_node": _as_str(stored_noise_settings.get("output_node")),
            "input_source": _as_str(stored_noise_settings.get("input_source")),
            "quantity": str(stored_noise_settings.get("quantity", "onoise")).lower(),
        }
        if self.noise_settings["quantity"] not in {"onoise", "onoise_db", "inoise", "inoise_db"}:
            self.noise_settings["quantity"] = "onoise"

        self.tran_settings = {
            "tstop": _as_float(stored_tran_settings.get("tstop"), None),
            "tstep": _as_float(stored_tran_settings.get("tstep"), None),
            "tstart": _as_float(stored_tran_settings.get("tstart"), None),
            "max_step": _as_float(stored_tran_settings.get("max_step"), None),
            "uic": bool(stored_tran_settings.get("uic", False)),
        }

        # --- Now build the lists ---
        self.node_voltage_expressions = [
            f"V({node})" for node in self.nodes if node != "0"
        ]

        # --- NOW it's safe to create the combined list ---
        self.allowed_constraint_left_sides: List[str] = (
            self.selected_parameters + self.node_voltage_expressions
        )
        deduped = []
        seen_ct = set()
        for item in self.allowed_constraint_left_sides:
            if item in seen_ct:
                continue
            seen_ct.add(item)
            deduped.append(item)
        self.allowed_constraint_left_sides = sorted(deduped)

        # --- Continue with other initializations ---
        self.constraints: List[Dict[str, str]] = []
        self.all_allowed_validation_vars = (  # This line should also come after definitions
            self.selected_parameters + self.node_voltage_expressions
        )
        self.function_button_pressed = False
        self.y_param_dropdown_selected = False

        # --- Header ---
        header_card = create_card(self, padding=None)
        header_card.pack(fill=tk.X, padx=32, pady=(24, 16))
        header_body = header_card.inner
        tk.Label(
            header_body,
            text="Optimization Settings",
            font=FONTS["title"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(anchor="w", padx=24, pady=(18, 4))
        tk.Label(
            header_body,
            text="Review your analysis configuration, adjust curve-fit goals, and manage constraints before running the optimization.",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_secondary"],
            wraplength=720,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=24, pady=(0, 18))

        # --- Scrollable Content Area ---
        content_wrapper = tk.Frame(self, bg=COLORS["bg_primary"])
        content_wrapper.pack(fill=tk.BOTH, expand=True, padx=32, pady=(0, 32))

        canvas = tk.Canvas(
            content_wrapper,
            borderwidth=0,
            highlightthickness=0,
            bg=COLORS["bg_primary"],
        )
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(content_wrapper, orient="vertical", command=canvas.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=vsb.set)

        scrollable_frame = ttk.Frame(canvas, style="TFrame")
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        scrollable_frame.bind("<Configure>", _on_frame_configure)
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfig(canvas_window, width=event.width),
        )

        def _on_mousewheel(event):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: scrollable_frame.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: scrollable_frame.unbind_all("<MouseWheel>"))
        main_frame = scrollable_frame

        # --- Optimization Type Dropdown ---
        optimization_type_frame = ttk.Frame(main_frame)
        optimization_type_frame.pack(side=tk.TOP, fill=tk.X)
        optimization_type_label = ttk.Label(
            optimization_type_frame, text="Optimization Type:"
        )
        optimization_type_label.pack(side=tk.LEFT, anchor=tk.W, pady=5)

        self.optimization_types = ["Curve Fit"]  # "Maximize/Minimize",
        self.optimization_type_var = tk.StringVar(value="Curve Fit")
        optimization_type_dropdown = ttk.Combobox(
            optimization_type_frame,
            textvariable=self.optimization_type_var,
            values=self.optimization_types,
            state="readonly",
        )
        optimization_type_dropdown.pack(side=tk.LEFT, anchor=tk.W, pady=5)
        optimization_type_dropdown.bind(
            "<<ComboboxSelected>>", self.on_optimization_type_change
        )

        analysis_type_frame = ttk.Frame(main_frame)
        analysis_type_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        ttk.Label(analysis_type_frame, text="Analysis Type:").pack(
            side=tk.LEFT, anchor=tk.W, pady=5
        )
        if self.analysis_type == "ac":
            initial_analysis_label = "AC"
        elif self.analysis_type == "noise":
            initial_analysis_label = "Noise"
        else:
            initial_analysis_label = "Transient"
        self.analysis_type_var = tk.StringVar(value=initial_analysis_label)
        analysis_type_dropdown = ttk.Combobox(
            analysis_type_frame,
            textvariable=self.analysis_type_var,
            values=["Transient", "AC", "Noise"],
            state="readonly",
            width=12,
        )
        analysis_type_dropdown.pack(side=tk.LEFT, anchor=tk.W, padx=(0, 10), pady=5)
        analysis_type_dropdown.bind("<<ComboboxSelected>>", self.on_analysis_type_change)

        self.ac_config_button = create_secondary_button(
            analysis_type_frame,
            text="Configure AC Sweep...",
            command=self.open_ac_settings,
        )
        self.ac_summary_var = tk.StringVar(value="")
        self.ac_details_frame = ttk.Frame(main_frame)
        self.ac_summary_label = ttk.Label(
            self.ac_details_frame, textvariable=self.ac_summary_var
        )
        self.ac_summary_label.pack(side=tk.LEFT, anchor=tk.W, padx=5)

        self.noise_config_button = create_secondary_button(
            analysis_type_frame,
            text="Configure Noise Sweep...",
            command=self.open_noise_settings,
        )
        self.noise_summary_var = tk.StringVar(value="")
        self.noise_details_frame = ttk.Frame(main_frame)
        self.noise_summary_label = ttk.Label(
            self.noise_details_frame, textvariable=self.noise_summary_var
        )
        self.noise_summary_label.pack(side=tk.LEFT, anchor=tk.W, padx=5)

        # Transient (.TRAN) configuration fields (shown only for Transient)
        self.tran_frame = create_card(main_frame)
        tran_inner = self.tran_frame.inner
        tran_inner.columnconfigure(1, weight=1)
        tk.Label(
            tran_inner,
            text="Transient (.TRAN) Settings",
            font=FONTS["subheading"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))
        # Stop time
        tk.Label(tran_inner, text="Stop time (s)", bg=COLORS["bg_secondary"], fg=COLORS["text_primary"]).grid(row=1, column=0, sticky=tk.W, pady=3)
        self.tstop_var = tk.StringVar(value="" if self.tran_settings["tstop"] is None else str(self.tran_settings["tstop"]))
        ttk.Entry(tran_inner, textvariable=self.tstop_var, width=18).grid(row=1, column=1, sticky=tk.W, pady=3)
        # Time step (optional)
        tk.Label(tran_inner, text="Time step (s)", bg=COLORS["bg_secondary"], fg=COLORS["text_primary"]).grid(row=2, column=0, sticky=tk.W, pady=3)
        self.tstep_var = tk.StringVar(value="" if self.tran_settings["tstep"] is None else str(self.tran_settings["tstep"]))
        ttk.Entry(tran_inner, textvariable=self.tstep_var, width=18).grid(row=2, column=1, sticky=tk.W, pady=3)
        # Start time (optional)
        tk.Label(tran_inner, text="Start time (s)", bg=COLORS["bg_secondary"], fg=COLORS["text_primary"]).grid(row=3, column=0, sticky=tk.W, pady=3)
        self.tstart_var = tk.StringVar(value="" if self.tran_settings["tstart"] is None else str(self.tran_settings["tstart"]))
        ttk.Entry(tran_inner, textvariable=self.tstart_var, width=18).grid(row=3, column=1, sticky=tk.W, pady=3)
        # Max step (optional)
        tk.Label(tran_inner, text="Max step (s)", bg=COLORS["bg_secondary"], fg=COLORS["text_primary"]).grid(row=4, column=0, sticky=tk.W, pady=3)
        self.tmax_var = tk.StringVar(value="" if self.tran_settings["max_step"] is None else str(self.tran_settings["max_step"]))
        ttk.Entry(tran_inner, textvariable=self.tmax_var, width=18).grid(row=4, column=1, sticky=tk.W, pady=3)
        # UIC toggle
        self.uic_var = tk.BooleanVar(value=self.tran_settings["uic"])
        ttk.Checkbutton(tran_inner, text="Use Initial Conditions (UIC)", variable=self.uic_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))

        # # --- Settings Panels (Curve Fit) ---
        setting_panel_frame = ttk.Frame(main_frame)
        # Pack this frame where the settings should appear
        setting_panel_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        # Instantiate CurveFitSettings, attaching it to the setting_panel_frame
        # Make sure to include the inputs_completed_callback from the main branch version
        self.curve_fit_settings = CurveFitSettings(
            setting_panel_frame,
            self.selected_parameters,
            self.nodes,
            controller,
            inputs_completed_callback=self.handle_curve_fit_conditions,  # Keep this callback
        )
        self.curve_fit_settings.set_analysis_context(
            self.analysis_type,
            self.ac_settings.get("response", "magnitude"),
            noise_settings=self.noise_settings,
        )
        # Pack the CurveFitSettings panel so it's visible
        self.curve_fit_settings.pack(fill=tk.X)
        self._update_ac_summary()
        self._update_noise_summary()
        self._update_analysis_ui()
        self.controller.update_app_data("analysis_type", self.analysis_type)
        self.controller.update_app_data("ac_settings", self.ac_settings)
        self.controller.update_app_data("noise_settings", self.noise_settings)

        # --- Constraints Table ---
        constraints_frame = ttk.Frame(main_frame)
        constraints_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        constraints_label = ttk.Label(constraints_frame, text="Constraints:")
        constraints_label.pack(
            side=tk.TOP, anchor=tk.W, pady=5
        )

        self.constraint_table = ConstraintTable(
            constraints_frame,
            self.open_add_constraint_window,  # Pass the *method* as callback
            self.remove_constraint,  # Pass remove_constraint
            self.open_edit_constraint_dialog,  # Pass edit constraint
        )
        setattr(self.controller, "constraint_table", self.constraint_table)
        self.constraint_table.pack(fill=tk.BOTH, expand=True)

        # --- Horizontal Button Container (Shared Frame) ---
        button_row_frame = ttk.Frame(constraints_frame)
        button_row_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        # --- Import/Export Buttons (Left-Aligned) ---
        import_export_frame = ttk.Frame(button_row_frame)
        import_export_frame.pack(side=tk.LEFT)

        import_button = create_secondary_button(
            import_export_frame,
            text="Import Constraints",
            command=self.import_constraints,
        )
        import_button.pack(side=tk.LEFT, padx=5)

        export_button = create_secondary_button(
            import_export_frame,
            text="Export Constraints",
            command=self.export_constraints,
        )
        export_button.pack(side=tk.LEFT, padx=5)

        # --- Add/Remove/Edit Buttons (Right-Aligned) ---
        self.button_frame = ttk.Frame(button_row_frame)
        self.button_frame.pack(side=tk.RIGHT)

        add_constraint_button = create_primary_button(
            self.button_frame,
            text="Add Constraint",
            command=self.open_add_constraint_window,  # type: ignore
        )
        add_constraint_button.pack(side=tk.LEFT, padx=2)

        remove_constraint_button = create_secondary_button(
            self.button_frame, text="Remove Constraint", command=self.remove_constraint
        )
        remove_constraint_button.pack(side=tk.LEFT, padx=2)

        edit_constraint_button = create_secondary_button(
            self.button_frame, text="Edit Constraint", command=self.edit_constraint
        )
        edit_constraint_button.pack(side=tk.LEFT, padx=2)

        # Frame for default bounds
        default_bounds_frame = ttk.Frame(main_frame)
        default_bounds_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        # Label for section
        default_bounds_label = ttk.Label(
            default_bounds_frame,
            text="Enable Default Bounds For Unspecified Component Bounds (1/10th minimum and 10x maximum of starting value):",
        )
        default_bounds_label.pack(side=tk.TOP, anchor=tk.W, pady=(5, 0))

        # Booleans for checkboxes
        self.enable_R_bounds = tk.BooleanVar(value=False)
        self.enable_L_bounds = tk.BooleanVar(value=False)
        self.enable_C_bounds = tk.BooleanVar(value=False)

        # Row of checkboxes (R, L, C)
        checkbox_row = ttk.Frame(default_bounds_frame)
        checkbox_row.pack(side=tk.TOP, anchor=tk.W, padx=10, pady=2)

        # R checkbox
        r_label = ttk.Label(checkbox_row, text="R:")
        r_label.pack(side=tk.LEFT)
        r_check = ttk.Checkbutton(checkbox_row, variable=self.enable_R_bounds)
        r_check.pack(side=tk.LEFT, padx=(0, 10))

        # L checkbox
        l_label = ttk.Label(checkbox_row, text="L:")
        l_label.pack(side=tk.LEFT)
        l_check = ttk.Checkbutton(checkbox_row, variable=self.enable_L_bounds)
        l_check.pack(side=tk.LEFT, padx=(0, 10))

        # C checkbox
        c_label = ttk.Label(checkbox_row, text="C:")
        c_label.pack(side=tk.LEFT)
        c_check = ttk.Checkbutton(checkbox_row, variable=self.enable_C_bounds)
        c_check.pack(side=tk.LEFT)

        # Optimization Tolerance and default bound Section

        tolerances_frame = ttk.Frame(main_frame)
        tolerances_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        tolerances_label = ttk.Label(tolerances_frame, text="Optimization Tolerances:")
        tolerances_label.pack(side=tk.TOP, anchor="w", pady=5)

        # Row of labeled entries
        entries_row = ttk.Frame(tolerances_frame)
        entries_row.pack(side=tk.TOP, anchor="w")

        # xtol
        xtol_label = ttk.Label(entries_row, text="xtol:")
        xtol_label.pack(side=tk.LEFT, padx=(0, 5))
        self.xtol_var = tk.StringVar(value="1e-12")
        self.xtol_entry = ttk.Entry(entries_row, width=10, textvariable=self.xtol_var)
        self.xtol_entry.pack(side=tk.LEFT, padx=(0, 15))
        self.xtol_entry.bind("<FocusOut>", lambda e: self.validate_float("xtol_var"))

        # gtol
        gtol_label = ttk.Label(entries_row, text="gtol:")
        gtol_label.pack(side=tk.LEFT, padx=(0, 5))
        self.gtol_var = tk.StringVar(value="1e-12")
        self.gtol_entry = ttk.Entry(entries_row, width=10, textvariable=self.gtol_var)
        self.gtol_entry.pack(side=tk.LEFT, padx=(0, 15))
        self.gtol_entry.bind("<FocusOut>", lambda e: self.validate_float("gtol_var"))

        # ftol
        ftol_label = ttk.Label(entries_row, text="ftol:")
        ftol_label.pack(side=tk.LEFT, padx=(0, 5))
        self.ftol_var = tk.StringVar(value="1e-12")
        self.ftol_entry = ttk.Entry(entries_row, width=10, textvariable=self.ftol_var)
        self.ftol_entry.pack(side=tk.LEFT)
        self.ftol_entry.bind("<FocusOut>", lambda e: self.validate_float("ftol_var"))

        # --- Navigation Buttons ---
        navigation_frame = tk.Frame(main_frame, bg=COLORS["bg_primary"])
        navigation_frame.pack(side=tk.TOP, fill=tk.X, pady=10)

        create_secondary_button(
            navigation_frame, text="Back", command=self.go_back
        ).pack(side=tk.LEFT, padx=5)
        self.continue_button = create_primary_button(
            navigation_frame,
            text="Begin Optimization",
            command=self.go_forward,
            state=tk.DISABLED,
        )
        self.continue_button.pack(side=tk.RIGHT, padx=5)

    def handle_curve_fit_conditions(self, condition_type, state):
        """Update flags based on inputs from CurveFitSettings."""
        if condition_type == "function_button_pressed":
            self.function_button_pressed = state
        elif condition_type == "y_param_dropdown_selected":
            self.y_param_dropdown_selected = state
        elif condition_type == "ac_response_changed":
            self.ac_settings["response"] = state
            self.controller.update_app_data("ac_settings", self.ac_settings)
            self._update_ac_summary()
        elif condition_type == "noise_output_node":
            self.noise_settings["output_node"] = state or ""
            self.controller.update_app_data("noise_settings", self.noise_settings)
            self._update_noise_summary()

        # Check if all conditions are met
        self.update_continue_button_state()

    def update_continue_button_state(self):
        """Enable the 'Begin Optimization' button if all conditions are met."""
        if self.function_button_pressed and self.y_param_dropdown_selected:
            self.continue_button.config(state=tk.NORMAL)
        else:
            self.continue_button.config(state=tk.DISABLED)

    def _update_ac_summary(self) -> None:
        if not self.ac_settings:
            self.ac_summary_var.set("")
            return
        response = self.ac_settings.get("response", "magnitude").lower()
        response_label = {
            "magnitude": "Magnitude",
            "magnitude_db": "Magnitude (dB)",
            "phase": "Phase",
            "real": "Real",
            "imag": "Imag",
        }.get(response, response.capitalize())
        summary = (
            f"{self.ac_settings['sweep_type']} sweep, "
            f"{self.ac_settings['points']} points, "
            f"{self.ac_settings['start_frequency']:.3g} -> "
            f"{self.ac_settings['stop_frequency']:.3g} Hz, "
            f"{response_label}"
        )
        self.ac_summary_var.set(summary)

    def _update_noise_summary(self) -> None:
        if not self.noise_settings or self.analysis_type != "noise":
            self.noise_summary_var.set("")
            return
        quantity_map = {
            "onoise": "Output noise (V/√Hz)",
            "onoise_db": "Output noise (dB/√Hz)",
            "inoise": "Input-referred noise (V/√Hz)",
            "inoise_db": "Input-referred noise (dB/√Hz)",
        }
        quantity = self.noise_settings.get("quantity", "onoise").lower()
        quantity_label = quantity_map.get(quantity, quantity_map["onoise"])
        summary = (
            f"{self.noise_settings['sweep_type']} sweep, "
            f"{self.noise_settings['points']} points, "
            f"{self.noise_settings['start_frequency']:.3g} -> "
            f"{self.noise_settings['stop_frequency']:.3g} Hz, "
            f"{quantity_label}"
        )
        node = self.noise_settings.get("output_node")
        source = self.noise_settings.get("input_source")
        if node or source:
            summary += f" (node {node or '?'} vs source {source or '?'})"
        self.noise_summary_var.set(summary)

    def _update_analysis_ui(self) -> None:
        if self.analysis_type == "ac":
            if not self.ac_config_button.winfo_ismapped():
                self.ac_config_button.pack(side=tk.LEFT, pady=5)
            if not self.ac_details_frame.winfo_ismapped():
                self.ac_details_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))
            if self.noise_config_button.winfo_ismapped():
                self.noise_config_button.pack_forget()
            if self.noise_details_frame.winfo_ismapped():
                self.noise_details_frame.pack_forget()
            if self.tran_frame.winfo_ismapped():
                self.tran_frame.pack_forget()
        elif self.analysis_type == "noise":
            if self.ac_config_button.winfo_ismapped():
                self.ac_config_button.pack_forget()
            if self.ac_details_frame.winfo_ismapped():
                self.ac_details_frame.pack_forget()
            if not self.noise_config_button.winfo_ismapped():
                self.noise_config_button.pack(side=tk.LEFT, pady=5)
            if not self.noise_details_frame.winfo_ismapped():
                self.noise_details_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))
            if self.tran_frame.winfo_ismapped():
                self.tran_frame.pack_forget()
        else:
            if self.ac_config_button.winfo_ismapped():
                self.ac_config_button.pack_forget()
            if self.ac_details_frame.winfo_ismapped():
                self.ac_details_frame.pack_forget()
            if self.noise_config_button.winfo_ismapped():
                self.noise_config_button.pack_forget()
            if self.noise_details_frame.winfo_ismapped():
                self.noise_details_frame.pack_forget()
            if not self.tran_frame.winfo_ismapped():
                self.tran_frame.pack(fill=tk.X, padx=32, pady=(0, 8))

    def open_ac_settings(self):
        dialog = AcSettingsDialog(self, self.ac_settings)
        self.wait_window(dialog)
        if dialog.result:
            self.ac_settings = dialog.result
            self.controller.update_app_data("ac_settings", self.ac_settings)
            self._update_ac_summary()
            self._update_analysis_ui()
            self.curve_fit_settings.set_analysis_context(
                self.analysis_type,
                self.ac_settings.get("response", "magnitude"),
                noise_settings=self.noise_settings,
            )

    def open_noise_settings(self):
        dialog = NoiseSettingsDialog(
            self,
            sorted(self.nodes),
            self.source_names,
            self.noise_settings,
        )
        self.wait_window(dialog)
        if dialog.result:
            self.noise_settings.update(dialog.result)
            self.controller.update_app_data("noise_settings", self.noise_settings)
            self._update_noise_summary()
            self._update_analysis_ui()
            self.curve_fit_settings.set_analysis_context(
                self.analysis_type,
                self.ac_settings.get("response", "magnitude"),
                noise_settings=self.noise_settings,
            )

    def on_optimization_type_change(self, event=None):
        selected_type = self.optimization_type_var.get()

    def on_analysis_type_change(self, event=None):
        selection = (self.analysis_type_var.get() or "Transient").strip().lower()
        if selection == "ac":
            self.analysis_type = "ac"
        elif selection == "noise":
            self.analysis_type = "noise"
        else:
            self.analysis_type = "transient"
        self.controller.update_app_data("analysis_type", self.analysis_type)
        self.controller.update_app_data("ac_settings", self.ac_settings)
        self.controller.update_app_data("noise_settings", self.noise_settings)
        self.curve_fit_settings.set_analysis_context(
            self.analysis_type,
            self.ac_settings.get("response", "magnitude"),
            noise_settings=self.noise_settings,
        )
        self._update_analysis_ui()

    def open_add_constraint_window(self):
        dialog = AddConstraintDialog(
            self,
            self.selected_parameters,
            self.node_voltage_expressions,
            self.allowed_constraint_left_sides,
        )
        self.wait_window(dialog)
        if dialog.constraint:
            self.add_constraint(dialog.constraint)

    def _determine_constraint_type(self, left_expression: str) -> Optional[str]:
        """Determines if the left side is a parameter or node expression."""
        if left_expression in (self.selected_parameters or []):
            return "parameter"
        elif (
            left_expression in self.node_voltage_expressions
        ):  # Add checks for other node types if needed
            return "node"
        else:
            # Could potentially be a more complex expression, but we're simplifying
            # Check if it's *only* a known parameter or node expression
            # You might need more robust parsing if left side can be complex later
            is_valid_expr, used_vars = ExpressionEvaluator(
                self.all_allowed_validation_vars
            ).validate_expression(left_expression)
            if is_valid_expr and len(used_vars) == 1:
                if used_vars[0] in (self.selected_parameters or []):
                    return "parameter"
                if used_vars[0] in self.node_voltage_expressions:
                    return "node"
            return None  # Indicates an invalid or unsupported left-hand side format

    def add_constraint(self, constraint_data: Dict[str, str]):
        """Adds the constraint type and stores it."""
        left_side = constraint_data.get("left", "")
        constraint_type = self._determine_constraint_type(left_side)

        if constraint_type is None:
            messagebox.showerror(
                "Error Adding Constraint",
                f"Invalid left-hand side expression: '{left_side}'. Must be a single selected parameter or node expression (e.g., V(node)).",
            )
            return

        # Add the type to the dictionary
        constraint_data["type"] = constraint_type

        self.constraints.append(constraint_data)  # Store the constraint with its type
        print(f"Added Constraint: {constraint_data}")  # Debug
        # Modify constraint_table.add_constraint to accept and potentially display the type
        self.constraint_table.add_constraint(constraint_data)

    def open_edit_constraint_dialog(self, constraint: Dict[str, str], index: int):
        dialog = EditConstraintDialog(
            self,
            self.selected_parameters,
            self.node_voltage_expressions,
            constraint,
            self.allowed_constraint_left_sides,
            preview_callback=getattr(self.controller, "constraint_preview", None),
        )
        self.wait_window(dialog)  # Wait for dialog to close
        if dialog.constraint is not None:
            new_constraint = (
                dialog.constraint
            )  # Assume EditDialog updated its self.constraint
            constraint_type = self._determine_constraint_type(new_constraint["left"])
            if constraint_type is None:
                messagebox.showerror(
                    "Error", f"Invalid left-hand side: {new_constraint['left']}"
                )
                return
            new_constraint["type"] = constraint_type  # Add/Update type
            self.constraints[index] = new_constraint
            self.constraint_table.update_constraint(
                index, new_constraint
            )  # Update table (needs type support)

    def remove_constraint(self):
        # get selected from treeview and index
        selected_items = self.constraint_table.selection()
        if not selected_items:
            messagebox.showinfo("Info", "Please select a constraint to remove.")
            return
        # loop in reverse to prevent index issues
        for selected in reversed(selected_items):
            index = self.constraint_table.index(selected)
            self.constraint_table.delete(selected)
            del self.constraints[index]

    def edit_constraint(self):
        """Opens the EditConstraintDialog for the selected constraint."""
        selected_items = self.constraint_table.selection()
        if not selected_items:
            messagebox.showinfo("Info", "Please select a constraint to edit.")
            return
        if len(selected_items) > 1:
            messagebox.showinfo("Info", "Please select only one constraint to edit.")
            return

        selected_item = selected_items[0]
        index = self.constraint_table.index(selected_item)
        #  CRUCIAL: We need to get the constraint data *from the Treeview*,
        #   NOT from the potentially outdated self.controller.constraints.
        values = self.constraint_table.item(selected_item, "values")
        constraint = {"left": values[0], "operator": values[1], "right": values[2]}
        self.open_edit_constraint_dialog(constraint, index)  # Call the edit callback

    def go_back(self):
        self.controller.navigate("parameter_selection")

    def _collect_tran_settings(self) -> Optional[Dict[str, Optional[float]]]:
        if self.analysis_type != "transient":
            return None

        def _parse_optional(var: tk.StringVar, label: str) -> (Optional[float], Optional[str]):
            raw = (var.get() or "").strip()
            if raw == "":
                return None, None
            try:
                return float(raw), None
            except ValueError:
                return None, label

        invalid_fields = []
        tstop, tstop_err = _parse_optional(self.tstop_var, "Stop time")
        if tstop is None:
            # Stop time is required; empty or invalid aborts
            if tstop_err is not None:
                invalid_fields.append("Stop time")
            else:
                messagebox.showerror("Stop Time Required", "Please provide a stop time for transient analysis.")
                return None

        tstep, tstep_err = _parse_optional(self.tstep_var, "Time step")
        tstart, tstart_err = _parse_optional(self.tstart_var, "Start time")
        tmax, tmax_err = _parse_optional(self.tmax_var, "Max step")
        for label, err in [("Time step", tstep_err), ("Start time", tstart_err), ("Max step", tmax_err)]:
            if err is not None:
                invalid_fields.append(label)
        if invalid_fields:
            messagebox.showerror(
                "Invalid Input",
                "Please enter a numeric value for: " + ", ".join(invalid_fields)
            )
            return None
        return {
            "tstop": tstop,
            "tstep": tstep,
            "tstart": tstart,
            "max_step": tmax,
            "uic": bool(self.uic_var.get()),
        }

    def go_forward(self):
        # --- Get all constraints (they now include the 'type' key) ---
        all_constraints = (
            self.constraints
        )  # List of dicts like {'left': 'R1', ..., 'type': 'parameter'}
        generated_data = self.controller.get_app_data("generated_data") or []

        # --- Separate constraints by type ---
        parameter_constraints = [
            c for c in all_constraints if c.get("type") == "parameter"
        ]
        node_constraints_from_ui = [
            c for c in all_constraints if c.get("type") == "node"
        ]
        untyped_constraints = [
            c for c in all_constraints if c.get("type") not in ["parameter", "node"]
        ]

        print(f"Found {len(parameter_constraints)} parameter constraints:")
        # for pc in parameter_constraints: print(f"  {pc}")
        print(f"Found {len(node_constraints_from_ui)} node constraints:")
        # for nc in node_constraints_from_ui: print(f"  {nc}")
        if untyped_constraints:
            print(
                f"Warning: Found {len(untyped_constraints)} constraints without a valid type."
            )
        optimization_settings = {
            "optimization_type": self.optimization_type_var.get(),
            "constraints": self.constraints,
        }
        if not generated_data:
            messagebox.showerror(
                "Target Required",
                "Please define or import a target curve before starting the optimization.",
            )
            return
        curve_settings = self.curve_fit_settings.get_settings()
        noise_output_node = curve_settings.pop("noise_output_node", None)
        noise_quantity = curve_settings.get("noise_quantity")
        ac_response = curve_settings.get("ac_response")
        optimization_settings.update(curve_settings)
        optimization_settings["analysis_type"] = self.analysis_type
        if self.analysis_type == "ac":
            if ac_response:
                self.ac_settings["response"] = ac_response
            optimization_settings["ac_settings"] = dict(self.ac_settings)
            optimization_settings["noise_settings"] = {}
            optimization_settings["tran_settings"] = {}
        elif self.analysis_type == "noise":
            if noise_output_node:
                self.noise_settings["output_node"] = noise_output_node
            if noise_quantity:
                self.noise_settings["quantity"] = noise_quantity
            if not self.noise_settings.get("output_node"):
                messagebox.showerror(
                    "Noise Output Required",
                    "Select the node where noise will be measured before running optimization.",
                )
                return
            if not self.noise_settings.get("input_source"):
                messagebox.showerror(
                    "Noise Source Required",
                    "Configure the noise analysis to choose a driving source.",
                )
                return
            optimization_settings["ac_settings"] = {}
            optimization_settings["noise_settings"] = dict(self.noise_settings)
        else:
            tran_settings = self._collect_tran_settings()
            if tran_settings is None:
                return
            optimization_settings["ac_settings"] = {}
            optimization_settings["noise_settings"] = {}
            optimization_settings["tran_settings"] = tran_settings

        print("AC settings before run:", optimization_settings.get("ac_settings"))

        self.controller.update_app_data("analysis_type", self.analysis_type)
        self.controller.update_app_data("ac_settings", self.ac_settings)
        self.controller.update_app_data("noise_settings", self.noise_settings)
        self.controller.update_app_data("tran_settings", optimization_settings.get("tran_settings", {}))

        self.controller.update_app_data("optimization_settings", optimization_settings)
        self.controller.update_app_data(
            "optimization_tolerances",
            [
                float(self.xtol_var.get()),
                float(self.gtol_var.get()),
                float(self.ftol_var.get()),
            ],
        )
        self.controller.update_app_data(
            "RLC_bounds",
            [
                self.enable_R_bounds.get(),
                self.enable_L_bounds.get(),
                self.enable_C_bounds.get(),
            ],
        )
        # Reset results so the next summary view starts a fresh optimization run
        self.controller.update_app_data("optimization_results", None)
        self.controller.navigate("optimization_summary")

    def import_constraints(self):
        """Imports constraints from a JSON file."""
        constraints = import_constraints_from_file()
        if constraints is not None:
            # Clear existing constraints
            self.constraints = []
            self.constraint_table.clear()

            # Add the imported constraints
            for constraint in constraints:
                self.add_constraint(constraint)
            messagebox.showinfo("Info", "Constraints imported successfully.")

    def export_constraints(self):
        """Exports constraints to a JSON file."""
        if not self.constraints:
            messagebox.showwarning("Warning", "No constraints to export.")
            return
        export_constraints_to_file(self.constraints)
