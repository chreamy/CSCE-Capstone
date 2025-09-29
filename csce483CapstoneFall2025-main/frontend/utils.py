import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional, List, Dict
import json
import os


def check_netlist_filetype(filepath: str) -> bool:
    """Checks if the selected file has a valid netlist extension."""
    valid_extensions = (".cir", ".net", ".sp", ".txt")
    return filepath.lower().endswith(valid_extensions)


def open_file_dialog() -> Optional[str]:
    """Opens a file dialog for the user to select a netlist."""
    file_path = filedialog.askopenfilename(
        title="Select a Netlist File",
        filetypes=[
            (
                "Netlist Files",
                ("*.cir", "*.net", "*.sp", "*.txt"),
            ),  # Corrected filetypes
            ("All Files", "*.*"),
        ],
    )
    if file_path and not check_netlist_filetype(file_path):
        messagebox.showerror(
            "Error", "Invalid file type. Please select a .cir, .net, .sp, or .txt file."
        )
        return None
    return file_path


def import_constraints_from_file() -> Optional[List[Dict[str, str]]]:
    """Opens a file dialog to import constraints from a JSON file."""
    file_path = filedialog.askopenfilename(
        title="Import Constraints",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
    )
    if not file_path:
        return None  # User cancelled

    try:
        with open(file_path, "r") as f:
            constraints = json.load(f)
        # Validate the imported data
        if not isinstance(constraints, list):
            raise ValueError("Invalid constraints file format: must be a list.")
        for constraint in constraints:
            if not isinstance(constraint, dict):
                raise ValueError("Invalid constraint format: must be a dictionary.")
            if not all(
                key in constraint for key in ["left", "operator", "right"]
            ):  # Check if the dict has the keys.
                raise ValueError(
                    "Invalid constraint format: must contain 'left', 'operator', and 'right' keys."
                )
        return constraints
    except FileNotFoundError:
        messagebox.showerror("Error", f"File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        messagebox.showerror("Error", f"Invalid JSON format in file: {file_path}")
        return None
    except ValueError as e:
        messagebox.showerror("Error", str(e))
        return None
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")
        return None


def export_constraints_to_file(constraints: List[Dict[str, str]]) -> None:
    """Opens a file dialog to export constraints to a JSON file."""
    file_path = filedialog.asksaveasfilename(
        title="Export Constraints",
        defaultextension=".json",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
    )
    if not file_path:
        return  # User cancelled

    # Ensure the file has a .json extension
    if not file_path.lower().endswith(".json"):
        file_path += ".json"

    try:
        with open(file_path, "w") as f:
            json.dump(constraints, f, indent=4)  # Use indent for readability
        messagebox.showinfo("Info", f"Constraints exported to {file_path}")
    except OSError as e:
        messagebox.showerror("Error", f"Could not write to file: {e}")
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")
