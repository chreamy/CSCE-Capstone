
import os
import shutil
import re
import numpy as np
from backend.curvefit_optimization import curvefit_optimize, get_current_session_number

_MIN_SWEEP_FREQ = 1e-12  # Prevent zero-frequency AC/Noise sweeps
_DB_FLOOR = 1e-30


def _linear_to_db(value: float) -> float:
    """Convert linear magnitude to dB with a safe floor."""
    return 20.0 * np.log10(max(value, _DB_FLOOR))

def add_part_constraints(constraints, netlist):
    equalConstraints = []
    for constraint in constraints:
        #Parse out  components
        if constraint["type"] == "parameter":
            left = constraint["left"].strip()
            right = constraint["right"].strip()

            componentVals = {}
            for component in netlist.components:
                componentVals[component.name] = component.value
            for component in netlist.components:
                if left == component.name:
                    match constraint["operator"]:
                        case ">=":
                            component.minVal = eval(right, componentVals)
                            if component.value <= component.minVal:
                                component.value = component.minVal + 1
                                component.modified = True
                            print(f"{component.name} minVal set to {component.minVal}")
                        case "=":
                            component.value = eval(right, componentVals)
                            component.variable = False
                            component.modified = True
                            equalConstraints.append(constraint)
                            print(f"{component.name} set to {component.value}")
                        case "<=":
                            component.maxVal = eval(right, componentVals)
                            if component.value >= component.maxVal:
                                component.value = component.maxVal - 1
                                component.modified = True
                            print(f"{component.name} maxVal set to {component.maxVal}")
                    break
    return equalConstraints


def normalize_observable_for_analysis(observable, analysis_type="transient", ac_response="magnitude"):
    if observable is None:
        return ""
    token = str(observable).strip()
    if not token:
        return ""

    analysis = (analysis_type or "transient").strip().lower()
    response = (ac_response or "magnitude").strip().lower()

    if analysis != "ac":
        return token.upper()

    lowered = token.lower()
    if lowered.startswith(("vm(", "vp(", "vr(", "vi(")):
        return token.upper()

    match = re.match(r"v\s*\((.+)\)", token, flags=re.IGNORECASE)
    if match:
        inner = match.group(1).strip()
        prefix_map = {
            "magnitude": "VM",
            "mag": "VM",
            "db": "VM",
            "magnitude_db": "VM",
            "phase": "VP",
            "angle": "VP",
            "real": "VR",
            "imag": "VI",
        }
        prefix = prefix_map.get(response, "VM")
        return f"{prefix}({inner.upper()})"
    return token.upper()


def add_node_constraints(constraints, analysis_type="transient", ac_response="magnitude"):
    """
    Returns: dict[str, list[dict]]
      key   = normalized node expression (e.g., VM(OUT))
      value = list of window dicts: {"lower": float|None, "upper": float|None,
                                     "xmin": float|None, "xmax": float|None}
    """
    formatted = {}
    for c in constraints:
        if c.get("type") != "node":
            continue

        key = normalize_observable_for_analysis(c.get("left", ""), analysis_type, ac_response)
        if not key:
            continue

        # parse numeric bound
        try:
            val = float(str(c.get("right", "")).strip())
        except (TypeError, ValueError):
            continue

        op = (c.get("operator") or "").strip()
        lower = upper = None
        if op == ">=":
            lower = val
        elif op == "<=":
            upper = val
        elif op == "=":
            lower = val
            upper = val

        # optional x window
        xmin = c.get("x_min", None)
        xmax = c.get("x_max", None)
        try:
            xmin = float(xmin) if xmin not in (None, "",) else None
        except (TypeError, ValueError):
            xmin = None
        try:
            xmax = float(xmax) if xmax not in (None, "",) else None
        except (TypeError, ValueError):
            xmax = None

        window = {"lower": lower, "upper": upper, "xmin": xmin, "xmax": xmax}
        formatted.setdefault(key, []).append(window)

    return formatted


