
# Visual curve editors (Matplotlib embedded in Tkinter)
from .visual_curve_editors import open_line_editor, open_heaviside_editor

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Any, Optional
import numpy as np
import csv
import re
from enum import Enum


class input_type(Enum):
    LINE = 1
    HEAVISIDE = 2
    UPLOAD = 3

class CurveFitSettings(tk.Frame):
    def __init__(self, parent: tk.Frame, parameters: List[str], nodes, controller: "AppController", inputs_completed_callback=None):
        super().__init__(parent)
        self.controller = controller
        self.inputs_completed_callback = inputs_completed_callback
        self.parameters = parameters
        self.nodes = nodes
        self.x_parameter_expression_var = tk.StringVar()
        self.y_parameter_expression_var = tk.StringVar()
        self.frames = {}
        self.generated_data = None
        self.inputs_completed = False
        self.time_tuples_list = []

        # --- combobox for: line input vs heavyside vs custom csv
        self.select_input_type_frame = ttk.Frame(self)
        self.select_input_type_frame.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(self.select_input_type_frame, text="Target Function Type: ").pack(side=tk.LEFT)
        answer = tk.StringVar()
        self.input_type_options = ttk.Combobox(self.select_input_type_frame, textvariable=answer)
        self.input_type_options['values'] = ('Line','Heaviside','Upload')
        self.input_type_options.pack(side=tk.LEFT)
        if self.input_type_options['values']:
            self.input_type_options.current(0)
        self.input_type_options.bind("<<ComboboxSelected>>", lambda event: self.show_frame())

        self.frames['Line'] = self.create_line_frame()
        self.frames['Heaviside'] = self.create_heaviside_frame()
        self.frames['Upload'] = self.create_upload_frame()

        for frame in self.frames.values():
            frame.pack_forget()

        # --- Target functions list + actions ---
        self.see_inputted_functions = ttk.Frame(self)
        self.see_inputted_functions.pack(pady=5, side=tk.TOP, expand=False, fill=tk.X)

        self.func_list = ttk.Treeview(self.see_inputted_functions, columns=("type","desc","range"), show="headings", height=4)
        self.func_list.heading("type", text="Type")
        self.func_list.heading("desc", text="Description")
        self.func_list.heading("range", text="x-range")
        self.func_list.column("type", width=90, anchor="w")
        self.func_list.column("desc", width=480, anchor="w")
        self.func_list.column("range", width=160, anchor="center")
        self.func_list.pack(side=tk.LEFT, padx=6, pady=4, fill=tk.X, expand=True)

        btns = ttk.Frame(self.see_inputted_functions)
        btns.pack(side=tk.LEFT, padx=8, pady=4)
        ttk.Button(btns, text="Edit Selected", command=self.edit_selected_function).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text="Delete Selected", command=self.delete_selected_function).pack(fill=tk.X, pady=2)

        self.func_model = []  # list of {"type": "...", "params": (...)}
        self.analysis_type = "transient"
        self.ac_response = "magnitude"
        self.ac_response_options = {
            "magnitude": "Magnitude",
            "magnitude_db": "Magnitude (dB)",
            "phase": "Phase",
        }

        # --- X and Y Parameter Dropdowns and Expressions ---
        self.x_parameter_var = tk.StringVar(value="TIME")
        self.x_param_label = ttk.Label(self, text="X Parameter: TIME")
        self.x_param_label.pack(side=tk.LEFT)

        self.y_parameter_var = tk.StringVar()
        self.y_param_label = ttk.Label(self, text="Y Parameter:")
        self.y_param_label.pack(side=tk.LEFT)

        y_param_frame = ttk.Frame(self)
        y_param_frame.pack(side=tk.LEFT)
        self.y_parameter_dropdown = ttk.Combobox(
            y_param_frame,
            textvariable=self.y_parameter_var,
            values=[f"V({node})" for node in self.nodes],  # Use node voltages
            state="readonly",
        )
        self.y_parameter_dropdown.pack(side=tk.LEFT, padx=5)
        self.y_parameter_dropdown.bind("<<ComboboxSelected>>", self.on_y_parameter_selected)

        self.ac_response_var = tk.StringVar(value=self.ac_response_options[self.ac_response])
        self.ac_response_frame = ttk.Frame(self)
        self.ac_response_label = ttk.Label(self.ac_response_frame, text="AC Response:")
        self.ac_response_label.pack(side=tk.LEFT, padx=(10, 0))
        self.ac_response_dropdown = ttk.Combobox(
            self.ac_response_frame,
            textvariable=self.ac_response_var,
            values=list(self.ac_response_options.values()),
            state="readonly",
            width=18,
        )
        self.ac_response_dropdown.pack(side=tk.LEFT, padx=5)
        self.ac_response_dropdown.bind("<<ComboboxSelected>>", self.on_ac_response_selected)
        self.ac_response_frame.pack(side=tk.LEFT)
        self.ac_response_frame.pack_forget()
    
    def custom_x_inputs_are_valid(self, x_start, x_end) -> bool:
        if self.analysis_type == "ac":
            if x_start <= 0:
                messagebox.showerror("Input Error", "The starting frequency must be greater than 0.")
                return False
            if x_end <= 0:
                messagebox.showerror("Input Error", "The ending frequency must be greater than 0.")
                return False
        else:
            if x_start < 0:
                messagebox.showerror("Input Error", "The starting x value may NOT be less than 0.")
                return False
            if x_end < 0:
                messagebox.showerror("Input Error", "The ending x value may NOT be less than 0.")
                return False
        if x_start >= x_end:
            messagebox.showerror("Input Error", "The starting value must be less than the ending value.")
            return False
        return True

    def is_intersecting(self, tuple1, tuple2) -> bool:
        # Check if two intervals intersect
        start1, end1 = tuple1 
        start2, end2 = tuple2 
        return start1 <= end2 and start2 <= end1

    def check_if_in_previous_x_ranges(self, time_tuple) -> bool:
        # Iterate through each tuple in the list and check for intersection
        for existing_tuple in self.time_tuples_list:
            if self.is_intersecting(existing_tuple, time_tuple):
                messagebox.showerror("Input Error", "The time range you entered overlaps with a previously defined range. Please enter a non-overlapping time range.")
                return True # Return True if an intersection is found
        return False # Return False if no intersections are found
        
    def create_line_frame(self):
        line_frame = tk.Frame(self.select_input_type_frame)
        line_frame.pack()
        tk.Label(line_frame, text="Slope = ").pack(side=tk.LEFT) 
        line_slope = tk.Entry(line_frame, width=5); line_slope.pack(side=tk.LEFT)
        tk.Label(line_frame, text=", Y-intercept = ").pack(side=tk.LEFT) 
        line_intercept = tk.Entry(line_frame, width=5); line_intercept.pack(side=tk.LEFT)
        tk.Label(line_frame, text=", From x = ").pack(side=tk.LEFT)
        line_start_x = tk.Entry(line_frame, width=5); line_start_x.pack(side=tk.LEFT)
        tk.Label(line_frame, text="to x = ").pack(side=tk.LEFT)
        line_end_x = tk.Entry(line_frame, width=5); line_end_x.pack(side=tk.LEFT)        
        self.line_button = ttk.Button(line_frame, text="Add Line",
            command=lambda: self.add_function(input_type.LINE, line_slope, line_intercept, line_start_x, line_end_x))
        self.line_button.pack(side=tk.LEFT, padx=10)

        ttk.Button(line_frame, text="Open Visual Editor",
            command=lambda: open_line_editor(
                self,
                float(line_slope.get() or 1.0),
                float(line_intercept.get() or 0.0),
                float(line_start_x.get() or 0.0),
                float(line_end_x.get() or 1.0),
                on_change=lambda m,b,x0,x1: (
                    line_slope.delete(0, tk.END), line_slope.insert(0, str(m)),
                    line_intercept.delete(0, tk.END), line_intercept.insert(0, str(b)),
                    line_start_x.delete(0, tk.END), line_start_x.insert(0, str(x0)),
                    line_end_x.delete(0, tk.END),   line_end_x.insert(0,   str(x1))
                ),
                on_apply=lambda m,b,x0,x1: self._add_line_from_visual_editor(m, b, x0, x1)
            )
        ).pack(side=tk.LEFT, padx=6)

        self.custom_functions = []
        return line_frame

    def _add_line_from_visual_editor(self, slope, y_int, x_start, x_end):
        """Helper method to add a line function from visual editor parameters"""
        # Create mock entry objects that return the values
        class MockEntry:
            def __init__(self, value):
                self.value = str(value)
            def get(self):
                return self.value
        
        slope_entry = MockEntry(slope)
        y_int_entry = MockEntry(y_int)
        x_start_entry = MockEntry(x_start)
        x_end_entry = MockEntry(x_end)
        
        # Call the existing add_function method
        self.add_function(input_type.LINE, slope_entry, y_int_entry, x_start_entry, x_end_entry)

    def _add_heaviside_from_visual_editor(self, amplitude, t0, x1):
        """Helper method to add a heaviside function from visual editor parameters"""
        # Create mock entry objects that return the values
        class MockEntry:
            def __init__(self, value):
                self.value = str(value)
            def get(self):
                return self.value
        
        amplitude_entry = MockEntry(amplitude)
        t0_entry = MockEntry(t0)
        x1_entry = MockEntry(x1)
        
        # Call the existing add_function method
        self.add_function(input_type.HEAVISIDE, amplitude_entry, t0_entry, x1_entry, "")

    def create_heaviside_frame(self):
        heaviside_frame = tk.Frame(self.select_input_type_frame)
        heaviside_frame.pack()
        tk.Label(heaviside_frame, text="Amplitude = ").pack(side=tk.LEFT) 
        heaviside_amplitude = tk.Entry(heaviside_frame, width=5); heaviside_amplitude.pack(side=tk.LEFT)
        tk.Label(heaviside_frame, text=", From x = ").pack(side=tk.LEFT)
        heaviside_start_x = tk.Entry(heaviside_frame, width=5); heaviside_start_x.pack(side=tk.LEFT)
        tk.Label(heaviside_frame, text="to x = ").pack(side=tk.LEFT)
        heaviside_end_x = tk.Entry(heaviside_frame, width=5); heaviside_end_x.pack(side=tk.LEFT)

        self.heaviside_button = ttk.Button(heaviside_frame, text="Add Heaviside",
            command=lambda: self.add_function(input_type.HEAVISIDE, heaviside_amplitude, heaviside_start_x, heaviside_end_x,""))
        self.heaviside_button.pack(side=tk.LEFT, padx=10)

        ttk.Button(heaviside_frame, text="Open Visual Editor",
            command=lambda: open_heaviside_editor(
                self,
                float(heaviside_amplitude.get() or 1.0),
                float(heaviside_start_x.get() or 0.0),
                float(heaviside_end_x.get() or 1.0),
                on_change=lambda a,t0,x1: (
                    heaviside_amplitude.delete(0, tk.END), heaviside_amplitude.insert(0, str(a)),
                    heaviside_start_x.delete(0, tk.END),   heaviside_start_x.insert(0, str(t0)),
                    heaviside_end_x.delete(0, tk.END),     heaviside_end_x.insert(0,   str(x1))
                ),
                on_apply=lambda a,t0,x1: self._add_heaviside_from_visual_editor(a, t0, x1)
            )
        ).pack(side=tk.LEFT, padx=6)

        return heaviside_frame

    def create_upload_frame(self):
        # --- Curve Fit File Picker ---
        upload_frame = tk.Frame(self.select_input_type_frame)
        upload_frame.pack()
        curve_fit_button = ttk.Button(upload_frame, text="Select Curve File", command=self.select_curve_file_and_process)
        curve_fit_button.pack(side=tk.LEFT, padx=10)

        self.curve_file_path_var = tk.StringVar(value="")
        curve_file_label = tk.Label(upload_frame, textvariable=self.curve_file_path_var)
        curve_file_label.pack()
        return upload_frame

    def show_frame(self):
        selected_frame = self.input_type_options.get()
        if selected_frame in self.frames:
            # hide all the frames first
            for frame in self.frames.values():
                frame.pack_forget()
            # but show the selected frame
            self.frames[selected_frame].pack(fill=tk.BOTH)

    def clear_existing_data(self):
        self.custom_functions = []
        self.generated_data = None
        # Clear the see_inputted_functions frame
        for widget in self.see_inputted_functions.winfo_children():
            widget.destroy()
        # Reset the buttons
        self.line_button.config(state=tk.NORMAL)
        self.heaviside_button.config(state=tk.NORMAL)

    def add_function(self, in_type, arg1, arg2, arg3, arg4):
        if in_type == input_type.LINE:
            slope = float(arg1.get()); y_int = float(arg2.get())
            x_start = float(arg3.get()); x_end = float(arg4.get())
            if not self.custom_x_inputs_are_valid(x_start, x_end): return
            if self.check_if_in_previous_x_ranges((x_start, x_end)): return

            self.heaviside_button.config(state=tk.DISABLED)
            self.time_tuples_list.append((x_start, x_end))
            self.custom_functions.append((slope, y_int, x_start, x_end))
            string_func = f"y = ({slope})*x + {y_int}"
            rng = f"[{x_start} to {x_end}]"

            x_values = np.linspace(x_start, x_end, 100)
            y_values = slope * x_values + y_int
            self.generated_data = [[float(x), float(y)] for x, y in zip(x_values, y_values)]
            self.controller.update_app_data("generated_data", self.generated_data)
            if self.inputs_completed_callback:
                self.inputs_completed_callback("function_button_pressed", True)

            item = {"type":"LINE", "params":(slope, y_int, x_start, x_end)}
            self.func_model.append(item)
            self.func_list.insert("", "end", values=("LINE", string_func, rng))

        elif in_type == input_type.HEAVISIDE:
            amplitude = float(arg1.get()); x_start = float(arg2.get()); x_end = float(arg3.get())
            if not self.custom_x_inputs_are_valid(x_start, x_end): return
            if self.check_if_in_previous_x_ranges((x_start, x_end)): return

            self.time_tuples_list.append((x_start, x_end))
            self.line_button.config(state=tk.DISABLED)
            self.custom_functions.append((amplitude, x_start, x_end))

            x_values = np.linspace(x_start, x_end, 100)
            y_values = [amplitude if x >= x_start else 0 for x in x_values]
            self.generated_data = [[float(x), float(y)] for x, y in zip(x_values, y_values)]
            self.controller.update_app_data("generated_data", self.generated_data)
            if self.inputs_completed_callback:
                self.inputs_completed_callback("function_button_pressed", True)

            item = {"type":"HEAVISIDE", "params":(amplitude, x_start, x_end)}
            self.func_model.append(item)
            self.func_list.insert("", "end", values=("HEAVISIDE", f"amplitude = {amplitude}", f"[{x_start} to {x_end}]"))

        else:
            return

    def _selected_index(self):
        sel = self.func_list.selection()
        if not sel:
            return None
        return self.func_list.index(sel[0])

    def delete_selected_function(self):
        idx = self._selected_index()
        if idx is None:
            return
        item = self.func_model.pop(idx)
        if item["type"] == "LINE":
            _, _, x0, x1 = item["params"]
        else:
            _, x0, x1 = item["params"]
        try:
            self.time_tuples_list.remove((x0, x1))
        except ValueError:
            pass
        self.func_list.delete(self.func_list.get_children()[idx])
        if not self.func_model:
            self.line_button.config(state=tk.NORMAL)
            self.heaviside_button.config(state=tk.NORMAL)

    def edit_selected_function(self):
        idx = self._selected_index()
        if idx is None:
            return
        item = self.func_model[idx]
        if item["type"] == "LINE":
            slope, yint, x0, x1 = item["params"]
            curr_range = (x0, x1)
            def _apply(m, b, xa, xb):
                nonlocal curr_range, x0, x1
                # temporarily remove this item’s current range so we don’t collide with ourselves
                try:
                    self.time_tuples_list.remove(curr_range)
                except ValueError:
                    pass
                if self.check_if_in_previous_x_ranges((xa, xb)):
                    # restore old range and abort
                    self.time_tuples_list.append(curr_range)
                    return
                # commit new model data
                self.func_model[idx] = {"type": "LINE", "params": (m, b, xa, xb)}
                # regenerate curve
                x_values = np.linspace(xa, xb, 100)
                y_values = m * x_values + b
                self.generated_data = [[float(x), float(y)] for x, y in zip(x_values, y_values)]
                self.controller.update_app_data("generated_data", self.generated_data)
                if self.inputs_completed_callback:
                    self.inputs_completed_callback("function_button_pressed", True)
                # update UI
                desc = f"y = ({m})*x + {b}"
                rng = f"[{xa} to {xb}]"
                row_id = self.func_list.get_children()[idx]
                self.func_list.item(row_id, values=("LINE", desc, rng))
                # commit new time range and update the tracker
                self.time_tuples_list.append((xa, xb))
                curr_range = (xa, xb)
                x0, x1 = xa, xb
            open_line_editor(self, slope, yint, x0, x1, _apply)
        else:
            amp, x0, x1 = item["params"]
            curr_range = (x0, x1)
            def _apply(a, t0, x1_new):
                nonlocal curr_range, x0, x1
                try:
                    self.time_tuples_list.remove(curr_range)
                except ValueError:
                    pass

                if self.check_if_in_previous_x_ranges((t0, x1_new)):
                    self.time_tuples_list.append(curr_range)
                    return

                self.func_model[idx] = {"type": "HEAVISIDE", "params": (a, t0, x1_new)}
                xs = np.linspace(t0, x1_new, 100)
                ys = [a if x >= t0 else 0 for x in xs]
                self.generated_data = [[float(x), float(y)] for x, y in zip(xs, ys)]
                self.controller.update_app_data("generated_data", self.generated_data)
                if self.inputs_completed_callback:
                    self.inputs_completed_callback("function_button_pressed", True)

                desc = f"amplitude = {a}; from x = [{t0} to {x1_new}]"
                row_id = self.func_list.get_children()[idx]
                self.func_list.item(row_id, values=("HEAVISIDE", desc, f"[{t0} to {x1_new}]"))

                self.time_tuples_list.append((t0, x1_new))
                curr_range = (t0, x1_new)
                x0, x1 = t0, x1_new
            open_heaviside_editor(self, amp, x0, x1, _apply)

    def select_curve_file_and_process(self):
        file_path = filedialog.askopenfilename(
            title="Select a Curve File",
            filetypes=[("CSV Files","*.csv"),("Text Files","*.txt"),("DAT Files","*.dat"),("All Files","*.*")],
        )
        if file_path:
            self.clear_existing_data()
            self.curve_file_path_var.set(file_path)
            self.process_csv_file(file_path)

    def process_csv_file(self, file_path):
        try:
            data_points = []
            with open(file_path, 'r') as file:
                csv_reader = csv.reader(file)
                for row in csv_reader:
                    try:
                        x, y = map(float, row)
                        data_points.append([x, y])
                    except ValueError:
                        print(f"Skipping row: {row} - Invalid data format")
                        continue 
            self.controller.update_app_data("generated_data", data_points)
            if self.inputs_completed_callback:
                self.inputs_completed_callback("function_button_pressed", True)
        except FileNotFoundError:
            print("File not found.")
        except Exception as e:
            print(f"Error processing CSV file: {e}")

    def on_y_parameter_selected(self, event=None):
        if self.y_parameter_dropdown.get():
            if self.inputs_completed_callback:
                self.inputs_completed_callback("y_param_dropdown_selected", True)

    def on_ac_response_selected(self, event=None):
        selected_label = self.ac_response_var.get()
        for value, label in self.ac_response_options.items():
            if label == selected_label:
                self.ac_response = value
                break
        self._update_ac_response_labels()
        if self.inputs_completed_callback:
            self.inputs_completed_callback("ac_response_changed", self.ac_response)

    def set_analysis_context(self, analysis_type: str, ac_response: Optional[str] = None) -> None:
        self.analysis_type = (analysis_type or "transient").lower()
        if ac_response:
            candidate = ac_response.lower()
            if candidate in {"magnitude", "magnitude_db", "phase", "real", "imag"}:
                self.ac_response = candidate
            else:
                self.ac_response = "magnitude"
        else:
            self.ac_response = "magnitude"
        if self.analysis_type == "ac":
            self.x_parameter_var.set("FREQ")
            self.x_param_label.config(text="X Parameter: FREQ")
            self.ac_response_var.set(self.ac_response_options.get(self.ac_response, "Magnitude"))
            self.ac_response_frame.pack(side=tk.LEFT)
            self._update_ac_response_labels()
        else:
            self.x_parameter_var.set("TIME")
            self.x_param_label.config(text="X Parameter: TIME")
            self.y_param_label.config(text="Y Parameter:")
            self.ac_response_frame.pack_forget()

    def _format_y_parameter_for_analysis(self, value: str) -> str:
        if not value:
            return value
        token = value.strip()
        if self.analysis_type == "ac":
            lowered = token.lower()
            if lowered.startswith(("vm(", "vp(", "vr(", "vi(")):
                return token.upper()
            match = re.match(r"v\s*\((.+)\)", token, flags=re.IGNORECASE)
            if match:
                inner = match.group(1).strip().upper()
                prefix = "VM"
                if self.ac_response == "phase":
                    prefix = "VP"
                elif self.ac_response == "real":
                    prefix = "VR"
                elif self.ac_response == "imag":
                    prefix = "VI"
                # For magnitude_db we still request VM and convert later
                return f"{prefix}({inner})"
        return token.upper()

    def get_settings(self) -> Dict[str, Any]:
        y_display = self.y_parameter_var.get()
        settings = {"curve_file": self.curve_file_path_var.get()}
        settings["x_parameter"] = self.x_parameter_var.get()
        settings["x_parameter_display"] = (
            "Frequency (Hz)" if self.analysis_type == "ac" else "Time (s)"
        )
        if self.analysis_type == "ac":
            if self.ac_response == "magnitude_db":
                unit_label = "Magnitude (dB)"
            elif self.ac_response == "phase":
                unit_label = "Phase (degrees)"
            elif self.ac_response == "real":
                unit_label = "Real Component"
            elif self.ac_response == "imag":
                unit_label = "Imaginary Component"
            else:
                unit_label = "Magnitude"
            if y_display:
                y_display_label = f"{y_display} {unit_label}"
            else:
                y_display_label = unit_label
            y_units = unit_label
        else:
            y_display_label = y_display or "Voltage"
            y_units = y_display or "Voltage"
        settings["y_parameter_display"] = y_display_label
        settings["y_parameter_expression"] = y_display
        settings["y_units"] = y_units
        settings["y_parameter"] = self._format_y_parameter_for_analysis(y_display)
        settings["ac_response"] = self.ac_response
        return settings

    def _update_ac_response_labels(self) -> None:
        if self.ac_response == "magnitude_db":
            self.y_param_label.config(text="Y Parameter (Magnitude dB):")
        elif self.ac_response == "phase":
            self.y_param_label.config(text="Y Parameter (Phase degrees):")
        else:
            self.y_param_label.config(text="Y Parameter (Magnitude):")
