import numpy as np
import subprocess
import io
import sys
import os
import glob
from datetime import datetime
from typing import Optional, Dict, Any
from scipy.optimize import least_squares
from scipy.interpolate import interp1d
from backend.xyce_parsing_function import parse_xyce_prn_output
from backend.netlist_parse import Netlist

_SMALL_POSITIVE = 1e-30


def _convert_array_to_db(values: np.ndarray) -> np.ndarray:
    """Convert magnitude array to dB using a safe numeric floor."""
    return 20.0 * np.log10(np.maximum(values, _SMALL_POSITIVE))

def log_to_file(message: str, log_file: str = None):
    """Write log message to log file."""
    if log_file is None:
        log_file = get_session_log_file()
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{message}\n")

def log_and_append(message: str, run_info: list, queue, log_file: str = None):
    """Log message to file, append to run_info, and send to frontend in real-time."""
    run_info.append(message)
    queue.put(("Log", message))

def get_session_log_file():
    """Get the next available session log file path."""
    import os
    
    # Create runs directory if it doesn't exist
    runs_dir = "runs"
    if not os.path.exists(runs_dir):
        os.makedirs(runs_dir)
    
    # Find the next available session number
    session_num = 1
    while True:
        session_dir = os.path.join(runs_dir, str(session_num))
        log_file = os.path.join(session_dir, "session.log")
        if not os.path.exists(log_file):
            # Create the session directory
            os.makedirs(session_dir, exist_ok=True)
            break
        session_num += 1
    
    return log_file

def get_current_session_number():
    """Get the current session number (same logic as get_session_log_file but returns just the number)."""
    import os
    
    # Create runs directory if it doesn't exist
    runs_dir = "runs"
    if not os.path.exists(runs_dir):
        os.makedirs(runs_dir)
    
    # Find the next available session number
    session_num = 1
    while True:
        session_dir = os.path.join(runs_dir, str(session_num))
        log_file = os.path.join(session_dir, "session.log")
        if not os.path.exists(log_file):
            # Create the session directory
            os.makedirs(session_dir, exist_ok=True)
            break
        session_num += 1
    
    return session_num

