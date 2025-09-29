
import shutil
import numpy as np
from backend.curvefit_optimization import curvefit_optimize

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
    

def add_node_constraints(constraints):
    formattedNodeConstraints = {}
    nodes = {}
    for constraint in constraints:
        if constraint["type"] == "node":
            nodes[constraint["left"].strip()] = [None,None]
    for constraint in constraints:
        if constraint["type"] == "node":
            match constraint["operator"]:
                        case ">=":
                            nodes[constraint["left"].strip()][0] = float(constraint["right"].strip())
                        case "<=":
                            nodes[constraint["left"].strip()][1] = float(constraint["right"].strip())
    for node in nodes:
        formattedNodeConstraints[node] = (nodes[node][0],nodes[node][1])
    return formattedNodeConstraints

def optimizeProcess(queue,curveData,testRows,netlistPath,netlistObject,selectedParameters,optimizationTolerances,RLCBounds):
    try:        
        TARGET_VALUE = curveData["y_parameter"]
        TEST_ROWS = testRows
        ORIG_NETLIST_PATH = netlistPath
        NETLIST = netlistObject
        WRITABLE_NETLIST_PATH = ORIG_NETLIST_PATH[:-4]+"Copy.txt"
        NODE_CONSTRAINTS = add_node_constraints(curveData["constraints"]) 

        print(f"TARGET_VALUE = {TARGET_VALUE}")
        print(f"ORIG_NETLIST_PATH = {ORIG_NETLIST_PATH}")
        print(f"NETLIST.file_path = {NETLIST.file_path}")
        print(f"WRIITABLE_NETLIST_PATH = {WRITABLE_NETLIST_PATH}")

        #UPDATE NETLIST BASED ON OPTIMIZATION SETTINGS AND CONSTRAINTS
        for component in NETLIST.components:
            if component.name in selectedParameters:
                component.variable = True

        #ADD IN INITIAL CONSTRAINTS TO NETLIST CLASS VIA MINVAL MAXVAL
        EQUALITY_PART_CONSTRAINTS = add_part_constraints(curveData["constraints"], NETLIST)

        #ADD DEFAULT BOUNDS IF USER WANTS THEM FOR COMPONENT TYPE AND THEY HAVEN'T BEEN SPECIFIED BY OTHER CONSTRAINT
        for component in NETLIST.components:
            match component.type:
                case "R":
                    if (RLCBounds[0]):
                        if component.minVal == -1:
                            component.minVal = component.value/10
                        if component.maxVal == np.inf:
                            component.maxVal = component.value*10
                case "L":
                    if (RLCBounds[1]):
                        if component.minVal == -1:
                            component.minVal = component.value/10
                        if component.maxVal == np.inf:
                            component.maxVal = component.value*10
                case "C":
                    if (RLCBounds[2]):
                        if component.minVal == -1:
                            component.minVal = component.value/10
                        if component.maxVal == np.inf:
                            component.maxVal = component.value*10
            #If min is still -1 after match statement (Case where no bound specified in a constraint and default bounds not desired by user) set to 0.
            if component.minVal == -1:
                component.minVal = 0

        endValue = max([sublist[0] for sublist in TEST_ROWS])
        initValue = min([sublist[0] for sublist in TEST_ROWS])
        shutil.copyfile(NETLIST.file_path, WRITABLE_NETLIST_PATH)
        NETLIST.class_to_file(WRITABLE_NETLIST_PATH)
        CONSTRAINED_NODES = []
        for constraint in curveData["constraints"]:
            if constraint["type"] == "node":
                if constraint["left"].strip() != TARGET_VALUE:
                    CONSTRAINED_NODES.append(constraint["left"].strip())
        NETLIST.writeTranCmdsToFile(WRITABLE_NETLIST_PATH,(endValue- initValue)/ 100,endValue,initValue,(endValue- initValue)/ 100,TARGET_VALUE,CONSTRAINED_NODES)
        #Optimization Call
        optim = curvefit_optimize(TARGET_VALUE, TEST_ROWS, NETLIST, WRITABLE_NETLIST_PATH, NODE_CONSTRAINTS, EQUALITY_PART_CONSTRAINTS,queue,optimizationTolerances[0],optimizationTolerances[1],optimizationTolerances[2])

        #Update AppData
        queue.put(("UpdateNetlist",NETLIST))
        queue.put(("UpdateOptimizationResults",optim))
        
        print(f"Optimization Results: {optim}")
        queue.put(("Update", "Optimization Complete!"))
        queue.put(("Update", f"Optimality: {optim[4]}"))
        queue.put(("Update", f"Final Cost: {optim[3]}"))
        queue.put(("Update", f"Initial Cost: {optim[2]}"))
        queue.put(("Update", f"Least Squares Iterations: {optim[1]}"))
        queue.put(("Update", f"Total Xyce Runs: {optim[0]}"))
        queue.put(("Done", f"Optimization Results:"))
    except Exception as e:
        queue.put(("Failed",f"{e}"))