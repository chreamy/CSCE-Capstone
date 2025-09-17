import tkinter as tk
from .netlist_uploader import NetlistUploaderWindow
from .parameter_selection import ParameterSelectionWindow
from .optimization_settings.optimization_settings_window import (
    OptimizationSettingsWindow,
)
from.optimization_summary import OptimizationSummary
from typing import Dict, Any, Optional

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class AppController:
    """Manages the application flow and data between windows."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Circuit Optimizer")
        self.root.geometry("800x600")
        self.current_window: Optional[tk.Frame] = None
        # Store data that needs to be shared between windows
        self.app_data: Dict[str, Any] = {
            "netlist_path": None,
            "selected_parameters": [],
            "optimization_settings": {},
            "nodes": set(),
            "optimization_results": [],
            "netlist_object": None,
            "generated_data": []
        }
        self.show_netlist_uploader()  # Start with the first window

    def show_netlist_uploader(self) -> None:
        """Displays the netlist upload window."""
        self._show_window(NetlistUploaderWindow)

    def show_parameter_selection(self) -> None:
        """Displays the parameter selection window."""
        self._show_window(ParameterSelectionWindow)

    def show_optimization_settings(self) -> None:
        """Displays the optimization settings window."""
        self._show_window(OptimizationSettingsWindow)

    def show_optimization_summary(self) -> None:
        """Displays the optimization settings window."""
        self._show_window(OptimizationSummary)

    def _show_window(self, window_class: type[tk.Frame], **kwargs) -> None:
        """Helper function to display a new window and destroy the old one."""
        if self.current_window:
            self.current_window.destroy()  # Destroy previous window

        self.current_window = window_class(self.root, self, **kwargs)
        self.current_window.pack(fill=tk.BOTH, expand=True)

    def navigate(self, target_window_name: str) -> None:
        """Navigates to the specified window."""
        if target_window_name == "parameter_selection":
            self.show_parameter_selection()
        elif target_window_name == "netlist_uploader":
            self.show_netlist_uploader()
        elif target_window_name == "optimization_settings":
            self.show_optimization_settings()
        elif target_window_name == "optimization_summary":
            self.show_optimization_summary()

    def update_app_data(self, key: str, value: Any) -> None:
        """Updates the shared application data."""
        self.app_data[key] = value

    def get_app_data(self, key: str) -> Any:
        """Retrieves data from the shared application data."""
        return self.app_data.get(key)
