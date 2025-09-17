import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Callable


class ConstraintTable(ttk.Treeview):
    def __init__(
        self,
        parent: tk.Frame,
        add_callback: Callable[[], None],
        remove_callback: Callable[[], None],
        edit_callback: Callable[[Dict[str, str], int], None],
    ):
        super().__init__(parent, columns=("Left", "Operator", "Right"), show="headings")
        self.heading("Left", text="Left")
        self.heading("Operator", text="Operator")
        self.heading("Right", text="Right")
        self.column("Left", width=100)
        self.column("Operator", width=50)
        self.column("Right", width=100)

        # Store the callbacks
        self.add_callback = add_callback
        self.remove_callback = remove_callback
        self.edit_callback = edit_callback

    def add_constraint(self, constraint: Dict[str, str]):
        """Adds a constraint to the Treeview."""
        self.insert(
            "",
            tk.END,
            values=(constraint["left"], constraint["operator"], constraint["right"]),
        )

    def remove_constraint(self):
        """Removes the selected constraint."""
        selected_items = self.selection()
        if not selected_items:
            messagebox.showinfo("Info", "Please select a constraint to remove.")
            return

        for selected_item in reversed(selected_items):
            index = self.index(
                selected_item
            )  # get the index BEFORE deleting from treeview
            self.delete(selected_item)  # delete from the tree
            self.remove_callback()

    def edit_constraint(self):
        """Opens the EditConstraintDialog for the selected constraint."""
        selected_items = self.selection()
        if not selected_items:
            messagebox.showinfo("Info", "Please select a constraint to edit.")
            return
        if len(selected_items) > 1:
            messagebox.showinfo("Info", "Please select only one constraint to edit.")
            return

        selected_item = selected_items[0]
        index = self.index(selected_item)
        #  CRUCIAL: We need to get the constraint data *from the Treeview*,
        #   NOT from the potentially outdated self.controller.constraints.
        values = self.item(selected_item, "values")
        constraint = {"left": values[0], "operator": values[1], "right": values[2]}
        self.edit_callback(constraint, index)  # Call the edit callback

    def update_constraint(self, index: int, constraint: Dict[str, str]):
        """Updates the values of a constraint row in the Treeview."""
        item_id = self.get_children()[index]
        self.item(
            item_id,
            values=(constraint["left"], constraint["operator"], constraint["right"]),
        )

    def clear(self):
        """Removes all constraints from the Treeview."""
        for item in self.get_children():
            self.delete(item)
