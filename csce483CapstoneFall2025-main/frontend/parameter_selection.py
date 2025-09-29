import tkinter as tk
from tkinter import ttk, messagebox
import re
from typing import List

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.netlist_parse import Netlist, Component

class ParameterSelectionWindow(tk.Frame):
    def __init__(
        self, parent: tk.Tk, controller: "AppController"
    ):  # Use string annotation for type hint
        super().__init__(parent)
        self.controller = controller
        self.netlist_path = self.controller.get_app_data("netlist_path")
        self.available_parameters: List[str] = []
        self.selected_parameters: List[str] = []
        self.nodes: set[str] = set()

        self.netlist: Netlist = None

        # --- instructions/explanatory text ---
        self.instructions = ttk.Frame(self)
        self.instructions.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        explanatory_text = ttk.Label(self.instructions, text="Specify which parameters to optimize.", anchor="w")
        explanatory_text.pack(side=tk.LEFT)

        # --- Left Frame (Available Parameters) ---
        self.left_frame = ttk.Frame(self)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.available_label = ttk.Label(self.left_frame, text="Available Parameters")
        self.available_label.pack()

        # Use a Listbox with a Scrollbar
        self.available_listbox_frame = ttk.Frame(self.left_frame)
        self.available_listbox_frame.pack(fill=tk.BOTH, expand=True)

        self.available_listbox = tk.Listbox(
            self.available_listbox_frame, selectmode=tk.MULTIPLE
        )  # Allow multiple selection
        self.available_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.available_scrollbar = ttk.Scrollbar(
            self.available_listbox_frame,
            orient=tk.VERTICAL,
            command=self.available_listbox.yview,
        )
        self.available_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.available_listbox.config(yscrollcommand=self.available_scrollbar.set)
        
        # --- Buttons Frame (between listboxes) ---
        self.buttons_frame = ttk.Frame(self)
        self.buttons_frame.pack(side=tk.LEFT, padx=5)

        self.add_button = ttk.Button(
            self.buttons_frame, text="Add ->", command=self.add_parameters
        )
        self.add_button.pack(pady=5)

        self.remove_button = ttk.Button(
            self.buttons_frame, text="<- Remove", command=self.remove_parameters
        )
        self.remove_button.pack(pady=5)

        # --- Right Frame (Selected Parameters) ---
        self.right_frame = ttk.Frame(self)
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.selected_label = ttk.Label(self.right_frame, text="Selected Parameters")
        self.selected_label.pack()

        # Use a Listbox with Scrollbar
        self.selected_listbox_frame = ttk.Frame(self.right_frame)
        self.selected_listbox_frame.pack(fill=tk.BOTH, expand=True)

        self.selected_listbox = tk.Listbox(
            self.selected_listbox_frame, selectmode=tk.MULTIPLE
        )
        self.selected_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.selected_scrollbar = ttk.Scrollbar(
            self.selected_listbox_frame,
            orient=tk.VERTICAL,
            command=self.selected_listbox.yview,
        )
        self.selected_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.selected_listbox.config(yscrollcommand=self.selected_scrollbar.set)

        # --- Navigation Buttons ---
        self.navigation_frame = ttk.Frame(self)
        self.navigation_frame.pack(side=tk.BOTTOM, fill=tk.X)  # Fill horizontally

        self.back_button = ttk.Button(
            self.navigation_frame, text="Back", command=self.go_back
        )
        self.back_button.pack(side=tk.LEFT, padx=10, pady=10)  # Pack on the LEFT

        self.continue_button = ttk.Button(
            self.navigation_frame,
            text="Continue",
            command=self.go_forward,
            state=tk.DISABLED,
        )
        self.continue_button.pack(side=tk.RIGHT, padx=10, pady=10)  # Pack on the RIGHT

        self.select_all_button = ttk.Button(
            self.buttons_frame, text="Select All ->", command=self.select_all_parameters
        )
        self.select_all_button.pack(pady=5)

        self.remove_all_button = ttk.Button(
            self.buttons_frame, text="<- Remove All", command=self.remove_all_parameters
        )
        self.remove_all_button.pack(pady=5)

        # Load and parse parameters when the window is created
        if self.netlist_path:
            self.load_and_parse_parameters(self.netlist_path)

    def load_and_parse_parameters(self, netlist_path: str):
        """Loads the netlist and extracts parameters."""
        try:
            self.netlist = Netlist(netlist_path)
            self.controller.update_app_data("netlist_object",self.netlist)
            self.available_parameters = [component.name for component in self.netlist.components if isinstance(component, Component)]
            self.nodes = self.netlist.nodes
            self.update_available_listbox()

        except FileNotFoundError:
            messagebox.showerror("Error", f"Netlist file not found: {netlist_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Error parsing netlist:\n{e}")

    def extract_parameters(self, netlist_content: str) -> List[str]:
        """
        Extracts parameters from the netlist content. This is a simplified example
        and needs to be adapted based on the netlist format.
        """
        parameters = []
        # Regular expression to find lines like "R1 node1 node2 value" or "C1 node1 node2 value"
        # This is a BASIC example and needs improvement for complex netlists
        for line in netlist_content.splitlines():
            match = re.match(r"([RC][\w]+)\s+[\w+]+\s+[\w+]+\s+([\d\.eE+-]+)", line)
            if match:
                parameters.append(match.group(1))

        return parameters

    def update_available_listbox(self):
        self.available_listbox.delete(0, tk.END)
        for param in sorted(self.available_parameters):
            self.available_listbox.insert(tk.END, param)

    def update_selected_listbox(self):
        self.selected_listbox.delete(0, tk.END)
        for param in sorted(self.selected_parameters):
            self.selected_listbox.insert(tk.END, param)

    def add_parameters(self):
        selected_indices = self.available_listbox.curselection()
        for i in sorted(selected_indices, reverse=True):
            param = self.available_listbox.get(i)
            if param not in self.selected_parameters:  # prevent duplicates
                self.selected_parameters.append(param)
                self.available_parameters.remove(param)

                for component in self.netlist.components:
                    if component.name == param:
                        component.variable = True
                        break
            self.available_listbox.delete(i)
        self.update_selected_listbox()
        if self.selected_parameters:  # enable continue only if parameters are selected.
            self.continue_button.config(state=tk.NORMAL)

    def remove_parameters(self):
        selected_indices = self.selected_listbox.curselection()
        # Remove in reverse order to avoid index issues after removal
        for i in reversed(selected_indices):
            param = self.selected_parameters.pop(i)
            self.available_parameters.append(param)
            self.available_listbox.insert(tk.END, param)
            for component in self.netlist.components:
                if component.name == param:
                    component.variable = False
                    break
        self.update_selected_listbox()
        if not self.selected_parameters:
            self.continue_button.config(state=tk.DISABLED)

    def go_back(self):
        self.controller.navigate("netlist_uploader")

    def go_forward(self):
        self.controller.update_app_data("selected_parameters", self.selected_parameters)
        self.controller.update_app_data("nodes", self.nodes)
        # Placeholder for now
        self.controller.navigate("optimization_settings")


    def select_all_parameters(self):
        for param in list(self.available_parameters):  
            if param not in self.selected_parameters:
                self.selected_parameters.append(param)
                for component in self.netlist.components:
                    if component.name == param:
                        component.variable = True
                        break
        self.available_parameters.clear()
        self.update_available_listbox()
        self.update_selected_listbox()
        if self.selected_parameters:
            self.continue_button.config(state=tk.NORMAL)

    def remove_all_parameters(self):
        for param in list(self.selected_parameters):
            self.available_parameters.append(param)
            for component in self.netlist.components:
                if component.name == param:
                    component.variable = False
                    break
        self.selected_parameters.clear()
        self.update_available_listbox()
        self.update_selected_listbox()
        self.continue_button.config(state=tk.DISABLED)


