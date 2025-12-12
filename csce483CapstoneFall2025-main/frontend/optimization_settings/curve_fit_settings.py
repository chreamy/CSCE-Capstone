
# Visual curve editors (Matplotlib embedded in Tkinter)
from .visual_curve_editors import open_heaviside_editor, open_piecewise_editor

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Any, Optional
import numpy as np
import csv
import re
from enum import Enum
from ..ui_theme import COLORS, create_primary_button, create_secondary_button


class input_type(Enum):
    HEAVISIDE = 2
    UPLOAD = 3
    PIECEWISE  = 4

class CurveFitSettings(tk.Frame):
    def __init__(self, parent: tk.Frame, parameters: List[str], nodes, controller: "AppController", inputs_completed_callback=None):
        super().__init__(parent, bg=COLORS["bg_secondary"], bd=0, highlightthickness=0)
        self.controller = controller
        self.inputs_completed_callback = inputs_completed_callback
        self.parameters = parameters
        self.nodes = nodes
        self.x_parameter_expression_var = tk.StringVar()
        self.y_parameter_expression_var = tk.StringVar()
        self.frames = {}
        self.generated_data = None
        self.current_noise_settings: Dict[str, Any] = {}
        self.inputs_completed = False
        self.time_tuples_list = []

        # --- combobox for: line input vs heavyside vs custom csv
        self.select_input_type_frame = ttk.Frame(self, style="Card.TFrame")
        self.select_input_type_frame.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(
            self.select_input_type_frame,
            text="Target Function Type:",
            style="Secondary.TLabel",
        ).pack(side=tk.LEFT, padx=(0, 6))
        answer = tk.StringVar()
        self.input_type_options = ttk.Combobox(self.select_input_type_frame, textvariable=answer)
        self.input_type_options['values'] = ('Heaviside','Upload', 'Piecewise Linear')
        self.input_type_options.pack(side=tk.LEFT)
        if self.input_type_options['values']:
            self.input_type_options.current(0)
        self.input_type_options.bind("<<ComboboxSelected>>", lambda event: self.show_frame())
        
        self.visual_editor_bar = ttk.Frame(self, style="Card.TFrame")
        self.visual_editor_bar.pack(fill=tk.X, padx=6, pady=(6, 0))
        self.open_editor_button = create_secondary_button(
            self.visual_editor_bar,
            text="Visual Editor (select a type)",
            state=tk.DISABLED,
        )
        self.open_editor_button.pack(side=tk.LEFT)

        self.frames['Heaviside'] = self.create_heaviside_frame()
        self.frames['Upload'] = self.create_upload_frame()
        self.frames['Piecewise Linear'] = self.create_piecewise_frame()

        for frame in self.frames.values():
            frame.pack_forget()
        # Show the default editor panel on load so the visual editor button makes sense
        self.show_frame()

        # --- Target functions list + actions ---
        self.see_inputted_functions = ttk.Frame(self, style="Card.TFrame")
        self.see_inputted_functions.pack(pady=5, side=tk.TOP, expand=False, fill=tk.X)

        self.func_list = ttk.Treeview(self.see_inputted_functions, columns=("type","desc","range"), show="headings", height=4)
        self.func_list.heading("type", text="Type")
        self.func_list.heading("desc", text="Description")
        self.func_list.heading("range", text="x-range")
        self.func_list.column("type", width=90, anchor="w")
        self.func_list.column("desc", width=480, anchor="w")
        self.func_list.column("range", width=160, anchor="center")
        self.func_list.pack(side=tk.LEFT, padx=6, pady=4, fill=tk.X, expand=True)

        btns = ttk.Frame(self.see_inputted_functions, style="Card.TFrame")
        btns.pack(side=tk.LEFT, padx=8, pady=4)
        create_secondary_button(
            btns,
            text="Edit Selected",
            command=self.edit_selected_function,
        ).pack(fill=tk.X, pady=4)
        create_secondary_button(
            btns,
            text="Delete Selected",
            command=self.delete_selected_function,
        ).pack(fill=tk.X, pady=4)

        self.func_model = []  # list of {"type": "...", "params": (...)}
        self.custom_functions = []
        self.analysis_type = "transient"
        self.ac_response = "magnitude"
        self.ac_response_options = {
            "magnitude": "Magnitude",
            "phase": "Phase",
        }

        # --- X and Y Parameter Dropdowns and Expressions ---
        self.x_parameter_var = tk.StringVar(value="TIME")
        self.x_param_label = tk.Label(
            self,
            text="X Parameter: TIME",
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        )
        self.x_param_label.pack(side=tk.LEFT)

        self.y_parameter_var = tk.StringVar()
        self.y_param_label = tk.Label(
            self,
            text="Y Parameter:",
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        )
        self.y_param_label.pack(side=tk.LEFT)

        y_param_frame = ttk.Frame(self, style="Card.TFrame")
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
        self.ac_response_frame = ttk.Frame(self, style="Card.TFrame")
        self.ac_response_label = tk.Label(
            self.ac_response_frame,
            text="AC Response:",
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        )
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
        if self.analysis_type in {"ac", "noise"}:
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
        return start1 < end2 and start2 < end1


    def check_if_in_previous_x_ranges(self, time_tuple) -> bool:
        # Iterate through each tuple in the list and check for intersection
        for existing_tuple in self.time_tuples_list:
            if self.is_intersecting(existing_tuple, time_tuple):
                messagebox.showerror("Input Error", "The time range you entered overlaps with a previously defined range. Please enter a non-overlapping time range.")
                return True # Return True if an intersection is found
        return False # Return False if no intersections are found
        
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
        heaviside_frame = tk.Frame(
            self.select_input_type_frame,
            bg=COLORS["bg_secondary"],
        )
        heaviside_frame.pack()
        tk.Label(
            heaviside_frame,
            text="Amplitude = ",
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(side=tk.LEFT)
        heaviside_amplitude = tk.Entry(heaviside_frame, width=5)
        heaviside_amplitude.pack(side=tk.LEFT)
        tk.Label(
            heaviside_frame,
            text=", From x = ",
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(side=tk.LEFT)
        heaviside_start_x = tk.Entry(heaviside_frame, width=5); heaviside_start_x.pack(side=tk.LEFT)
        tk.Label(
            heaviside_frame,
            text="to x = ",
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(side=tk.LEFT)
        heaviside_end_x = tk.Entry(heaviside_frame, width=5); heaviside_end_x.pack(side=tk.LEFT)
        def _open_editor():
            amp = float(heaviside_amplitude.get() or 1.0)
            t0 = float(heaviside_start_x.get() or 0.0)
            x1 = float(heaviside_end_x.get() or 1.0)

            def _on_change(a, t_start, t_end):
                heaviside_amplitude.delete(0, tk.END); heaviside_amplitude.insert(0, str(a))
                heaviside_start_x.delete(0, tk.END);   heaviside_start_x.insert(0, str(t_start))
                heaviside_end_x.delete(0, tk.END);     heaviside_end_x.insert(0, str(t_end))

            open_heaviside_editor(
                self,
                amp,
                t0,
                x1,
                on_change=_on_change,
                on_apply=lambda a, t_start, t_end: self._add_heaviside_from_visual_editor(a, t_start, t_end),
                on_save_constraint=self.push_constraint_from_editor,
                axis_labels=self._current_axis_labels(),
                constraint_left_options=self._constraint_left_options(),
                current_y_signal=self.y_parameter_var.get() or ""
            )
        self.heaviside_open_editor_callback = _open_editor
        self.heaviside_button = create_primary_button(
            heaviside_frame,
            text="Add Heaviside",
            command=lambda: self.add_function(
                input_type.HEAVISIDE,
                heaviside_amplitude,
                heaviside_start_x,
                heaviside_end_x,
                "",
            ),
        )
        self.heaviside_button.pack(side=tk.LEFT, padx=10, pady=(4, 2))



        return heaviside_frame

    def create_upload_frame(self):
        # --- Curve Fit File Picker ---
        upload_frame = tk.Frame(
            self.select_input_type_frame,
            bg=COLORS["bg_secondary"],
        )
        upload_frame.pack()
        curve_fit_button = create_primary_button(
            upload_frame,
            text="Select Curve File",
            command=self.select_curve_file_and_process,
        )
        curve_fit_button.pack(side=tk.LEFT, padx=10, pady=(2, 2))

        self.curve_file_path_var = tk.StringVar(value="")
        curve_file_label = tk.Label(
            upload_frame,
            textvariable=self.curve_file_path_var,
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_secondary"],
        )
        curve_file_label.pack(padx=(8, 0))
        return upload_frame
    
    def _build_piecewise_series(self, pts):
        pts = sorted(pts, key=lambda p: p[0])
        xs = [p[0] for p in pts]
        x0, x1 = min(xs), max(xs)
        X = np.linspace(x0, x1, 300); Y = np.zeros_like(X)
        for i in range(len(pts)-1):
            xa, ya = pts[i]; xb, yb = pts[i+1]
            mask = (X >= xa) & (X <= xb)
            span = (xb - xa) if xb > xa else 1.0
            t = np.zeros_like(X); t[mask] = (X[mask] - xa) / span
            Y[mask] = ya + t[mask]*(yb - ya)
        return [[float(x), float(y)] for x, y in zip(X, Y)]

    def _segments_from_piecewise(self, pts):
        segs = []
        pts = sorted(pts, key=lambda p: p[0])
        for i in range(len(pts)-1):
            x0, y0 = pts[i]; x1, y1 = pts[i+1]
            if x1 <= x0: 
                continue
            m = (y1 - y0) / (x1 - x0)
            b = y0 - m*x0
            segs.append((m, b, x0, x1))
        return segs

    def _rebuild_all_line_segments(self):
        """Re-publish all line-like segments for the exporter."""
        segs = []
        for item in self.func_model:
            if item["type"] == "LINE":
                segs.append(item["params"])  # (m,b,x0,x1)
            elif item["type"] == "PIECEWISE":
                segs.extend(self._segments_from_piecewise(item["params"]))
            # HEAVISIDE/STEP can have their own path if/when needed
        self.custom_functions = segs
        self.controller.update_app_data("target_line_segments", segs)
    
    def create_piecewise_frame(self):
        frame = tk.Frame(
            self.select_input_type_frame,
            bg=COLORS["bg_secondary"],
        )
        frame.pack()
        self._pwl_points_buffer = [(0.0, 0.0), (1.0, 1.0)]
        info = tk.StringVar(value="Points: 2 | Range: [0.0 .. 1.0]")
        tk.Label(
            frame,
            textvariable=info,
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(side=tk.LEFT, padx=6)

        def _open_editor():
            def _on_change(pts):
                if pts:
                    xs = [p[0] for p in pts]
                    info.set(f"Points: {len(pts)} | Range: [{min(xs)} .. {max(xs)}]")
                else:
                    info.set("Points: 0")
                self._pwl_points_buffer = list(pts)

            open_piecewise_editor(
                self,
                list(self._pwl_points_buffer),
                on_change=_on_change,
                on_apply=self._apply_piecewise_from_editor,
                on_save_constraint=self.push_constraint_from_editor,
                axis_labels=self._current_axis_labels(),
                constraint_left_options=self._constraint_left_options(),
                current_y_signal=self.y_parameter_var.get() or ""
            )
        self.piecewise_open_editor_callback = _open_editor

        def _add_piecewise():
            pts = list(self._pwl_points_buffer)
            if len(pts) < 2:
                messagebox.showerror("Input Error", "Add at least two points.")
                return
            xs = [p[0] for p in pts]; x0, x1 = min(xs), max(xs)
            # reuse your overlap checker
            if self.check_if_in_previous_x_ranges((x0, x1)):
                return
            # commit model/list
            item = {"type":"PIECEWISE", "params": pts}
            self.func_model.append(item)
            self.time_tuples_list.append((x0, x1))
            self.func_list.insert("", "end", values=("PIECEWISE", f"{len(pts)} points", f"[{x0} to {x1}]"))
            # preview data & exporter segments
            data_points = self._build_piecewise_series(pts)
            self.generated_data = data_points
            self.controller.update_app_data("generated_data", data_points)
            if self.inputs_completed_callback:
                self.inputs_completed_callback("function_button_pressed", True)
            self._rebuild_all_line_segments()

        self._add_piecewise_callback = _add_piecewise
        create_primary_button(frame, text="Add Piecewise", command=_add_piecewise).pack(side=tk.LEFT, padx=10, pady=(2, 2))
        return frame

    def _apply_piecewise_from_editor(self, points):
        """Push the current visual editor points into the target list without extra clicks."""
        try:
            self._pwl_points_buffer = list(points)
        except Exception:
            return
        # Ensure the UI reflects the piecewise workflow
        try:
            self.input_type_options.set("Piecewise Linear")
        except Exception:
            pass
        add_cb = getattr(self, "_add_piecewise_callback", None)
        if callable(add_cb):
            add_cb()

    def show_frame(self):
        selected_frame = self.input_type_options.get()
        if selected_frame in self.frames:
            for frame in self.frames.values():
                frame.pack_forget()
            self.frames[selected_frame].pack(fill=tk.BOTH)

            if selected_frame == "Heaviside" and hasattr(self, "heaviside_open_editor_callback"):
                self.open_editor_button.configure(
                    command=self.heaviside_open_editor_callback,
                    state=tk.NORMAL,
                    text="Visual Editor (Heaviside)",
                )
            elif selected_frame == "Piecewise Linear" and hasattr(self, "piecewise_open_editor_callback"):
                self.open_editor_button.configure(
                    command=self.piecewise_open_editor_callback,
                    state=tk.NORMAL,
                    text="Visual Editor (Piecewise)",
                )
            else:
                self.open_editor_button.configure(
                    command=lambda: None,
                    state=tk.DISABLED,
                    text="Visual editor unavailable for uploads",
                )


    def clear_existing_data(self):
        self.custom_functions = []
        self.generated_data = None
        # Only clear the table rows, keep the widget
        try:
            for iid in self.func_list.get_children():
                self.func_list.delete(iid)
        except Exception:
            pass
        # Reset state/buttons
        self.heaviside_button.config(state=tk.NORMAL)
        self.func_model.clear()
        self.time_tuples_list.clear()


    def add_function(self, in_type, arg1, arg2, arg3, arg4):
        if in_type == input_type.HEAVISIDE:
            amplitude = float(arg1.get()); x_start = float(arg2.get()); x_end = float(arg3.get())
            if not self.custom_x_inputs_are_valid(x_start, x_end): return
            if self.check_if_in_previous_x_ranges((x_start, x_end)): return

            self.time_tuples_list.append((x_start, x_end))
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
            self._rebuild_all_line_segments()

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

        # CHANGED: compute the range per type
        if item["type"] == "HEAVISIDE":
            _, x0, x1 = item["params"]
        elif item["type"] == "PIECEWISE":
            pts = item["params"]
            xs = [p[0] for p in pts] if pts else []
            if xs:
                x0, x1 = min(xs), max(xs)
            else:
                x0, x1 = 0.0, 0.0
        else:
            x0, x1 = 0.0, 0.0  # safety

        try:
            self.time_tuples_list.remove((x0, x1))
        except ValueError:
            pass

        self.func_list.delete(self.func_list.get_children()[idx])

        if not self.func_model:
            self.heaviside_button.config(state=tk.NORMAL)

        self._rebuild_all_line_segments()  # ADDED


    def edit_selected_function(self):
        idx = self._selected_index()
        if idx is None:
            return
        item = self.func_model[idx]
        if item["type"] == "HEAVISIDE":
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
                self._rebuild_all_line_segments()
            open_heaviside_editor(
                self,
                amp,
                x0,
                x1,
                on_change=_apply,
                on_save_constraint=self.push_constraint_from_editor,
                axis_labels=self._current_axis_labels(),
                constraint_left_options=self._constraint_left_options(),
                current_y_signal=self.y_parameter_var.get() or ""
            )
        else:
            pts = item["params"]  # list of (x,y)
            # compute and remember the current x-range for overlap tracking
            xs = [p[0] for p in pts]
            curr_range = (min(xs), max(xs)) if xs else (0.0, 0.0)

            def _on_change(new_pts):
                # Live-apply from the editor
                nonlocal curr_range
                if len(new_pts) < 2:
                    return  # need at least two points to form a segment

                # Temporarily remove old range so we don't collide with ourselves
                try:
                    self.time_tuples_list.remove(curr_range)
                except ValueError:
                    pass

                xs_new = [p[0] for p in new_pts]
                new_range = (min(xs_new), max(xs_new))

                if self.check_if_in_previous_x_ranges(new_range):
                    # restore old range and abort this change
                    self.time_tuples_list.append(curr_range)
                    return

                # Commit model
                self.func_model[idx] = {"type": "PIECEWISE", "params": list(new_pts)}

                # Preview data
                data_points = self._build_piecewise_series(new_pts)
                self.generated_data = data_points
                self.controller.update_app_data("generated_data", data_points)
                if self.inputs_completed_callback:
                    self.inputs_completed_callback("function_button_pressed", True)

                # Update UI row
                row_id = self.func_list.get_children()[idx]
                desc = f"{len(new_pts)} points"
                rng  = f"[{new_range[0]} to {new_range[1]}]"
                self.func_list.item(row_id, values=("PIECEWISE", desc, rng))

                # Track new range and rebuild exporter segments
                self.time_tuples_list.append(new_range)
                curr_range = new_range
                self._rebuild_all_line_segments()  # ADDED

            # Open the PIECEWISE editor with live on_change
            open_piecewise_editor(
                self,
                list(pts),
                on_change=_on_change,
                on_save_constraint=self.push_constraint_from_editor,
                axis_labels=self._current_axis_labels(),
                constraint_left_options=self._constraint_left_options(),
                current_y_signal=self.y_parameter_var.get() or ""
            )

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
            if self.analysis_type == "noise" and self.inputs_completed_callback:
                node_name = self._extract_node_name(self.y_parameter_dropdown.get())
                if node_name:
                    self.inputs_completed_callback("noise_output_node", node_name)

    def on_ac_response_selected(self, event=None):
        selected_label = self.ac_response_var.get()
        for value, label in self.ac_response_options.items():
            if label == selected_label:
                self.ac_response = value
                break
        self._update_ac_response_labels()
        if self.inputs_completed_callback:
            self.inputs_completed_callback("ac_response_changed", self.ac_response)

    def set_analysis_context(
        self,
        analysis_type: str,
        ac_response: Optional[str] = None,
        noise_settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.analysis_type = (analysis_type or "transient").lower()
        if ac_response:
            candidate = ac_response.lower()
            if candidate in {"magnitude", "magnitude_db", "phase", "real", "imag"}:
                self.ac_response = candidate
            else:
                self.ac_response = "magnitude"
        else:
            self.ac_response = "magnitude"
        if noise_settings is not None:
            self.current_noise_settings = dict(noise_settings)
        elif self.analysis_type == "noise":
            self.current_noise_settings = dict(self.controller.get_app_data("noise_settings") or {})
        else:
            self.current_noise_settings = {}
        if self.analysis_type == "ac":
            self.x_parameter_var.set("FREQ")
            self.x_param_label.config(text="X Parameter: FREQ")
            self.ac_response_var.set(self.ac_response_options.get(self.ac_response, "Magnitude"))
            self.ac_response_frame.pack(side=tk.LEFT)
            self._update_ac_response_labels()
        elif self.analysis_type == "noise":
            self.x_parameter_var.set("FREQ")
            self.x_param_label.config(text="X Parameter: FREQ")
            self.y_param_label.config(text="Noise Output Node (Y Parameter):")
            self.ac_response_frame.pack_forget()
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

    def _extract_node_name(self, expression: str) -> str:
        if not expression:
            return ""
        token = expression.strip()
        match = re.match(r"v\s*\((.+)\)", token, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return token

    def get_settings(self) -> Dict[str, Any]:
        y_display = self.y_parameter_var.get()
        settings = {"curve_file": self.curve_file_path_var.get()}
        settings["x_parameter"] = self.x_parameter_var.get()
        settings["x_parameter_display"] = (
            "Frequency (Hz)" if self.analysis_type in {"ac", "noise"} else "Time (s)"
        )
        y_display_label = ""
        y_expression_value = y_display
        y_units = ""
        formatted_y_parameter = ""
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
            formatted_y_parameter = self._format_y_parameter_for_analysis(y_display)
        elif self.analysis_type == "noise":
            noise_conf = self.current_noise_settings or self.controller.get_app_data("noise_settings") or {}
            quantity = (noise_conf.get("quantity") or "onoise").lower()
            quantity_labels = {
                "onoise": ("Output noise", "V/√Hz"),
                "onoise_db": ("Output noise", "dB/√Hz"),
                "inoise": ("Input-referred noise", "V/√Hz"),
                "inoise_db": ("Input-referred noise", "dB/√Hz"),
            }
            label_text, unit_text = quantity_labels.get(quantity, quantity_labels["onoise"])
            y_units = f"{label_text} ({unit_text})"
            y_display_label = y_display or y_units
            output_node = self._extract_node_name(y_display) or noise_conf.get("output_node", "")
            y_expression_value = y_display or (f"V({output_node})" if output_node else "")
            formatted_y_parameter = "INOISE" if quantity.startswith("i") else "ONOISE"
            settings["noise_output_node"] = output_node
            settings["noise_quantity"] = quantity
        else:
            y_display_label = y_display or "Voltage"
            y_units = y_display or "Voltage"
            formatted_y_parameter = self._format_y_parameter_for_analysis(y_display)
        settings["y_parameter_display"] = y_display_label
        settings["y_parameter_expression"] = y_expression_value
        settings["y_units"] = y_units
        settings["y_parameter"] = formatted_y_parameter
        settings["ac_response"] = self.ac_response if self.analysis_type == "ac" else None
        return settings

    def _update_ac_response_labels(self) -> None:
        if self.ac_response == "magnitude_db":
            self.y_param_label.config(text="Y Parameter (Magnitude dB):")
        elif self.ac_response == "phase":
            self.y_param_label.config(text="Y Parameter (Phase degrees):")
        else:
            self.y_param_label.config(text="Y Parameter (Magnitude):")
    
    
    def push_constraint_from_editor(self, cdict: dict) -> None:
        """
        Accepts {"left","op","right","x_start","x_end"} from visual editors,
        converts to the table's expected keys, saves to controller state,
        and inserts a row in the Constraints table UI.
        """
        # Validate & normalize
        try:
            left   = str(cdict.get("left", "")).strip()
            op     = str(cdict.get("op", "")).strip()
            right  = float(cdict.get("right"))
            x_min  = float(cdict.get("x_start"))
            x_max  = float(cdict.get("x_end"))
        except Exception:
            messagebox.showerror("Constraint", "Please enter numeric Right/From/To.")
            return

        if not left or op not in {"=", ">=", "<="}:
            messagebox.showerror("Constraint", "Choose Left and an operator (=, >=, <=).")
            return
        if x_min >= x_max:
            messagebox.showerror("Constraint", "From x must be < To x.")
            return

        row = {"left": left, "operator": op, "right": right, "x_min": x_min, "x_max": x_max}
        # Route through OptimizationSettingsWindow.add_constraint so graph-created
        # constraints share the exact pipeline (type tagging + storage) as manual entries.
        opt_window = getattr(self.controller, "current_window", None)
        add_constraint = getattr(opt_window, "add_constraint", None)
        if callable(add_constraint):
            add_constraint(row)
            messagebox.showinfo("Constraint", "Saved constraint to model.")
        else:
            messagebox.showerror(
                "Constraint",
                "Could not locate the optimization window; constraint was not saved.",
            )

    def _constraint_left_options(self):
        """
        Build the 'Left' dropdown options to mirror your Add Constraint dialog.
        - Components/params: self.parameters (e.g., ['R1', 'C1', ...])
        - Node voltages: V(node) for each node
        """
        node_vs = [f"V({node})" for node in self.nodes]
        # If your dialog uses a specific ordering, adjust here
        return list(self.parameters) + node_vs

    def _current_axis_labels(self):
        """
        Build contextual axis labels for the visual editors based on the current
        analysis mode and Y-parameter selection so the plots remain self-documenting.
        """
        settings_snapshot = self.get_settings()
        x_label = settings_snapshot.get("x_parameter_display") or self.x_parameter_var.get() or "x"
        y_label = settings_snapshot.get("y_parameter_display") or self.y_parameter_var.get() or "Value"
        return (x_label, y_label)
