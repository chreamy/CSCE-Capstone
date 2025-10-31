import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Optional
from .expression_evaluator import ExpressionEvaluator
from ..ui_theme import (
    COLORS,
    FONTS,
    apply_modern_theme,
    create_card,
    create_primary_button,
    create_secondary_button,
)


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
        apply_modern_theme(self)
        self.configure(bg=COLORS["bg_primary"])
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

        container = create_card(self)
        container.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)
        body = container.inner
        body.configure(bg=COLORS["bg_secondary"])
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=1)

        # --- Left Expression ---
        left_frame = tk.Frame(body, bg=COLORS["bg_secondary"])
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(
            left_frame,
            text="Left",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(anchor="w")
        self.left_var = tk.StringVar(value=constraint["left"])
        self.left_combobox = ttk.Combobox(
            left_frame,
            textvariable=self.left_var,
            values=self.allowed_left_items,
            state="readonly",
            width=22,
        )
        self.left_combobox.pack(fill=tk.X, pady=(6, 0))
        if (
            self.left_var.get() not in self.allowed_left_items
            and self.allowed_left_items
        ):
            self.left_var.set(self.allowed_left_items[0])
        elif not self.allowed_left_items:
            self.left_var.set("")

        # --- Operator ---
        operator_frame = tk.Frame(body, bg=COLORS["bg_secondary"])
        operator_frame.grid(row=0, column=1, sticky="nsew", padx=12)
        tk.Label(
            operator_frame,
            text="Operator",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(anchor="w")
        self.operator_var = tk.StringVar(value=constraint["operator"])
        operators = ["=", ">=", "<="]
        for op in operators:
            ttk.Radiobutton(
                operator_frame, text=op, variable=self.operator_var, value=op
            ).pack(anchor="w", pady=(4, 0))

        # --- Right Expression/Value ---
        right_frame = tk.Frame(body, bg=COLORS["bg_secondary"])
        right_frame.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        tk.Label(
            right_frame,
            text="Right",
            font=FONTS["body"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(anchor="w")
        self.right_var = tk.StringVar(value=constraint["right"])
        ttk.Entry(right_frame, textvariable=self.right_var, width=22).pack(
            fill=tk.X, pady=(6, 0)
        )

        # --- OK and Cancel Buttons ---
        button_frame = tk.Frame(body, bg=COLORS["bg_secondary"])
        button_frame.grid(row=1, column=0, columnspan=3, pady=(18, 0), sticky=tk.E)
        create_secondary_button(button_frame, text="Cancel", command=self.on_cancel).pack(
            side=tk.RIGHT, padx=(0, 10)
        )
        create_primary_button(button_frame, text="Save Changes", command=self.on_ok).pack(
            side=tk.RIGHT
        )

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
