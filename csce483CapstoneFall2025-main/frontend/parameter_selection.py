import tkinter as tk
from tkinter import messagebox
import re
from typing import List

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.netlist_parse import Netlist, Component
from .ui_theme import (
    COLORS,
    FONTS,
    create_card,
    create_primary_button,
    create_secondary_button,
    style_listbox,
)

class ParameterSelectionWindow(tk.Frame):
    def __init__(
        self, parent: tk.Tk, controller: "AppController"
    ):  # Use string annotation for type hint
        super().__init__(parent, bg=COLORS["bg_primary"])
        self.controller = controller
        self.netlist_path = self.controller.get_app_data("netlist_path")
        self.available_parameters: List[str] = []
        persisted_selected = self.controller.get_app_data("selected_parameters") or []
        self.netlist: Netlist = None
        # Try to parse the netlist early so we can filter persisted selections by component type
        if self.netlist_path:
            try:
                self.netlist = Netlist(self.netlist_path)
            except Exception:
                # Let load_and_parse_parameters handle user-facing errors later
                self.netlist = None
        if self.netlist is not None:
            component_map = {comp.name: comp for comp in self.netlist.components}
            self.selected_parameters: List[str] = [
                name for name in persisted_selected
                if name in component_map
                and not self._is_source_component(component_map[name])
            ]
        else:
            self.selected_parameters: List[str] = list(persisted_selected)
        self.nodes: set[str] = set()
        self.sources: List[str] = []

        # Header
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
            text="Select Parameters",
            font=FONTS["title"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(anchor="w", padx=24, pady=(18, 4))
        tk.Label(
            header,
            text="Choose which component parameters will be included in the optimization run.",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_secondary"],
            wraplength=620,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=24, pady=(0, 18))

        # Main content area
        content = tk.Frame(self, bg=COLORS["bg_primary"])
        content.pack(fill=tk.BOTH, expand=True, padx=32, pady=(0, 16))

        list_container = tk.Frame(content, bg=COLORS["bg_primary"])
        list_container.pack(fill=tk.BOTH, expand=True)
        list_container.columnconfigure(0, weight=1)
        list_container.columnconfigure(2, weight=1)
        list_container.rowconfigure(0, weight=1)

        # Available parameters card
        available_card = create_card(list_container)
        available_card.grid(row=0, column=0, sticky="nsew")
        available_body = available_card.inner
        tk.Label(
            available_body,
            text="Available Parameters",
            font=FONTS["subheading"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, 8))
        available_list_frame = tk.Frame(available_body, bg=COLORS["bg_secondary"])
        available_list_frame.pack(fill=tk.BOTH, expand=True)
        self.available_listbox = tk.Listbox(
            available_list_frame, selectmode=tk.MULTIPLE, exportselection=False
        )
        style_listbox(self.available_listbox)
        self.available_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        available_scrollbar = tk.Scrollbar(
            available_list_frame, orient=tk.VERTICAL, command=self.available_listbox.yview
        )
        available_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.available_listbox.config(yscrollcommand=available_scrollbar.set)

        # Action buttons between listboxes
        action_column = tk.Frame(list_container, bg=COLORS["bg_primary"])
        action_column.grid(row=0, column=1, padx=12)
        create_primary_button(
            action_column, text="Add ->", command=self.add_parameters
        ).pack(pady=6)
        create_primary_button(
            action_column, text="Select All ->", command=self.select_all_parameters
        ).pack(pady=6)
        create_secondary_button(
            action_column, text="<- Remove", command=self.remove_parameters
        ).pack(pady=6)
        create_secondary_button(
            action_column, text="<- Remove All", command=self.remove_all_parameters
        ).pack(pady=6)

        # Selected parameters card
        selected_card = create_card(list_container)
        selected_card.grid(row=0, column=2, sticky="nsew")
        selected_body = selected_card.inner
        tk.Label(
            selected_body,
            text="Selected Parameters",
            font=FONTS["subheading"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, 8))
        selected_list_frame = tk.Frame(selected_body, bg=COLORS["bg_secondary"])
        selected_list_frame.pack(fill=tk.BOTH, expand=True)
        self.selected_listbox = tk.Listbox(
            selected_list_frame, selectmode=tk.MULTIPLE, exportselection=False
        )
        style_listbox(self.selected_listbox)
        self.selected_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        selected_scrollbar = tk.Scrollbar(
            selected_list_frame, orient=tk.VERTICAL, command=self.selected_listbox.yview
        )
        selected_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.selected_listbox.config(yscrollcommand=selected_scrollbar.set)

        # Footer navigation
        footer = tk.Frame(self, bg=COLORS["bg_primary"])
        footer.pack(fill=tk.X, padx=32, pady=(0, 32))
        create_secondary_button(footer, text="Back", command=self.go_back).pack(
            side=tk.LEFT
        )
        self.continue_button = create_primary_button(
            footer, text="Continue", command=self.go_forward
        )
        self.continue_button.configure(state=tk.DISABLED)
        self.continue_button.pack(side=tk.RIGHT)

        # Load and parse parameters when the window is created
        if self.netlist_path:
            self.load_and_parse_parameters(self.netlist_path)

    def load_and_parse_parameters(self, netlist_path: str):
        """Loads the netlist and extracts parameters."""
        try:
            if self.netlist is None:
                self.netlist = Netlist(netlist_path)
            self.controller.update_app_data("netlist_object", self.netlist)
            resolved_includes = self.netlist.resolve_include_paths()
            self.controller.update_app_data("netlist_includes", resolved_includes)
            missing_includes = [entry for entry in resolved_includes if not entry.get("found")]
            if missing_includes:
                missing_list = "\n".join(
                    f"- {entry.get('path') or entry.get('raw', '')}"
                    for entry in missing_includes
                )
                messagebox.showwarning(
                    "Missing Libraries",
                    "The following .include/.lib references could not be resolved:\n"
                    + missing_list
                    + "\n\nMake sure these files are accessible to Xyce before running optimization."
                )
            self.available_parameters = [
                component.name
                for component in self.netlist.components
                if isinstance(component, Component)
                and getattr(component, "scope", "top") == "top"
                and not self._is_source_component(component)  # skip sources
            ]
            self.nodes = self.netlist.nodes
            self.sources = self._extract_source_components()
            self.update_available_listbox()
            self.controller.update_app_data("source_names", self.sources)

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
        self.controller.update_app_data("source_names", self.sources)
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

    def _extract_source_components(self) -> List[str]:
        if not self.netlist:
            return []
        names = []
        for component in self.netlist.components:
            if self._is_source_component(component):
                names.append(component.name)
        # Preserve original order but drop duplicates
        seen = set()
        ordered = []
        for name in names:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

    @staticmethod
    def _is_source_component(component: Component) -> bool:
        """
        Returns True when the component represents an independent voltage or current source
        (i.e., type "V" or "I" in SPICE netlists). Does not include dependent sources such as
        VCVS, VCCS, CCCS, or CCVS.
        """
        comp_type = getattr(component, "type", "")
        return str(comp_type).upper() in {"V", "I"}


