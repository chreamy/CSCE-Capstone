import numpy as np
import subprocess
import io
import sys
import os
from datetime import datetime
from scipy.optimize import least_squares
from scipy.interpolate import interp1d
from backend.xyce_parsing_function import parse_xyce_prn_output
from backend.netlist_parse import Netlist

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
def curvefit_optimize(target_value: str, target_curve_rows: list, netlist: Netlist, writable_netlist_path: str, node_constraints: dict, equality_part_constraints: list,queue, custom_xtol= 1e-12,custom_gtol= 1e-12,custom_ftol= 1e-12) -> None:
    # Get the session log file path
    session_log_file = get_session_log_file()
    
    # Initialize log file with session header
    session_start_time = datetime.now()
    log_to_file("="*80, session_log_file)
    log_to_file("Starting new optimization session", session_log_file)
    log_to_file(f"Session started at: {session_start_time.strftime('%Y-%m-%d %H:%M:%S')}", session_log_file)
    log_to_file(f"Target value: {target_value}", session_log_file)
    log_to_file(f"Netlist file: {writable_netlist_path}", session_log_file)
    log_to_file(f"Node constraints: {node_constraints}", session_log_file)
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
            log_and_append(f"Attempting to parse output file: {local_netlist_file}.prn", run_info, queue, session_log_file)
            xyce_parse = parse_xyce_prn_output(local_netlist_file + ".prn")
            log_and_append(f"Successfully parsed output file. Found {len(xyce_parse[1])} data points", run_info, queue, session_log_file)
            
            # Store this run's results
            all_run_results.append(run_info)

            # Assumes Xyce output is Index, Time, arb. # of VALUES
            row_index = xyce_parse[0].index(target_value.upper())

            X_ARRAY_FROM_XYCE = np.array([float(x[1]) for x in xyce_parse[1]])
            Y_ARRAY_FROM_XYCE = np.array([float(x[row_index]) for x in xyce_parse[1]])

            if run_state["first_run"]:
                run_state["first_run"] = False
                run_state["master_x_points"] = X_ARRAY_FROM_XYCE


            # Send run count update for every run
            queue.put(("Update",f"total runs completed: {xyceRuns}"))
            queue.put(("UpdateYData",(X_ARRAY_FROM_XYCE,Y_ARRAY_FROM_XYCE))) 

            xyce_interpolation = interp1d(X_ARRAY_FROM_XYCE, Y_ARRAY_FROM_XYCE)

            for node_name, (node_lower, node_upper) in node_constraints.items():
                node_index = xyce_parse[0].index(node_name.upper())
                node_values = np.array([float(x[node_index]) for x in xyce_parse[1]])
                if (node_lower is not None and np.any(node_values < node_lower)) or (node_upper is not None and np.any(node_values > node_upper)):
                    return np.full_like(run_state["master_x_points"], 1e6)  # TODO: Right now its just an arbitraritly large penalty

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