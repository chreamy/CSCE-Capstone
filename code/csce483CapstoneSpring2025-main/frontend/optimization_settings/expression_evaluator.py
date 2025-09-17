# frontend/optimization_settings/expression_evaluator.py
import ast
import math
import re
from typing import Dict, Any, List, Tuple


class ExpressionEvaluator:
    """
    Handles the safe validation of mathematical expressions including parameters
    and node expressions (e.g., V(node)).
    """

    _allowed_funcs: Dict[str, Any] = {  # Renamed from _allowed_names for clarity
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "sqrt": math.sqrt,
        "log": math.log,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
        # Add others like abs, pow if needed
    }

    # Store original parameters and node expressions
    def __init__(
        self, parameters: List[str] = None, node_expressions: List[str] = None
    ) -> None:
        self.original_parameters = list(parameters) if parameters else []
        self.original_node_expressions = (
            list(node_expressions) if node_expressions else []
        )

        self.mangled_node_map: Dict[
            str, str
        ] = {}  # Maps mangled name -> original V(node)
        self.reverse_mangled_node_map: Dict[
            str, str
        ] = {}  # Maps original V(node) -> mangled name

        # Create mangled names for node expressions (e.g., V(2) -> V_2)
        self.mangled_node_vars = []
        for node_expr in self.original_node_expressions:
            match = re.match(
                r"([VI])\((\w+)\)", node_expr, re.IGNORECASE
            )  # Match V(node) or I(node)
            if match:
                prefix = match.group(1).upper()  # V or I
                node_name = match.group(2)
                # Basic mangling - ensure it's a valid Python identifier and handle potential conflicts
                mangled_name = f"{prefix}_{node_name}".replace(
                    "-", "_"
                )  # Replace hyphens if nodes have them
                if mangled_name.isidentifier():
                    self.mangled_node_vars.append(mangled_name)
                    self.mangled_node_map[mangled_name] = node_expr
                    self.reverse_mangled_node_map[node_expr] = mangled_name
                else:
                    print(
                        f"Warning: Could not create valid identifier for node expression {node_expr}"
                    )
            else:
                print(f"Warning: Could not parse node expression format: {node_expr}")

        # Combine original parameters and mangled node names for validation checks
        self.allowed_mangled_vars = self.original_parameters + self.mangled_node_vars

        # Combine everything allowed in expressions
        self.full_allowed_symbols = set(self._allowed_funcs.keys()) | set(
            self.allowed_mangled_vars
        )

    def _preprocess_expression(self, expression: str) -> Tuple[str, List[str]]:
        """Converts V(node)/I(node) syntax to V_node/I_node for AST parsing."""
        processed_expression = expression
        original_names_found = []

        # Define a function for re.sub to perform replacement and capture names
        def replacer(match):
            original_name = match.group(0)  # The full V(node) or I(node)
            mangled_name = self.reverse_mangled_node_map.get(original_name)
            if mangled_name:
                if original_name not in original_names_found:
                    original_names_found.append(original_name)
                return mangled_name
            else:
                # Should not happen if map is correct, but return original if no mapping found
                return original_name

        # Use regex to find and replace V(node) or I(node) patterns
        # Need to be careful with the pattern to avoid partial matches or issues
        # Pattern: V or I, followed by '(', then node name (word chars), then ')'
        node_pattern = (
            r"[VI]\(\w+\)"  # Case-insensitive handled by map lookup later if needed
        )
        processed_expression = re.sub(
            node_pattern, replacer, expression, flags=re.IGNORECASE
        )

        # Also find regular parameter names
        # Find potential variables (simple identifiers)
        potential_vars = set(
            re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", processed_expression)
        )
        for var in potential_vars:
            if var in self.original_parameters and var not in original_names_found:
                original_names_found.append(var)

        return processed_expression, original_names_found

    # Keep evaluate method if needed, but update it to use preprocessing too

    def validate_expression(self, expression: str) -> Tuple[bool, List[str]]:
        """
        Validates a mathematical expression, checking syntax and ensuring only
        allowed functions, parameters, and node expressions (V(node)/I(node)) are used.

        Args:
            expression: The expression string to validate.

        Returns:
            A tuple: (is_valid, original_variables_used).
            - is_valid: True if the expression is valid, False otherwise.
            - original_variables_used: A list of *original* parameter names or
              node expressions (e.g., 'R1', 'V(2)') found in the expression.
        """
        # 1. Preprocess the expression ( V(2) -> V_2 )
        processed_expression, initial_names_found = self._preprocess_expression(
            expression
        )

        # 2. Validate syntax and allowed names using AST on the *processed* expression
        try:
            # Allow slightly more chars now? Parentheses are needed.
            # Basic check - AST parsing is the real security check
            # allowed_chars_pattern = r"^[a-zA-Z0-9_+\-*/().\s]+$" # Allow underscore for V_2
            # if not re.match(allowed_chars_pattern, processed_expression):
            #     return False, []

            parsed_expression = ast.parse(processed_expression, mode="eval")
            actual_mangled_vars_used = set()

            for node in ast.walk(parsed_expression):
                if isinstance(node, ast.Name):
                    # Check if the (potentially mangled) name is allowed
                    if node.id not in self.full_allowed_symbols:
                        return False, []  # Disallowed variable or function name
                    if node.id in self.allowed_mangled_vars:
                        actual_mangled_vars_used.add(node.id)  # Track used vars/nodes
                elif isinstance(node, ast.Call):
                    # Check if it's an allowed function call
                    if (
                        not isinstance(node.func, ast.Name)
                        or node.func.id not in self._allowed_funcs
                    ):
                        func_name = (
                            node.func.id
                            if isinstance(node.func, ast.Name)
                            else "unknown"
                        )
                        return False, []
                elif not isinstance(
                    node,
                    (
                        ast.Expression,
                        ast.Constant,
                        ast.UnaryOp,
                        ast.BinOp,
                        ast.Compare,
                        ast.BoolOp,
                        ast.IfExp,
                        ast.Num,
                        ast.Load,
                        ast.operator,
                        ast.unaryop,
                        ast.cmpop,
                        ast.boolop,
                        ast.expr_context,
                    ),
                ):
                    # Disallow other potentially unsafe AST node types
                    return False, []

            # Map used mangled names back to original names
            original_vars_used = []
            for mangled_var in actual_mangled_vars_used:
                if mangled_var in self.mangled_node_map:
                    original_vars_used.append(self.mangled_node_map[mangled_var])
                elif mangled_var in self.original_parameters:
                    original_vars_used.append(mangled_var)
                # Else: Should be an allowed func like pi/e, ignore here.

            return True, sorted(
                list(set(original_vars_used))
            )  # Return unique sorted original names

        except SyntaxError as e:
            return False, []  # Invalid Python syntax after preprocessing
        except Exception as e:  # Catch other potential errors during validation
            print(f"Unexpected validation error: {e}")
            return False, []
