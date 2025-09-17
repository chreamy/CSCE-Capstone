import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Optional
from .expression_evaluator import ExpressionEvaluator


class EditConstraintDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        parameters: List[str],
        node_expressions: List[str],
        constraint: Dict[str, str],
        allowed_left_items: List[str],
    ):
        super().__init__(parent)
        self.allowed_left_items = allowed_left_items
        self.title("Edit Constraint")
        self.parameters = parameters
        self.node_expressions = node_expressions
        self.all_allowed_vars_display = parameters + node_expressions
        self.constraint: Optional[Dict[str, str]] = constraint
        # Instantiate evaluator with separate lists
        self.evaluator = ExpressionEvaluator(
            parameters=parameters, node_expressions=node_expressions
        )

        # --- Left Expression ---
        left_frame = ttk.Frame(self)
        left_frame.pack(side=tk.LEFT, padx=5, pady=5)
        left_label = ttk.Label(left_frame, text="Left:")
        left_label.pack()
        self.left_var = tk.StringVar(value=constraint["left"])  # Pre-populate
        self.left_combobox = ttk.Combobox(
            left_frame,
            textvariable=self.left_var,  # self.left_var is already set
            values=self.allowed_left_items,  # Use the passed list
            state="readonly",  # Make it a dropdown only
            width=20,  # Adjust width if needed
        )
        self.left_combobox.pack(fill=tk.X)
        # Optional: Add check if initial value is valid
        if (
            self.left_var.get() not in self.allowed_left_items
            and self.allowed_left_items
        ):
            self.left_var.set(self.allowed_left_items[0])  # Default to first if invalid
        elif not self.allowed_left_items:
            self.left_var.set("")  # Clear if list is empty

        # --- Operator ---
        operator_frame = ttk.Frame(self)
        operator_frame.pack(side=tk.LEFT, padx=5, pady=5)
        operator_label = ttk.Label(operator_frame, text="Operator:")
        operator_label.pack()
        self.operator_var = tk.StringVar(value=constraint["operator"])  # Pre-populate
        operators = ["=", ">=", "<="]
        for op in operators:
            op_radio = ttk.Radiobutton(
                operator_frame, text=op, variable=self.operator_var, value=op
            )
            op_radio.pack(anchor=tk.W)

        # --- Right Expression/Value ---
        right_frame = ttk.Frame(self)
        right_frame.pack(side=tk.LEFT, padx=5, pady=5)
        right_label = ttk.Label(right_frame, text="Right:")
        right_label.pack()
        self.right_var = tk.StringVar(value=constraint["right"])  # Pre-populate
        right_entry = ttk.Entry(right_frame, textvariable=self.right_var, width=15)
        right_entry.pack(side=tk.LEFT)

        # --- OK and Cancel Buttons ---
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)
        ok_button = ttk.Button(button_frame, text="OK", command=self.on_ok)
        ok_button.pack(side=tk.LEFT, padx=5)
        cancel_button = ttk.Button(button_frame, text="Cancel", command=self.on_cancel)
        cancel_button.pack(side=tk.LEFT, padx=5)

    def on_ok(self):
        left = self.left_var.get().strip()
        operator = self.operator_var.get()
        right = self.right_var.get().strip()

        # Validate inputs
        if not left or not operator or not right:
            messagebox.showerror("Error", "All fields are required.")
            return

        if not self.is_valid_input(left):  # Corrected call: self.is_valid_input
            return
        if not self.is_valid_input(right):  # Corrected call: self.is_valid_input
            return

        # Update the constraint dictionary
        if self.constraint is not None:
            self.constraint["left"] = left
            self.constraint["operator"] = operator
            self.constraint["right"] = right
        else:  # This case *shouldn't* happen, but it's good to be defensive
            self.constraint = {"left": left, "operator": operator, "right": right}

        self.destroy()

    def on_cancel(self):
        # Don't change the constraint
        self.destroy()

    def is_valid_input(self, input_str: str) -> bool:
        """Validates the right-hand side string as either a valid expression or a number."""
        # 1. Try to validate as an expression using the evaluator
        is_valid_expr, used_vars = self.evaluator.validate_expression(input_str)

        if is_valid_expr:
            # --- REMOVED REDUNDANT LOOP ---
            # If validate_expression returned True, the variables used are already confirmed
            # to be within the evaluator's allowed set (parameters + mangled nodes).
            return True  # It's a valid expression

        # 2. If not a valid expression, check if it's a valid number
        try:
            # TODO: Enhance to handle SI units like '1k', '0.1u' if desired
            float(input_str)
            return True  # It's a valid number
        except ValueError:
            # If it's neither a valid expression nor a valid number
            messagebox.showerror(
                "Validation Error",
                f"Invalid right-hand side: '{input_str}'.\nMust be a valid number or expression using allowed terms.",
                parent=self,
            )
            return False
