import tkinter as tk

from tkinter import ttk, messagebox
from typing import List, Dict, Any, Optional
from .add_constraint_dialog import AddConstraintDialog
from .edit_constraint_dialog import EditConstraintDialog
from .constraint_table import ConstraintTable
from .curve_fit_settings import CurveFitSettings
from .ac_settings_dialog import AcSettingsDialog
from ..utils import import_constraints_from_file, export_constraints_to_file


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
        super().__init__(parent)
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
        self.analysis_type = "ac" if stored_analysis_type == "ac" else "transient"
        self.ac_settings = {
            "sweep_type": str(stored_ac_settings.get("sweep_type", "DEC")).upper(),
            "points": _as_int(stored_ac_settings.get("points"), 10),
            "start_frequency": _as_float(stored_ac_settings.get("start_frequency"), 1.0),
            "stop_frequency": _as_float(stored_ac_settings.get("stop_frequency"), 1_000_000.0),
            "response": str(stored_ac_settings.get("response", "magnitude")).lower(),
        }

        # --- Now build the lists ---
        self.node_voltage_expressions = [
            f"V({node})" for node in self.nodes if node != "0"
        ]

        # --- NOW it's safe to create the combined list ---
        self.allowed_constraint_left_sides: List[str] = (
            self.selected_parameters + self.node_voltage_expressions
        )
        self.allowed_constraint_left_sides.sort()

        # --- Continue with other initializations ---
        self.constraints: List[Dict[str, str]] = []
        self.all_allowed_validation_vars = (  # This line should also come after definitions
            self.selected_parameters + self.node_voltage_expressions
        )
        self.function_button_pressed = False
        self.y_param_dropdown_selected = False

        # --- Scrollable Canvas Setup ---
        canvas = tk.Canvas(self, borderwidth=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add vertical scrollbar
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=vsb.set)

        # Create a frame inside the canvas
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Add the scrollable frame to the canvas window
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def resize_scrollable_frame(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind("<Configure>", resize_scrollable_frame)

        def _on_mousewheel(event):
             if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # For Windows and macOS
        canvas.bind("<Enter>", lambda e: scrollable_frame.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: scrollable_frame.unbind_all("<MouseWheel>"))
        # Now use scrollable_frame instead of main_frame
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
        initial_analysis_label = "AC" if self.analysis_type == "ac" else "Transient"
        self.analysis_type_var = tk.StringVar(value=initial_analysis_label)
        analysis_type_dropdown = ttk.Combobox(
            analysis_type_frame,
            textvariable=self.analysis_type_var,
            values=["Transient", "AC"],
            state="readonly",
            width=12,
        )
        analysis_type_dropdown.pack(side=tk.LEFT, anchor=tk.W, padx=(0, 10), pady=5)
        analysis_type_dropdown.bind("<<ComboboxSelected>>", self.on_analysis_type_change)

        self.ac_config_button = ttk.Button(
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
            self.analysis_type, self.ac_settings.get("response", "magnitude")
        )
        # Pack the CurveFitSettings panel so it's visible
        self.curve_fit_settings.pack(fill=tk.X)
        self._update_ac_summary()
        self._update_analysis_ui()
        self.controller.update_app_data("analysis_type", self.analysis_type)
        self.controller.update_app_data("ac_settings", self.ac_settings)

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

        import_button = ttk.Button(
            import_export_frame,
            text="Import Constraints",
            command=self.import_constraints,
        )
        import_button.pack(side=tk.LEFT, padx=5)

        export_button = ttk.Button(
            import_export_frame,
            text="Export Constraints",
            command=self.export_constraints,
        )
        export_button.pack(side=tk.LEFT, padx=5)

        # --- Add/Remove/Edit Buttons (Right-Aligned) ---
        self.button_frame = ttk.Frame(button_row_frame)
        self.button_frame.pack(side=tk.RIGHT)

        add_constraint_button = ttk.Button(
            self.button_frame,
            text="Add Constraint",
            command=self.open_add_constraint_window,  # type: ignore
        )
        add_constraint_button.pack(side=tk.LEFT, padx=2)

        remove_constraint_button = ttk.Button(
            self.button_frame, text="Remove Constraint", command=self.remove_constraint
        )
        remove_constraint_button.pack(side=tk.LEFT, padx=2)

        edit_constraint_button = ttk.Button(
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
        navigation_frame = ttk.Frame(main_frame)
        navigation_frame.pack(side=tk.TOP, fill=tk.X, pady=10)

        back_button = ttk.Button(navigation_frame, text="Back", command=self.go_back)
        back_button.pack(side=tk.LEFT, padx=5)
        self.continue_button = ttk.Button(
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

    def _update_analysis_ui(self) -> None:
        is_ac = self.analysis_type == "ac"
        if is_ac:
            if not self.ac_config_button.winfo_ismapped():
                self.ac_config_button.pack(side=tk.LEFT, pady=5)
            if not self.ac_details_frame.winfo_ismapped():
                self.ac_details_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))
        else:
            if self.ac_config_button.winfo_ismapped():
                self.ac_config_button.pack_forget()
            if self.ac_details_frame.winfo_ismapped():
                self.ac_details_frame.pack_forget()

    def open_ac_settings(self):
        dialog = AcSettingsDialog(self, self.ac_settings)
        self.wait_window(dialog)
        if dialog.result:
            self.ac_settings = dialog.result
            self.controller.update_app_data("ac_settings", self.ac_settings)
            self._update_ac_summary()
            self._update_analysis_ui()
            self.curve_fit_settings.set_analysis_context(
                self.analysis_type, self.ac_settings.get("response", "magnitude")
            )

    def on_optimization_type_change(self, event=None):
        selected_type = self.optimization_type_var.get()

    def on_analysis_type_change(self, event=None):
        selection = (self.analysis_type_var.get() or "Transient").strip().lower()
        self.analysis_type = "ac" if selection == "ac" else "transient"
        self.controller.update_app_data("analysis_type", self.analysis_type)
        self.controller.update_app_data("ac_settings", self.ac_settings)
        self.curve_fit_settings.set_analysis_context(
            self.analysis_type, self.ac_settings.get("response", "magnitude")
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

    def go_forward(self):
        # --- Get all constraints (they now include the 'type' key) ---
        all_constraints = (
            self.constraints
        )  # List of dicts like {'left': 'R1', ..., 'type': 'parameter'}

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
        curve_settings = self.curve_fit_settings.get_settings()
        ac_response = curve_settings.get("ac_response")
        optimization_settings.update(curve_settings)
        optimization_settings["analysis_type"] = self.analysis_type
        if self.analysis_type == "ac":
            if ac_response:
                self.ac_settings["response"] = ac_response
            optimization_settings["ac_settings"] = dict(self.ac_settings)
        else:
            optimization_settings["ac_settings"] = {}

        print("AC settings before run:", optimization_settings.get("ac_settings"))

        self.controller.update_app_data("analysis_type", self.analysis_type)
        self.controller.update_app_data("ac_settings", self.ac_settings)

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