"""
Two constraint types:
1. Node value constraints
    These will be solved by checking output after a Xyce run, then skewing the residual output so it won't select it if the voltage constraint is breached
    This will probably mess up next part value selection if if not done well
2. Part value constraints
    These are simpler to do and can be done using bounds arg of least_squares
    Equation type ones (i.e. R1 + R2 < 4000) are trickier perhaps and not currently supported.

node_constraints structure
node_constraints = {
    'V(2)': (None, 5.0),  # Example: V(2) must be <= 5V
    'V(3)': (1.0, None)   # Example: V(3) must be >= 1V
}
"""
def curvefit_optimize(
    target_value: str,
    target_curve_rows: list,
    netlist: Netlist,
    writable_netlist_path: str,
    node_constraints: dict,
    equality_part_constraints: list,
    queue,
    custom_xtol=1e-12,
    custom_gtol=1e-12,
    custom_ftol=1e-12,
    analysis_type="transient",
    x_parameter="TIME",
    ac_response="magnitude",
    noise_settings: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Run the curve-fitting optimization for the requested analysis mode.

    Args:
        target_value: normalized observable name (e.g., V(OUT), ONOISE).
        target_curve_rows: [[x, y], ...] describing the desired curve.
        netlist: parsed Netlist instance to mutate/write out.
        writable_netlist_path: temp path passed to Xyce.
        node_constraints: mapping of constraint windows by node.
        equality_part_constraints: list of part equality rules to enforce.
        queue: IPC queue for UI/log updates.
        custom_xtol/gtol/ftol: least_squares tolerances.
        analysis_type/x_parameter/ac_response: metadata from the UI.
        noise_settings: optional dict with noise sweep metadata; copied locally
            before mutation to avoid altering caller-owned dictionaries.
    """
    # Get the session log file path
    session_log_file = get_session_log_file()
    
    analysis_mode = (analysis_type or "transient").strip().lower()
    x_axis_identifier = (x_parameter or "TIME").strip().upper()
    response_aliases = {
        "mag": "magnitude",
        "magnitude": "magnitude",
        "db": "magnitude_db",
        "magnitude_db": "magnitude_db",
        "phase": "phase",
        "angle": "phase",
        "real": "real",
        "imag": "imag",
    }
    noise_settings = dict(noise_settings or {})
    valid_noise_quantities = {"onoise", "onoise_db", "inoise", "inoise_db"}
    noise_quantity = str(noise_settings.get("quantity", "onoise")).strip().lower()
    if noise_quantity not in valid_noise_quantities:
        noise_quantity = "onoise"

    response_mode = "magnitude"
    if analysis_mode == "ac":
        response_mode = response_aliases.get((ac_response or "magnitude").strip().lower(), "magnitude")
    elif analysis_mode == "noise":
        response_mode = noise_quantity

    # Initialize log file with session header
    session_start_time = datetime.now()
    log_to_file("="*80, session_log_file)
    log_to_file("Starting new optimization session", session_log_file)
    log_to_file(f"Session started at: {session_start_time.strftime('%Y-%m-%d %H:%M:%S')}", session_log_file)
    log_to_file(f"Target value: {target_value}", session_log_file)
    log_to_file(f"Netlist file: {writable_netlist_path}", session_log_file)
    log_to_file(f"Node constraints: {node_constraints}", session_log_file)
    log_to_file(f"Analysis type: {analysis_mode}", session_log_file)
    log_to_file(f"X-axis variable: {x_axis_identifier}", session_log_file)
    if analysis_mode == "ac":
        response_label = {
            "magnitude": "magnitude",
            "magnitude_db": "magnitude (dB)",
            "phase": "phase",
            "real": "real",
            "imag": "imag",
        }.get(response_mode, response_mode)
        log_to_file(f"AC response: {response_label}", session_log_file)
    elif analysis_mode == "noise":
        log_to_file(f"Noise quantity: {noise_quantity}", session_log_file)
    log_to_file(f"Optimization parameters:", session_log_file)
    log_to_file(f"  xtol: {custom_xtol}", session_log_file)
    log_to_file(f"  gtol: {custom_gtol}", session_log_file)
    log_to_file(f"  ftol: {custom_ftol}", session_log_file)
    log_to_file("="*80 + "\n", session_log_file)
    
    # Send initial info to UI (these don't need to be in run_info since they're session-level)
    queue.put(("Log", "="*80))
    queue.put(("Log", "Starting new optimization session"))
    queue.put(("Log", f"Session started at: {session_start_time.strftime('%Y-%m-%d %H:%M:%S')}"))
    queue.put(("Log", f"Target value: {target_value}"))
    queue.put(("Log", f"Netlist file: {writable_netlist_path}"))
    queue.put(("Log", f"Node constraints: {node_constraints}"))
    queue.put(("Log", f"Analysis type: {analysis_mode}"))
    queue.put(("Log", f"X-axis variable: {x_axis_identifier}"))
    if analysis_mode == "ac":
        queue.put(("Log", f"AC response: {response_label}"))
    elif analysis_mode == "noise":
        queue.put(("Log", f"Noise quantity: {noise_quantity}"))
    queue.put(("Log", f"Optimization parameters:"))
    queue.put(("Log", f"  xtol: {custom_xtol}"))
    queue.put(("Log", f"  gtol: {custom_gtol}"))
    queue.put(("Log", f"  ftol: {custom_ftol}"))
    queue.put(("Log", "="*80))

    # Store all run results for final logging
    all_run_results = []
    
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()  # Redirect output
    global xyceRuns
    # Initialize variables that need to be accessible in finally block
    xyceRuns = 0
    leastSquaresIterations = 0
    initialCost = 0
    finalCost = 0
    optimality = 0
    
    try:
        
        xyceRuns = 0
        # Assumes input_curve[0] is X, input_curve[1] is Y/target_value
        x_ideal = np.array([x[0] for x in target_curve_rows])
        y_ideal = np.array([x[1] for x in target_curve_rows])
        ideal_interpolation = interp1d(x_ideal, y_ideal)

        local_netlist_file = writable_netlist_path 
    
        # Parse netlist to figure out which parts are subject to change
        changing_components = [x for x in netlist.components if x.variable]
        changing_components_values = [x.value for x in changing_components]

        lower_bounds = np.array([x.minVal if hasattr(x, "minVal") else 0 for x in changing_components])
        upper_bounds = np.array([x.maxVal if hasattr(x, "maxVal") else np.inf for x in changing_components])

        run_state = {
            "first_run": True,
            "master_x_points": np.array([])
        }

        output_suffixes = [".prn"]
        if analysis_mode == "ac":
            output_suffixes = [".FD.prn"] + output_suffixes
        elif analysis_mode == "noise":
            output_suffixes = [
                # Primary noise sweep results (ONOISE/INOISE columns)
                ".NOISE.prn",
                # Some Xyce builds emit additional noise info in a ".NOISE0" file
                ".NOISE0.prn",
                # Noise analyses can also reuse AC data, so check for .FD outputs too
                ".FD.prn",
            ] + output_suffixes

        def _remove_old_outputs(base_path: str) -> None:
            for suffix in output_suffixes:
                candidate = base_path + suffix
                if os.path.exists(candidate):
                    try:
                        os.remove(candidate)
                    except OSError:
                        pass

        def _resolve_output_file(base_path: str) -> str:
            for suffix in output_suffixes:
                candidate = base_path + suffix
                if os.path.exists(candidate):
                    return candidate
            pattern = base_path + "*.prn"
            matches = glob.glob(pattern)
            if matches:
                matches.sort(key=os.path.getmtime, reverse=True)
                return matches[0]
            raise FileNotFoundError(f"No Xyce output file found for {base_path}")

        def residuals(component_values, components):
            global xyceRuns
            xyceRuns += 1
            new_netlist = netlist
            new_netlist.file_path = local_netlist_file

            # Edit new_netlist with correct values
            for i in range(len(component_values)):
                for netlist_component in new_netlist.components:
                    if components[i].name == netlist_component.name:
                        netlist_component.value = component_values[i]
                        netlist_component.modified = True
                        break

            # ENFORCE EQUALITY PART CONSTRAINTS
            componentVals = {}
            for component in new_netlist.components:
                componentVals[component.name] = component.value
            for constraint in equality_part_constraints:
                left = constraint["left"].strip()
                right = constraint["right"].strip()
                for component in new_netlist.components:
                    if left == component.name:
                        component.value = eval(right, componentVals)
                        component.variable = False
                        component.modified = True
            
            new_netlist.class_to_file(local_netlist_file)
            _remove_old_outputs(local_netlist_file)

            # Store run information for later logging
            run_info = []
            
            # Use combined function for all run logging
            log_and_append(f"Run #{xyceRuns} - Starting Xyce simulation", run_info, queue, session_log_file)
            log_and_append(f"Netlist file: {local_netlist_file}", run_info, queue, session_log_file)
            log_and_append("Component values:", run_info, queue, session_log_file)
            for comp in new_netlist.components:
                log_and_append(f"  {comp.name}: {comp.value} (variable={comp.variable}, modified={comp.modified})", run_info, queue, session_log_file)
            
            # Run Xyce with full output capture
            process = subprocess.run(
                ["Xyce", "-delim", "COMMA", local_netlist_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Store Xyce output (filter out time-related messages and only log specific percent complete milestones)
            log_and_append("Xyce stdout:", run_info, queue, session_log_file)
            for line in process.stdout.split('\n'):
                if line.strip():
                    # Filter out time-related messages
                    if "Current system time:" in line or "Estimated time to completion:" in line:
                        queue.put(("Log", f"  {line}"))
                        continue
                    # For percent complete messages, only log at 20%, 40%, 60%, 80%, 100%
                    if "Percent complete:" in line:
                        queue.put(("Log", f"  {line}"))
                        try:
                            # Extract the percentage value
                            percent_str = line.split("Percent complete:")[1].strip().rstrip(" %")
                            percent = float(percent_str)
                            # Only log if it's a milestone percentage
                            if percent >= 20.0 and percent % 20.0 == 0:
                                log_and_append(f"  {line}", run_info, queue, session_log_file)
                        except (ValueError, IndexError):
                            # If we can't parse the percentage, skip this line
                            continue
                    else:
                        # Log all other non-time-related messages
                        log_and_append(f"  {line}", run_info, queue, session_log_file)
            
            log_and_append("Xyce stderr:", run_info, queue, session_log_file)
            for line in process.stderr.split('\n'):
                if line.strip():
                    # Filter out time-related messages
                    if "Current system time:" in line or "Estimated time to completion:" in line:
                        queue.put(("Log", f"  {line}"))
                        continue
                    # For percent complete messages, only log at 20%, 40%, 60%, 80%, 100%
                    if "Percent complete:" in line:
                        queue.put(("Log", f"  {line}"))
                        try:
                            # Extract the percentage value
                            percent_str = line.split("Percent complete:")[1].strip().rstrip(" %")
                            percent = float(percent_str)
                            # Only log if it's a milestone percentage
                            if percent >= 20.0 and percent % 20.0 == 0:
                                log_and_append(f"  {line}", run_info, queue, session_log_file)
                        except (ValueError, IndexError):
                            # If we can't parse the percentage, skip this line
                            continue
                    else:
                        # Log all other non-time-related messages
                        log_and_append(f"  {line}", run_info, queue, session_log_file)
            
            # Store parsing attempt
            output_file = _resolve_output_file(local_netlist_file)
            log_and_append(f"Attempting to parse output file: {output_file}", run_info, queue, session_log_file)
            xyce_parse = parse_xyce_prn_output(output_file)
            log_and_append(f"Successfully parsed output file. Found {len(xyce_parse[1])} data points", run_info, queue, session_log_file)
            
            # Store this run's results
            all_run_results.append(run_info)

            headers = [header.strip() for header in xyce_parse[0]]
            header_lookup = {}
            for idx, header in enumerate(headers):
                key = header.upper()
                if key and key not in header_lookup:
                    header_lookup[key] = idx

            def resolve_header_index(identifier: str, kind: str) -> int:
                if not identifier:
                    raise ValueError(f"{kind} name is empty; cannot resolve column in Xyce output.")
                candidates = []
                raw = identifier.strip()
                if raw:
                    candidates.extend([raw, raw.upper()])
                    if raw.upper().startswith("V(") and raw.endswith(")"):
                        inner = raw[2:-1].strip()
                    else:
                        inner = raw.strip()
                    if inner:
                        candidates.extend([
                            inner,
                            inner.upper(),
                            f"V({inner})",
                            f"V({inner.upper()})",
                        ])
                seen = set()
                for candidate in candidates:
                    normalized = candidate.strip().upper()
                    if not normalized or normalized in seen:
                        continue
                    seen.add(normalized)
                    if normalized in header_lookup:
                        return header_lookup[normalized]
                available = ", ".join(headers)
                raise ValueError(f"{kind} '{identifier}' not found in Xyce output columns: {available}")

            x_index = resolve_header_index(x_axis_identifier, "X-axis variable")
            row_index = resolve_header_index(target_value, "Target variable")

            X_ARRAY_FROM_XYCE = np.array([float(row[x_index]) for row in xyce_parse[1]])
            Y_ARRAY_FROM_XYCE = np.array([float(row[row_index]) for row in xyce_parse[1]])
            if analysis_mode == "ac":
                if response_mode == "magnitude_db":
                    Y_ARRAY_FROM_XYCE = _convert_array_to_db(Y_ARRAY_FROM_XYCE)
            elif analysis_mode == "noise":
                if response_mode and response_mode.endswith("_db"):
                    Y_ARRAY_FROM_XYCE = _convert_array_to_db(Y_ARRAY_FROM_XYCE)
            elif analysis_mode == "noise":
                if response_mode and response_mode.endswith("_db"):
                    Y_ARRAY_FROM_XYCE = 20.0 * np.log10(np.maximum(Y_ARRAY_FROM_XYCE, 1e-30))

            if run_state["first_run"]:
                run_state["first_run"] = False
                run_state["master_x_points"] = X_ARRAY_FROM_XYCE


            # Send run count update for every run
            queue.put(("Update",f"total runs completed: {xyceRuns}"))
            queue.put(("UpdateYData",(analysis_mode, response_mode, X_ARRAY_FROM_XYCE, Y_ARRAY_FROM_XYCE))) 

            xyce_interpolation = interp1d(X_ARRAY_FROM_XYCE, Y_ARRAY_FROM_XYCE)

            for node_name, windows in node_constraints.items():
                node_index = resolve_header_index(node_name, "Node variable")
                node_values = np.array([float(x[node_index]) for x in xyce_parse[1]])
                # Match AC dB behavior you already have
                if analysis_mode == "ac" and response_mode == "magnitude_db" and node_name.startswith("VM("):
                    node_values = _convert_array_to_db(node_values)

                # X axis values for masking windows
                X_vals = X_ARRAY_FROM_XYCE  # already built above

                for w in windows:
                    lower = w.get("lower", None)
                    upper = w.get("upper", None)
                    xmin  = w.get("xmin", None)
                    xmax  = w.get("xmax", None)

                    mask = np.ones_like(X_vals, dtype=bool)
                    if xmin is not None:
                        mask &= (X_vals >= float(xmin))
                    if xmax is not None:
                        mask &= (X_vals <= float(xmax))

                    if not np.any(mask):
                        continue  # nothing to check in this window

                    vals = node_values[mask]
                    if ((lower is not None and np.any(vals < float(lower))) or
                        (upper is not None and np.any(vals > float(upper)))):
                        # Same arbitrarily large penalty strategy you're using today
                        return np.full_like(run_state["master_x_points"], 1e6)


            # TODO: Proper residual? (subrtarct, rms, etc.)
            return ideal_interpolation(run_state["master_x_points"]) - xyce_interpolation(run_state["master_x_points"])

        # Log optimization start (session-level, not run-specific)
        queue.put(("Log", f"Starting optimization with {len(changing_components)} variable components"))
        queue.put(("Log", f"Component bounds: {len(lower_bounds)} lower, {len(upper_bounds)} upper"))
        queue.put(("Log", "Beginning least squares optimization..."))
        
        result = least_squares(residuals, changing_components_values, method='trf', bounds=(lower_bounds, upper_bounds), args=(changing_components,),
                               xtol=custom_xtol, gtol=custom_gtol, ftol = custom_ftol, jac='3-point', verbose=1)

        for i in range(len(changing_components)):
            changing_components[i].value = result.x[i]

        optimal_netlist = netlist
        optimal_netlist.file_path = local_netlist_file
        for changed_component in changing_components:
            for netlist_component in optimal_netlist.components:
                if changed_component.name == netlist_component.name:
                    netlist_component.value = changed_component.value
                    netlist_component.modified = True
                    break

        optimal_netlist.class_to_file(local_netlist_file)

        # Log final optimization state (session-level, not run-specific)
        log_to_file("\nOptimization completed", session_log_file)
        log_to_file("Final component values:", session_log_file)
        queue.put(("Log", "Optimization completed"))
        queue.put(("Log", "Final component values:"))
        for comp in optimal_netlist.components:
            if comp.variable:
                log_to_file(f"  {comp.name}: {comp.value} (modified={comp.modified})", session_log_file)
                queue.put(("Log", f"  {comp.name}: {comp.value} (modified={comp.modified})"))

        # Parse optimization results
        sys.stdout.flush()
        captured = sys.stdout.getvalue()
        lines = captured.split("\n")
        line = next((item for item in lines if item.startswith("Function evaluations")), None)
        if line:
            values = line.split()
            leastSquaresIterations = int(values[2].rstrip(","))
            initialCost = float(values[5].rstrip(","))
            finalCost = float(values[8].rstrip(","))
            optimality = float(values[11].rstrip("."))
            
            # Send optimization metrics to UI (session-level, not run-specific)
            queue.put(("Log", "Optimization metrics:"))
            queue.put(("Log", f"  Total Xyce runs: {xyceRuns}"))
            queue.put(("Log", f"  Least squares iterations: {leastSquaresIterations}"))
            queue.put(("Log", f"  Initial cost: {initialCost}"))
            queue.put(("Log", f"  Final cost: {finalCost}"))
            queue.put(("Log", f"  Optimality: {optimality}"))

    except Exception as e:
        # Log the error
        log_to_file(f"\nOptimization failed with error: {e}", session_log_file)
        log_to_file("="*80, session_log_file)
        queue.put(("Log", f"Optimization failed with error: {e}"))
        queue.put(("Log", "="*80))

    finally:
        # Always log optimization metrics and run results, even if optimization failed
        try:
            # Log optimization metrics
            log_to_file("\nOptimization metrics:", session_log_file)
            log_to_file(f"  Total Xyce runs: {xyceRuns}", session_log_file)
            log_to_file(f"  Least squares iterations: {leastSquaresIterations}", session_log_file)
            log_to_file(f"  Initial cost: {initialCost}", session_log_file)
            log_to_file(f"  Final cost: {finalCost}", session_log_file)
            log_to_file(f"  Optimality: {optimality}", session_log_file)
            
            # Log only the last 3 run results at the end (even if optimization failed)
            if all_run_results:  # Only log if we have run results
                log_to_file("\n" + "="*80, session_log_file)
                log_to_file("DETAILED RUN RESULTS (Last 3 runs only)", session_log_file)
                log_to_file("="*80, session_log_file)
                
                # Only show the last 3 runs
                last_runs = all_run_results[-3:] if len(all_run_results) >= 3 else all_run_results
                start_run_num = max(1, len(all_run_results) - 2)  # Calculate starting run number
                
                for i, run_result in enumerate(last_runs):
                    actual_run_num = start_run_num + i
                    log_to_file(f"\n--- RUN {actual_run_num} DETAILS ---", session_log_file)
                    for line in run_result:
                        log_to_file(line, session_log_file)
            
            log_to_file("\n" + "="*80, session_log_file)
            log_to_file("END OF OPTIMIZATION SESSION", session_log_file)
            log_to_file("="*80 + "\n", session_log_file)
            queue.put(("Log", "="*80))
            queue.put(("Log", "END OF OPTIMIZATION SESSION"))
            queue.put(("Log", "="*80))
        except Exception as logging_error:
            # If logging fails, at least try to log the error
            try:
                log_to_file(f"\nError during final logging: {logging_error}", session_log_file)
            except:
                pass  # If even this fails, just continue
        
        sys.stdout = old_stdout  # Restore stdout no matter what
    return [xyceRuns, leastSquaresIterations, initialCost, finalCost, optimality]

# Voltage Divider Test
# WRITABLE_NETLIST_PATH = r"C:\Users\User\capstone\csce483CapstoneSpring2025\netlists\voltageDividerCopy.txt"
# TARGET_VALUE = 'V(2)'
# TEST_ROWS = [[0.00000000e+00, 4.00000000e+00],
#         [4.00000000e-04, 4.00000000e+00],
#         [8.00000000e-04, 4.00000000e+00],
#         [1.20000000e-03, 4.00000000e+00],
#         [1.60000000e-03, 4.00000000e+00],
#         [2.00000000e-03, 4.00000000e+00]]
# ORIG_NETLIST_PATH = r"C:\Users\User\capstone\csce483CapstoneSpring2025\netlists\voltageDivider.txt"
# TEST_NETLIST = Netlist(ORIG_NETLIST_PATH)
# for component in TEST_NETLIST.components:
#     component.variable = True
#     component.maxVal = 2001

# NODE_CONSTRAINTS = {"V(2)":(None, 4.1)}
# curvefit_optimize(TARGET_VALUE, TEST_ROWS, TEST_NETLIST, WRITABLE_NETLIST_PATH, NODE_CONSTRAINTS)

# Instermental Amp Test
# WRITABLE_NETLIST_PATH = r"C:\Users\User\capstone\csce483CapstoneSpring2025\netlists\InstermentalAmpCopy.cir"
# TARGET_VALUE = 'V(_NET3)'
# TEST_ROWS = [[0.00000000e+00, 4.00000000e+00],
#         [4.00000000e-04, 4.00000000e+00],
#         [8.00000000e-04, 4.00000000e+00],
#         [1.20000000e-03, 4.00000000e+00],
#         [1.60000000e-03, 4.00000000e+00],
#         [2.00000000e-03, 4.00000000e+00],
#         [2.40000000e-03, 4.00000000e+00],
#         [2.80000000e-03, 4.00000000e+00],
#         [3.20000000e-03, 4.00000000e+00],
#         [3.60000000e-03, 4.00000000e+00],
#         [4.00000000e-03, 4.00000000e+00],
#         [4.40000000e-03, 4.00000000e+00],
#         [4.80000000e-03, 4.00000000e+00],
#         [5.20000000e-03, 4.00000000e+00],
#         [5.60000000e-03, 4.00000000e+00],
#         [6.00000000e-03, 4.00000000e+00],
#         [6.40000000e-03, 4.00000000e+00],
#         [6.80000000e-03, 4.00000000e+00],
#         [7.20000000e-03, 4.00000000e+00],
#         [7.60000000e-03, 4.00000000e+00],
#         [8.00000000e-03, 4.00000000e+00],
#         [8.40000000e-03, 4.00000000e+00],
#         [8.80000000e-03, 4.00000000e+00],
#         [9.20000000e-03, 4.00000000e+00],
#         [9.60000000e-03, 4.00000000e+00],
#         [1.00000000e-02, 4.00000000e+00]]

# ORIG_NETLIST_PATH = r"C:\Users\User\capstone\csce483CapstoneSpring2025\netlists\InstermentalAmp.cir"
# TEST_NETLIST = Netlist(ORIG_NETLIST_PATH)
# TUNED_R = ["R1","R2","R3","R4","R5","R6","R7"]
# print([x.name for x in TEST_NETLIST.components])
# for component in TEST_NETLIST.components:
#     if component.name in TUNED_R:
#         component.variable = True
#         # component.maxVal = 2001

# # NODE_CONSTRAINTS = {"V(_NET3)":(None, 4.1)}
# NODE_CONSTRAINTS = {}

# curvefit_optimize(TARGET_VALUE, TEST_ROWS, TEST_NETLIST, WRITABLE_NETLIST_PATH, NODE_CONSTRAINTS)