def optimizeProcess(queue, curveData, testRows, netlistPath, netlistObject, selectedParameters, optimizationTolerances, RLCBounds, xyce_executable_path=None):
    original_netlist_path = getattr(netlistObject, "file_path", netlistPath)
    try:
        constraints = (curveData or {}).get("constraints", [])
        target_expression = (curveData or {}).get("y_parameter_expression") or (curveData or {}).get("y_parameter", "")
        if ((curveData or {}).get("analysis_type") or "").strip().lower() == "noise":
            target_expression = (curveData or {}).get("y_parameter") or "ONOISE"
        target_display = target_expression
        TEST_ROWS = testRows or []
        ORIG_NETLIST_PATH = netlistPath
        NETLIST = netlistObject
        selectedParameters = selectedParameters or []
        RLCBounds = RLCBounds or [False, False, False]

        analysis_type = ((curveData or {}).get("analysis_type") or "transient").strip().lower()
        ac_settings = (curveData or {}).get("ac_settings") or {}
        noise_settings = (curveData or {}).get("noise_settings") or {}
        ac_response_alias = (ac_settings.get("response") if isinstance(ac_settings, dict) else None) or "magnitude"
        ac_response_alias = ac_response_alias.strip().lower()
        response_aliases = {
            "mag": "magnitude",
            "vm": "magnitude",
            "magnitude": "magnitude",
            "db": "magnitude_db",
            "magnitude_db": "magnitude_db",
            "phase": "phase",
            "angle": "phase",
            "real": "real",
            "imag": "imag",
        }
        ac_response = response_aliases.get(ac_response_alias, "magnitude")
        if ac_response not in {"magnitude", "phase", "real", "imag", "magnitude_db"}:
            ac_response = "magnitude"

        y_units = (curveData or {}).get("y_units", "")
        noise_quantity = (noise_settings.get("quantity") if isinstance(noise_settings, dict) else None) or "onoise"
        noise_quantity = noise_quantity.strip().lower()
        valid_noise_quantities = {"onoise", "onoise_db", "inoise", "inoise_db"}
        if noise_quantity not in valid_noise_quantities:
            noise_quantity = "onoise"

        if analysis_type == "ac":
            units_lower = str(y_units).lower()
            if "db" in units_lower:
                ac_response = "magnitude_db"
                if isinstance(ac_settings, dict):
                    ac_settings["response"] = "magnitude_db"
            elif "phase" in units_lower:
                ac_response = "phase"
                if isinstance(ac_settings, dict):
                    ac_settings["response"] = "phase"
        elif analysis_type == "noise":
            if "db" in str(y_units).lower():
                noise_quantity = "onoise_db" if noise_quantity.startswith("o") else "inoise_db"
                if isinstance(noise_settings, dict):
                    noise_settings["quantity"] = noise_quantity

        if analysis_type == "ac" and ac_response == "magnitude_db":
            converted_rows = []
            for row in TEST_ROWS:
                try:
                    x_val = float(row[0])
                    y_val = float(row[1])
                except (TypeError, ValueError, IndexError):
                    continue
                converted_rows.append([x_val, _linear_to_db(y_val)])
            TEST_ROWS = converted_rows
        elif analysis_type == "noise" and noise_quantity.endswith("_db"):
            converted_rows = []
            for row in TEST_ROWS:
                try:
                    x_val = float(row[0])
                    y_val = float(row[1])
                except (TypeError, ValueError, IndexError):
                    continue
                converted_rows.append([x_val, _linear_to_db(y_val)])
            TEST_ROWS = converted_rows

        target_identifier = (curveData or {}).get("y_parameter") or target_display
        normalized_target = normalize_observable_for_analysis(target_identifier, analysis_type, ac_response)
        x_parameter = (curveData or {}).get("x_parameter")
        if not x_parameter:
            x_parameter = "FREQ" if analysis_type in {"ac", "noise"} else "TIME"
        x_parameter = str(x_parameter).strip().upper()

        session_num = get_current_session_number()
        # Calculate group folder (1-10, 11-20, etc.)
        group_start = ((session_num - 1) // 10) * 10 + 1
        group_end = group_start + 9
        group_folder = f"{group_start}-{group_end}"
        
        # Build path: runs/1-10/1/
        group_dir = os.path.join("runs", group_folder)
        session_dir = os.path.join(group_dir, str(session_num))
        if not os.path.exists(session_dir):
            os.makedirs(session_dir)
        WRITABLE_NETLIST_PATH = os.path.join(session_dir, "optimized.txt")

        NODE_CONSTRAINTS = add_node_constraints(constraints, analysis_type, ac_response)
        if analysis_type == "noise" and NODE_CONSTRAINTS:
            print("Node constraints are not applied during noise analysis.")
            NODE_CONSTRAINTS = {}

        print(f"TARGET_VALUE (display) = {target_display}")
        print(f"TARGET_VALUE (normalized) = {normalized_target}")
        print(f"ORIG_NETLIST_PATH = {ORIG_NETLIST_PATH}")
        print(f"NETLIST.file_path = {NETLIST.file_path}")
        print(f"WRIITABLE_NETLIST_PATH = {WRITABLE_NETLIST_PATH}")
        print(f"Analysis type = {analysis_type}")
        print(f"Node constraints (normalized) = {NODE_CONSTRAINTS}")
        if analysis_type == "noise" and NODE_CONSTRAINTS:
            msg = "Node constraints are ignored during noise analysis."
            print(msg)
            queue.put(("Log", msg))
            NODE_CONSTRAINTS = {}

        for component in NETLIST.components:
            if component.name in selectedParameters:
                component.variable = True

        EQUALITY_PART_CONSTRAINTS = add_part_constraints(constraints, NETLIST)

        for component in NETLIST.components:
            match component.type:
                case "R":
                    if RLCBounds[0]:
                        if component.minVal == -1:
                            component.minVal = component.value / 10
                        if component.maxVal == np.inf:
                            component.maxVal = component.value * 10
                case "L":
                    if RLCBounds[1]:
                        if component.minVal == -1:
                            component.minVal = component.value / 10
                        if component.maxVal == np.inf:
                            component.maxVal = component.value * 10
                case "C":
                    if RLCBounds[2]:
                        if component.minVal == -1:
                            component.minVal = component.value / 10
                        if component.maxVal == np.inf:
                            component.maxVal = component.value * 10
            if component.minVal == -1:
                component.minVal = 0

        if TEST_ROWS:
            xs = [row[0] for row in TEST_ROWS]
            endValue = max(xs)
            initValue = min(xs)
        else:
            endValue = 0.0
            initValue = 0.0

        source_netlist_path = ORIG_NETLIST_PATH
        if not os.path.exists(source_netlist_path):
            source_netlist_path = NETLIST.file_path
        shutil.copyfile(source_netlist_path, WRITABLE_NETLIST_PATH)
        NETLIST.file_path = ORIG_NETLIST_PATH
        NETLIST.class_to_file(WRITABLE_NETLIST_PATH)

        print_variables = []
        if normalized_target:
            print_variables.append(normalized_target)
        for node_name in NODE_CONSTRAINTS.keys():
            if node_name not in print_variables:
                print_variables.append(node_name)

        if analysis_type == "ac":
            sweep = ac_settings.get("sweep_type") or ac_settings.get("sweep") or "DEC"
            points = ac_settings.get("points") or ac_settings.get("points_per_decade") or ac_settings.get("points_per_interval")
            if points is None:
                points = 10
            start_frequency = ac_settings.get("start_frequency", ac_settings.get("start_freq"))
            stop_frequency = ac_settings.get("stop_frequency", ac_settings.get("stop_freq"))

            default_start = max(initValue, _MIN_SWEEP_FREQ) if TEST_ROWS else _MIN_SWEEP_FREQ
            if start_frequency is None or start_frequency <= 0:
                start_frequency = default_start
            if stop_frequency is None or stop_frequency <= start_frequency:
                default_stop = max(endValue, start_frequency * 10)
                if default_stop <= start_frequency:
                    default_stop = start_frequency * 10
                stop_frequency = default_stop

            NETLIST.writeAcCmdsToFile(
                WRITABLE_NETLIST_PATH,
                sweep,
                points,
                start_frequency,
                stop_frequency,
                print_variables,
            )
        elif analysis_type == "noise":
            sweep = (
                noise_settings.get("sweep_type")
                or noise_settings.get("sweep")
                or "DEC"
            )
            points = (
                noise_settings.get("points")
                or noise_settings.get("points_per_decade")
                or noise_settings.get("points_per_interval")
                or 10
            )
            try:
                points = int(float(points))
            except (TypeError, ValueError):
                points = 10
            start_frequency = noise_settings.get("start_frequency")
            stop_frequency = noise_settings.get("stop_frequency")
            default_start = max(initValue, _MIN_SWEEP_FREQ) if TEST_ROWS else _MIN_SWEEP_FREQ
            if start_frequency is None or start_frequency <= 0:
                start_frequency = default_start
            if stop_frequency is None or stop_frequency <= start_frequency:
                default_stop = max(endValue, start_frequency * 10)
                if default_stop <= start_frequency:
                    default_stop = start_frequency * 10
                stop_frequency = default_stop
            node = (noise_settings.get("output_node") or "").strip()
            source_name = (noise_settings.get("input_source") or "").strip()
            if not node:
                raise ValueError("Noise analysis requires an output node.")
            if not source_name:
                raise ValueError("Noise analysis requires an input source.")
            source_name = source_name.upper()
            output_expression = node if node.strip().upper().startswith("V(") else f"V({node})"
            NETLIST.writeNoiseCmdsToFile(
                WRITABLE_NETLIST_PATH,
                sweep,
                points,
                start_frequency,
                stop_frequency,
                output_expression,
                source_name,
            )
        else:
            span = endValue - initValue
            if span == 0:
                step_guess = max(abs(endValue), 1e-9) / 100 if endValue else 1e-9
            else:
                step_guess = abs(span) / 100
            constrained_nodes = [node for node in print_variables if node != normalized_target]
            NETLIST.writeTranCmdsToFile(
                WRITABLE_NETLIST_PATH,
                step_guess,
                endValue,
                initValue,
                step_guess,
                normalized_target,
                constrained_nodes,
            )

        optim = curvefit_optimize(
            normalized_target,
            TEST_ROWS,
            NETLIST,
            WRITABLE_NETLIST_PATH,
            NODE_CONSTRAINTS,
            EQUALITY_PART_CONSTRAINTS,
            queue,
            optimizationTolerances[0],
            optimizationTolerances[1],
            optimizationTolerances[2],
            analysis_type=analysis_type,
            x_parameter=x_parameter,
            ac_response=ac_response,
            noise_settings=noise_settings if analysis_type == "noise" else None,
            xyce_executable_path=xyce_executable_path,
        )

        NETLIST.file_path = ORIG_NETLIST_PATH
        queue.put(("UpdateNetlist", NETLIST))
        queue.put(("UpdateOptimizationResults", optim))

        print(f"Optimization Results: {optim}")
        queue.put(("Update", "Optimization Complete!"))
        queue.put(("Update", f"Optimality: {optim[4]}"))
        queue.put(("Update", f"Final Cost: {optim[3]}"))
        queue.put(("Update", f"Initial Cost: {optim[2]}"))
        queue.put(("Update", f"Least Squares Iterations: {optim[1]}"))
        queue.put(("Update", f"Total Xyce Runs: {optim[0]}"))
        queue.put(("Done", "Optimization Results:"))
    except Exception as e:
        # Even if optimization fails, try to get partial results and log them
        print(f"Optimization failed with error: {e}")
        queue.put(("Failed", f"Optimization failed: {e}"))
        
        # Try to get partial results if available
        try:
            # The curvefit_optimize function should have logged the last 3 runs even on failure
            # We can still try to update the netlist with whatever values were set
            NETLIST.file_path = ORIG_NETLIST_PATH
            queue.put(("UpdateNetlist", NETLIST))
            queue.put(("Update", f"Optimization failed but partial results may be available in session log"))
        except:
            pass  # If even this fails, just continue
    finally:
        netlistObject.file_path = original_netlist_path
