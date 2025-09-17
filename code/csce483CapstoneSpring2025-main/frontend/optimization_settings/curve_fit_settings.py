import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Any
import numpy as np
import csv
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
        self.input_type_options['values'] = ('Line',
                                        'Heaviside',
                                        'Upload')
        self.input_type_options.pack(side=tk.LEFT)
        if self.input_type_options['values']:
            self.input_type_options.current(0)
        self.input_type_options.bind("<<ComboboxSelected>>", lambda event: self.show_frame())

        self.frames['Line'] = self.create_line_frame()
        self.frames['Heaviside'] = self.create_heaviside_frame()
        self.frames['Upload'] = self.create_upload_frame()

        for frame in self.frames.values():
            frame.pack_forget()

        self.see_inputted_functions = ttk.Frame(self)
        self.see_inputted_functions.pack(pady=5, side=tk.TOP, expand=False)




        # --- X and Y Parameter Dropdowns and Expressions ---
        x_param_label = ttk.Label(self, text="X Parameter: TIME , ")
        x_param_label.pack(side=tk.LEFT)
        self.x_parameter_var = tk.StringVar(value="TIME")

        y_param_label = ttk.Label(self, text="Y Parameter:")
        y_param_label.pack(side=tk.LEFT)
        self.y_parameter_var = tk.StringVar()

        y_param_frame = ttk.Frame(self)
        y_param_frame.pack(side=tk.LEFT)
        self.y_parameter_dropdown = ttk.Combobox(
            y_param_frame,
            textvariable=self.y_parameter_var,
            values=[f"V({node})" for node in self.nodes],  # Use node voltages
            state="readonly",
        )
        self.y_parameter_dropdown.pack(side=tk.LEFT, padx=5)
        self.y_parameter_dropdown.bind(
            "<<ComboboxSelected>>", self.on_y_parameter_selected
        )
    
    def custom_x_inputs_are_valid(self, x_start, x_end) -> bool:
        if (x_start < 0):
            messagebox.showerror("Input Error", "The starting x value may NOT be less than 0.")
            return False
        if (x_end < 0):
            messagebox.showerror("Input Error", "The ending x value may NOT be less than 0.")
            return False
        if (x_start >= x_end):
            messagebox.showerror("Input Error", "The starting x value may NOT be greater than the ending x value.")
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
                return True  # Return True if an intersection is found
        return False  # Return False if no intersections are found
        
    def create_line_frame(self):
        line_frame = tk.Frame(self.select_input_type_frame)
        line_frame.pack()
        tk.Label(line_frame, text="Slope = ").pack(side=tk.LEFT) 
        line_slope = tk.Entry(line_frame, width=5)
        line_slope.pack(side=tk.LEFT)# have to separate the pack() into a new line bc it makes the type NONE
        tk.Label(line_frame, text=", Y-intercept = ").pack(side=tk.LEFT) 
        line_intercept = tk.Entry(line_frame, width=5)
        line_intercept.pack(side=tk.LEFT)
        tk.Label(line_frame, text=", From x = ").pack(side=tk.LEFT)
        line_start_x = tk.Entry(line_frame, width=5)
        line_start_x.pack(side=tk.LEFT)
        tk.Label(line_frame, text="to x = ").pack(side=tk.LEFT)
        line_end_x = tk.Entry(line_frame, width=5)
        line_end_x.pack(side=tk.LEFT)        
        self.line_button = ttk.Button(line_frame, text="Add Line", command=lambda: self.add_function(input_type.LINE, line_slope, line_intercept, line_start_x, line_end_x))
        self.line_button.pack(side=tk.LEFT, padx=10)
        self.custom_functions = []

        return line_frame

    def create_heaviside_frame(self):
        heaviside_frame = tk.Frame(self.select_input_type_frame)
        heaviside_frame.pack()
        tk.Label(heaviside_frame, text="Amplitude = ").pack(side=tk.LEFT) 
        heaviside_amplitude = tk.Entry(heaviside_frame, width=5)
        heaviside_amplitude.pack(side=tk.LEFT)# have to separate the pack() into a new line bc it makes the type NONE
        tk.Label(heaviside_frame, text=", From x = ").pack(side=tk.LEFT)
        heaviside_start_x = tk.Entry(heaviside_frame, width=5)
        heaviside_start_x.pack(side=tk.LEFT)
        tk.Label(heaviside_frame, text="to x = ").pack(side=tk.LEFT)
        heaviside_end_x = tk.Entry(heaviside_frame, width=5)
        heaviside_end_x.pack(side=tk.LEFT)
        self.heaviside_button = ttk.Button(heaviside_frame, text="Add Heaviside", command=lambda:
                   self.add_function(input_type.HEAVISIDE, heaviside_amplitude, heaviside_start_x, heaviside_end_x,""))
        self.heaviside_button.pack(side=tk.LEFT, padx=10)
        
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
            slope = float(arg1.get())
            y_int = float(arg2.get())
            x_start = float(arg3.get())
            x_end = float(arg4.get())
            
            if (self.custom_x_inputs_are_valid(x_start, x_end) == False):
                return
            
            if (self.check_if_in_previous_x_ranges((x_start, x_end)) == True):
                return
            
            self.heaviside_button.config(state=tk.DISABLED) #disable the other button
            
            self.time_tuples_list.append((x_start, x_end))
            
            self.custom_functions.append((slope, y_int, x_start, x_end))
            string_func = f"LINE: y = ({slope})*x + {y_int}; from x = [{x_start} to {x_end}]"

            x_values = np.linspace(x_start, x_end, 100)
            y_values = slope * x_values + y_int
            self.generated_data = [[float(x), float(y)] for x, y in zip(x_values, y_values)]
            self.controller.update_app_data("generated_data", self.generated_data)

            if self.inputs_completed_callback:
                self.inputs_completed_callback("function_button_pressed", True)

        elif in_type == input_type.HEAVISIDE:
            amplitude = float(arg1.get())
            x_start = float(arg2.get())
            x_end = float(arg3.get())

            if (self.custom_x_inputs_are_valid(x_start, x_end) == False):
                return
            
            if (self.check_if_in_previous_x_ranges((x_start, x_end)) == True):
                return
            
            self.time_tuples_list.append((x_start, x_end))

            self.line_button.config(state=tk.DISABLED) #disable the other button          

            self.custom_functions.append((amplitude, x_start, x_end))
            string_func = f"HEAVISIDE: amplitude = {amplitude}; from x = [{x_start} to {x_end}]"
            
            x_values = np.linspace(x_start, x_end, 100)
            y_values = [amplitude if x >= x_start else 0 for x in x_values]
            self.generated_data = [[float(x), float(y)] for x, y in zip(x_values, y_values)]
            self.controller.update_app_data("generated_data", self.generated_data)

            if self.inputs_completed_callback:
                self.inputs_completed_callback("function_button_pressed", True)

        else:
            return # this function should never be called if the type was anything other than LINE or HEAVISIDE (i.e. it could not be called if type was UPLOAD)
        self.func_label = ttk.Label(self.see_inputted_functions, text=string_func)
        self.func_label.pack(side=tk.TOP, pady=5)
       
    def select_curve_file_and_process(self):
        file_path = filedialog.askopenfilename(
            title="Select a Curve File",
            filetypes=[
                ("CSV Files", "*.csv"),
                ("Text Files", "*.txt"),
                ("DAT Files", "*.dat"),
                ("All Files", "*.*"),
            ],
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
                    # this is assuming CSV is formatted as x,y
                    try:
                        x, y = map(float, row)  # Convert x and y to float
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
        if self.y_parameter_dropdown.get():  # If something is selected
            if self.inputs_completed_callback:
                self.inputs_completed_callback("y_param_dropdown_selected", True)

    def get_settings(self) -> Dict[str, Any]:
        settings = {
            "curve_file": self.curve_file_path_var.get(),
        }
        settings["x_parameter"] = self.x_parameter_var.get()
        settings["y_parameter"] = self.y_parameter_var.get()
        return settings