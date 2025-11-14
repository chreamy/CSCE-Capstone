"""
Manual stress test harness that drives a long-running optimization using the
InstrumentationAmp netlist.

The goal is to feed the optimizer a dense 5k-point target waveform, widen the
component search bounds, and tighten the tolerances so that the least-squares
solver and Xyce spend considerably more time iterating.

Run this script from the project root after activating the virtual environment
with all requirements installed (numpy, scipy, etc.):

    python -m backend.manual_tests.long_instr_amp_test

Expect this run to take a while; it is intentionally configured to push the
optimizer hard and should be used sparingly as a regression/stress scenario.
"""

from __future__ import annotations

import csv
import os
from math import inf
from typing import Iterable, Tuple

from backend.netlist_parse import Netlist
from backend.optimization_process import optimizeProcess


TARGET_CSV = os.path.join("csv", "instrumentation_amp_slow_target.csv")
NETLIST_PATH = os.path.join("netlists", "InstrumentationAmp.cir")

# Tune every top-level resistor in the instrumentation amplifier front-end.
TUNABLE_COMPONENTS = [
    "R1_2",
    "R2_1",
    "R2_2",
    "R1_1",
    "R3_1",
    "R3_2",
    "RGAIN",
]


class ConsoleQueue:
    """Minimal queue-like object that prints optimizer messages to stdout.

    The production UI attaches a multiprocessing queue; for a manual test we
    only need to surface progress to the console while avoiding huge payloads
    (e.g., waveform arrays).
    """

    def __init__(self) -> None:
        self.total_logs = 0
        self.total_updates = 0
        self.ydata_updates = 0

    def put(self, item: Tuple[str, object]) -> None:
        kind, payload = item
        if kind == "UpdateYData":
            # Skip printing raw waveform arrays but keep a count.
            self.ydata_updates += 1
            return

        if kind == "Log":
            self.total_logs += 1
            print(f"[LOG] {payload}")
            return

        self.total_updates += 1
        print(f"[{kind}] {payload}")


def load_target_rows(target_csv_path: str) -> list[list[float]]:
    """Load a dense time-domain target curve from CSV."""
    rows: list[list[float]] = []
    with open(target_csv_path, newline="") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            try:
                time_val = float(row[0])
                voltage_val = float(row[1])
            except (IndexError, ValueError):
                continue
            rows.append([time_val, voltage_val])
    return rows


def configure_netlist(netlist: Netlist, tunable_names: Iterable[str]) -> list[str]:
    """Flag the requested components as variables and widen their bounds."""
    selected = []
    for component in netlist.components:
        if component.name not in tunable_names:
            continue
        original_value = component.value or 1.0
        component.variable = True
        # Widen bounds dramatically to expand the search space.
        component.minVal = max(original_value * 1e-2, 1e-3)
        component.maxVal = (
            original_value * 1e3
            if component.maxVal == inf
            else max(component.maxVal, original_value * 1e3)
        )
        component.modified = True
        selected.append(component.name)
    return selected


def build_curve_data() -> dict:
    """Construct curve/constraint payload mimicking frontend input."""
    return {
        "analysis_type": "transient",
        "x_parameter": "TIME",
        "y_units": "V",
        "y_parameter_expression": "V(VOUT)",
        "constraints": [
            {"type": "node", "left": "V(VOUT)", "operator": "<=", "right": "5.0"},
            {"type": "node", "left": "V(VOUT)", "operator": ">=", "right": "0.0"},
        ],
    }


def main() -> None:
    if not os.path.exists(TARGET_CSV):
        raise FileNotFoundError(f"Target CSV not found: {TARGET_CSV}")
    if not os.path.exists(NETLIST_PATH):
        raise FileNotFoundError(f"Instrumentation netlist not found: {NETLIST_PATH}")

    target_rows = load_target_rows(TARGET_CSV)
    if len(target_rows) < 1000:
        raise ValueError(
            f"Target curve is too small for the stress test ({len(target_rows)} rows)."
        )

    netlist = Netlist(NETLIST_PATH)
    selected_parameters = configure_netlist(netlist, TUNABLE_COMPONENTS)

    if not selected_parameters:
        raise RuntimeError("No tunable components were located in the netlist.")

    queue = ConsoleQueue()
    curve_data = build_curve_data()

    # Extremely tight tolerances encourage more iterations/search effort.
    optimization_tolerances = [1e-14, 1e-14, 1e-14]

    print("Starting instrumentation amplifier stress test...")
    print(f"  Target samples  : {len(target_rows)}")
    print(f"  Tunable parts   : {', '.join(selected_parameters)}")
    print(f"  Tolerances      : {optimization_tolerances}")
    print(f"  Netlist path    : {NETLIST_PATH}")
    print(f"  Target CSV path : {TARGET_CSV}")

    optimizeProcess(
        queue=queue,
        curveData=curve_data,
        testRows=target_rows,
        netlistPath=NETLIST_PATH,
        netlistObject=netlist,
        selectedParameters=selected_parameters,
        optimizationTolerances=optimization_tolerances,
        RLCBounds=[False, False, False],
    )

    print("\nStress test finished.")
    print(f"  Log messages   : {queue.total_logs}")
    print(f"  Other updates  : {queue.total_updates}")
    print(f"  Waveform pushes: {queue.ydata_updates}")


if __name__ == "__main__":
    main()
