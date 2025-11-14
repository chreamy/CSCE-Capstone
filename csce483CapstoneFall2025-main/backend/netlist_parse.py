import os
import re
import shlex
import numpy as np


class Component:
    def __init__(self, name="", type="", value=0.0, variable=False, modified=False, minVal=-1, maxVal=np.inf, raw_value=None, model=None, scope="top", metadata=None):
        self.name = name
        self.type = type
        self.value = value
        self.variable = variable
        self.modified = modified
        self.minVal = minVal
        self.maxVal = maxVal
        self.raw_value = raw_value
        self.model = model
        self.scope = scope
        self.metadata = metadata or {}


class Netlist:
    def __init__(self, file_path):
        components, nodes, include_directives, model_definitions, parameter_values = self.parse_file(file_path)
        self.components = components
        self.nodes = nodes
        self.include_directives = include_directives
        self.model_definitions = model_definitions
        self.parameter_values = parameter_values
        self.file_path = file_path

    def parse_file(self, file_path):
        components = []
        nodes = set()
        include_directives = []
        model_definitions = {}
        parameter_values = {}
        subckt_stack = []
        pending_line = ""

        def process_line(stripped_line):
            if not stripped_line or stripped_line.startswith(("*", ";")):
                return

            try:
                tokens = shlex.split(stripped_line, posix=False)
            except ValueError:
                tokens = stripped_line.split()

            if not tokens:
                return

            keyword = tokens[0].upper()
            scope = subckt_stack[-1] if subckt_stack else "top"

            if keyword == ".SUBCKT":
                subckt_stack.append(tokens[1] if len(tokens) > 1 else "")
                return
            if keyword == ".ENDS":
                if subckt_stack:
                    subckt_stack.pop()
                return
            if keyword in (".INCLUDE", ".INC"):
                include_directives.append({
                    "type": "include",
                    "path": tokens[1].strip('"') if len(tokens) > 1 else "",
                    "raw": stripped_line,
                    "scope": scope,
                })
                return
            if keyword == ".LIB":
                include_directives.append({
                    "type": "lib",
                    "path": tokens[1].strip('"') if len(tokens) > 1 else "",
                    "section": tokens[2] if len(tokens) > 2 else "",
                    "raw": stripped_line,
                    "scope": scope,
                })
                return
            if keyword == ".MODEL" and len(tokens) >= 3:
                model_definitions[tokens[1].upper()] = {
                    "type": tokens[2],
                    "definition": stripped_line,
                    "scope": scope,
                }
                return
            if keyword in (".PARAM", ".PARAMS") and len(tokens) > 1:
                body = stripped_line[len(tokens[0]):].strip()
                for key, expr in self._iterate_param_assignments(body):
                    value = self._convert_value(expr, parameter_values)
                    if value is not None:
                        parameter_values[key.upper()] = value
                return

            leading_char = tokens[0][0].upper()

            if scope != "top":
                return

            if leading_char == "X" and len(tokens) > 2:
                for token in tokens[1:-1]:
                    nodes.add(token)
                return
            if leading_char == "A" and len(tokens) >= 9:
                for token in tokens[1:9]:
                    nodes.add(token)
                return
            if leading_char in {"B", "C", "D", "F", "H", "I", "L", "R", "V", "W"}:
                if leading_char in {"R", "L", "C"} and len(tokens) >= 4:
                    converted_value = self._convert_value(tokens[3], parameter_values)
                    if converted_value is None:
                        return
                    components.append(Component(
                        name=tokens[0],
                        type=leading_char,
                        value=converted_value,
                        raw_value=tokens[3],
                        scope=scope,
                    ))
                elif leading_char in {"V", "I"}:
                    raw_value = tokens[3] if len(tokens) >= 4 else tokens[-1]
                    converted_value = self._convert_value(raw_value, parameter_values)
                    components.append(Component(
                        name=tokens[0],
                        type=leading_char,
                        value=converted_value if converted_value is not None else 0.0,
                        raw_value=raw_value,
                        scope=scope,
                    ))
                if len(tokens) >= 3:
                    nodes.add(tokens[1])
                    nodes.add(tokens[2])
                return
            if leading_char in {"J", "Q", "U", "Z"} and len(tokens) >= 4:
                nodes.add(tokens[1])
                nodes.add(tokens[2])
                nodes.add(tokens[3])
                return
            if leading_char in {"E", "G", "M", "O", "S", "T"} and len(tokens) >= 5:
                nodes.add(tokens[1])
                nodes.add(tokens[2])
                nodes.add(tokens[3])
                nodes.add(tokens[4])
                return

        try:
            with open(file_path, "r") as file:
                for raw_line in file:
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    if stripped.startswith("+") and pending_line:
                        pending = stripped[1:].lstrip()
                        pending_line = ("%s %s" % (pending_line, pending)).strip()
                        continue
                    if pending_line:
                        process_line(pending_line)
                    pending_line = stripped
                if pending_line:
                    process_line(pending_line)
        except FileNotFoundError:
            print("Error: The file '%s' was not found." % file_path)
        except Exception as exc:
            print("An error occurred: %s" % exc)

        return components, nodes, include_directives, model_definitions, parameter_values

    def class_to_file(self, file_path):
        try:
            with open(file_path, "r") as file:
                data = file.readlines()

            modified_components = []
            for component in self.components:
                if component.modified:
                    modified_components.append(component)
                    component.modified = False

            updated_lines = []
            ctrl = False
            for line in data:
                tokens = line.strip().split()
                if not tokens:
                    continue
                token_upper = tokens[0].upper()
                if token_upper == ".CONTROL":
                    ctrl = True
                if token_upper == ".ENDC":
                    ctrl = False
                if ctrl:
                    continue

                for component in list(modified_components):
                    if tokens[0] == component.name and len(tokens) >= 4:
                        tokens[3] = str(component.value)
                        line = "%s %s %s %s\n" % (
                            tokens[0],
                            tokens[1],
                            tokens[2],
                            float(tokens[3]),
                        )
                        modified_components.remove(component)
                        break
                updated_lines.append(line)

            with open(file_path, "w") as file:
                file.writelines(updated_lines)
        except FileNotFoundError:
            print("Error: The file '%s' was not found." % file_path)
        except Exception as exc:
            print("An error occurred: %s" % exc)

    def writeTranCmdsToFile(self, file_path, initial_step_value, final_time_value, start_time_value, step_ceiling_value, target_node, constrained_nodes):
        try:
            with open(file_path, "r") as file:
                data = file.readlines()

            filtered_lines = []
            for line in data:
                tokens = line.strip().split()
                if not tokens:
                    continue
                keyword = tokens[0].upper()
                if keyword in {".TRAN", ".AC", ".NOISE"}:
                    print("tran command detected already. Removing from copy...")
                    continue
                if keyword == ".PRINT":
                    print("print command detected already Removing from copy...")
                    continue
                filtered_lines.append(line)

            print_command_string = ".PRINT TRAN %s %s\n" % (target_node, " ".join(constrained_nodes))
            tran_command_string = ".TRAN %ss %ss %ss %ss\n" % (
                initial_step_value,
                final_time_value,
                start_time_value,
                step_ceiling_value,
            )

            insertion_index = self._find_analysis_insert_index(filtered_lines)
            filtered_lines.insert(insertion_index, tran_command_string)
            filtered_lines.insert(insertion_index + 1, print_command_string)

            with open(file_path, "w") as file:
                file.writelines(filtered_lines)
        except FileNotFoundError:
            print("Error: The file '%s' was not found." % file_path)
        except Exception as exc:
            print("An error occurred: %s" % exc)

    def writeNoiseCmdsToFile(
        self,
        file_path,
        sweep_type,
        points_per_interval,
        start_frequency,
        stop_frequency,
        output_expression,
        input_source,
    ):
        try:
            with open(file_path, "r") as file:
                data = file.readlines()

            filtered_lines = []
            for line in data:
                tokens = line.strip().split()
                if not tokens:
                    continue
                keyword = tokens[0].upper()
                if keyword in {".NOISE", ".AC", ".TRAN"}:
                    print("analysis command detected already. Removing from copy...")
                    continue
                if keyword == ".PRINT":
                    print("print command detected already. Removing from copy...")
                    continue
                filtered_lines.append(line)

            sweep = (sweep_type or "DEC").upper()
            if sweep not in {"DEC", "LIN", "OCT"}:
                sweep = "DEC"
            try:
                points_value = int(float(points_per_interval))
            except (TypeError, ValueError):
                points_value = 10
            start_literal = self._format_literal(start_frequency)
            stop_literal = self._format_literal(stop_frequency)

            output_expr = (output_expression or "").strip()
            if not output_expr:
                raise ValueError("Noise analysis requires an output expression.")
            source_name = (input_source or "").strip()
            if not source_name:
                raise ValueError("Noise analysis requires an input source.")

            noise_command_string = (
                f".NOISE {output_expr} {source_name} {sweep} {points_value} {start_literal} {stop_literal}\n"
            )
            print_command_string = ".PRINT NOISE FREQ ONOISE INOISE\n"

            insertion_index = self._find_analysis_insert_index(filtered_lines)
            filtered_lines.insert(insertion_index, noise_command_string)
            filtered_lines.insert(insertion_index + 1, print_command_string)

            with open(file_path, "w") as file:
                file.writelines(filtered_lines)
        except FileNotFoundError:
            print("Error: The file '%s' was not found." % file_path)
        except Exception as exc:
            print("An error occurred: %s" % exc)

    def writeAcCmdsToFile(self, file_path, sweep_type, points_per_interval, start_frequency, stop_frequency, print_variables):
        try:
            with open(file_path, "r") as file:
                data = file.readlines()

            filtered_lines = []
            for line in data:
                tokens = line.strip().split()
                if not tokens:
                    continue
                keyword = tokens[0].upper()
                if keyword in {".AC", ".TRAN", ".NOISE"}:
                    print("analysis command detected already. Removing from copy...")
                    continue
                if keyword == ".PRINT":
                    print("print command detected already Removing from copy...")
                    continue
                filtered_lines.append(line)

            sweep = (sweep_type or "DEC").upper()
            if sweep not in {"DEC", "LIN", "OCT"}:
                sweep = "DEC"
            try:
                points_value = int(float(points_per_interval))
            except (TypeError, ValueError):
                points_value = 10
            start_literal = self._format_literal(start_frequency)
            stop_literal = self._format_literal(stop_frequency)

            ac_command_string = f".AC {sweep} {points_value} {start_literal} {stop_literal}\n"

            ordered_variables = []
            seen = set()
            for variable in print_variables or []:
                token = (variable or "").strip()
                if not token:
                    continue
                key = token.upper()
                if key in seen:
                    continue
                seen.add(key)
                ordered_variables.append(token)

            print_command_string = f".PRINT AC {' '.join(ordered_variables)}\n"

            insertion_index = self._find_analysis_insert_index(filtered_lines)
            filtered_lines.insert(insertion_index, ac_command_string)
            filtered_lines.insert(insertion_index + 1, print_command_string)

            with open(file_path, "w") as file:
                file.writelines(filtered_lines)
        except FileNotFoundError:
            print("Error: The file '%s' was not found." % file_path)
        except Exception as exc:
            print("An error occurred: %s" % exc)

    def resolve_include_paths(self, search_paths=None):
        if search_paths is None:
            search_paths = []
        netlist_dir = os.path.dirname(os.path.abspath(self.file_path))
        resolved_entries = []
        for entry in self.include_directives:
            path_token = entry.get("path", "")
            if not path_token:
                resolved_entries.append(dict(entry, resolved_path="", found=False))
                continue
            candidate_paths = []
            if os.path.isabs(path_token):
                candidate_paths.append(path_token)
            else:
                candidate_paths.append(os.path.join(netlist_dir, path_token))
                for base in search_paths:
                    candidate_paths.append(os.path.join(base, path_token))
            resolved_path = None
            for candidate in candidate_paths:
                if os.path.exists(candidate):
                    resolved_path = candidate
                    break
            resolved_entries.append(dict(entry, resolved_path=resolved_path or "", found=resolved_path is not None))
        return resolved_entries

    def _iterate_param_assignments(self, body):
        if not body:
            return []
        cleaned = re.sub(r"\s*=\s*", "=", body)
        segments = []
        buffer = []
        depth = 0
        for char in cleaned:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth = max(depth - 1, 0)
            if depth == 0 and char in {",", " ", "\t"}:
                segment = "".join(buffer).strip()
                if segment:
                    segments.append(segment)
                buffer = []
                continue
            buffer.append(char)
        tail = "".join(buffer).strip()
        if tail:
            segments.append(tail)

        assignments = []
        for segment in segments:
            if "=" not in segment:
                continue
            key, expr = segment.split("=", 1)
            key = key.strip()
            expr = expr.strip()
            if key and expr:
                assignments.append((key, expr))
        return assignments

    def _convert_value(self, value_str, parameters=None):
        if value_str is None:
            return None
        cleaned = value_str.strip()
        if not cleaned:
            return None
        cleaned = cleaned.replace('\u00b5', 'u').replace('\u03bc', 'u')
        if cleaned.upper().startswith("VALUE="):
            cleaned = cleaned.split("=", 1)[1].strip()
        if cleaned.startswith("{") and cleaned.endswith("}"):
            inner = cleaned[1:-1].strip()
            if not inner:
                return None
            cleaned = inner

        params = parameters or {}
        parameter_key = cleaned.upper()
        if parameter_key in params:
            return params[parameter_key]

        try:
            return float(cleaned)
        except ValueError:
            pass

        match = re.fullmatch(r"([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)([A-Za-z]+)?", cleaned)
        if match:
            base = float(match.group(1))
            suffix = match.group(2) or ""
            multiplier = self._suffix_multiplier(suffix)
            if multiplier is None:
                return None
            return base * multiplier
        return None

    def _suffix_multiplier(self, suffix):
        normalized = suffix.strip()
        if not normalized:
            return 1.0
        normalized = normalized.replace('\u00b5', 'u').replace('\u03bc', 'u')
        special = {
            "M": 1e6,
            "m": 1e-3,
            "P": 1e15,
            "Z": 1e21,
            "Y": 1e24,
        }
        if normalized in special:
            return special[normalized]
        lower = normalized.lower()
        if lower == "mil":
            return 25.4e-6
        mapping = {
            "y": 1e-24,
            "z": 1e-21,
            "a": 1e-18,
            "f": 1e-15,
            "p": 1e-12,
            "n": 1e-9,
            "u": 1e-6,
            "k": 1e3,
            "meg": 1e6,
            "g": 1e9,
            "t": 1e12,
            "e": 1e18,
        }
        if lower in mapping:
            return mapping[lower]
        return None

    def _format_literal(self, value):
        """Format numbers/strings for control statements."""
        if isinstance(value, (int, float)):
            return f"{value:.6g}"
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return "0"

    def _find_analysis_insert_index(self, lines):
        subckt_depth = 0
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            tokens = stripped.split()
            keyword = tokens[0].upper()
            if keyword == ".SUBCKT":
                subckt_depth += 1
                continue
            if keyword == ".ENDS" and subckt_depth > 0:
                subckt_depth -= 1
                continue
            if subckt_depth > 0:
                continue
            if stripped.startswith("*"):
                continue
            if keyword in {".TITLE", ".OPTIONS", ".PARAM", ".INCLUDE", ".INC", ".LIB"}:
                continue
            return index
        return len(lines)
