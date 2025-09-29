import numpy as np
import subprocess
import io
import sys
from scipy.optimize import least_squares
from scipy.interpolate import interp1d
from backend.xyce_parsing_function import parse_xyce_prn_output
from backend.netlist_parse import Netlist

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
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()  # Redirect output

    try:
        global xyceRuns
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
            subprocess.run(["Xyce", "-delim", "COMMA", "-quiet", local_netlist_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            #TODO: Smart way to set timestep and ensure consistency. Rn just decided arbitrarily by first run
            xyce_parse = parse_xyce_prn_output(local_netlist_file + ".prn")

            # Assumes Xyce output is Index, Time, arb. # of VALUES
            row_index = xyce_parse[0].index(target_value.upper())

            X_ARRAY_FROM_XYCE = np.array([float(x[1]) for x in xyce_parse[1]])
            Y_ARRAY_FROM_XYCE = np.array([float(x[row_index]) for x in xyce_parse[1]])

            if run_state["first_run"]:
                run_state["first_run"] = False
                run_state["master_x_points"] = X_ARRAY_FROM_XYCE


            if (xyceRuns % 5 == 0):
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

        sys.stdout.flush()
        captured = sys.stdout.getvalue()
        lines = captured.split("\n")
        line = next((item for item in lines if item.startswith("Function evaluations")), None)
        values = line.split()
        leastSquaresIterations = int(values[2].rstrip(","))
        initialCost = float(values[5].rstrip(","))
        finalCost = float(values[8].rstrip(","))
        optimality = float(values[11].rstrip("."))

    finally:
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