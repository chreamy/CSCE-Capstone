"""
Manual stress test harness for a long-running AC optimization on the
InstrumentationAmp netlist. It mirrors the transient stress test but targets an
AC magnitude response with thousands of frequency samples and tight solver
settings.

Run from the project root (after activating the required virtual environment
and installing dependencies such as numpy/scipy) via:

    python -m backend.manual_tests.long_instr_amp_ac_test

Expect this to take a long time; it is designed as a heavy regression scenario.
"""

from __future__ import annotations

import csv
import os
from math import inf
from typing import Iterable, Tuple

from backend.netlist_parse import Netlist
from backend.optimization_process import optimizeProcess


TARGET_CSV = os.path.join("csv", "instrumentation_amp_ac_slow_target.csv")
NETLIST_PATH = os.path.join("netlists", "InstrumentationAmp.cir")

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
    """Minimal queue-like object that prints optimizer messages to stdout."""

    def __init__(self) -> None:
        self.total_logs = 0
        self.total_updates = 0
        self.ydata_updates = 0

    def put(self, item: Tuple[str, object]) -> None:
        kind, payload = item
        if kind == "UpdateYData":
            self.ydata_updates += 1
            return
        if kind == "Log":
            self.total_logs += 1
            print(f"[LOG] {payload}")
            return
        self.total_updates += 1
        print(f"[{kind}] {payload}")


def load_target_rows(target_csv_path: str) -> list[list[float]]:
    rows: list[list[float]] = []
    with open(target_csv_path, newline="") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            try:
                freq_val = float(row[0])
                gain_val = float(row[1])
            except (IndexError, ValueError):
                continue
            rows.append([freq_val, gain_val])
    return rows


def configure_netlist(netlist: Netlist, tunable_names: Iterable[str]) -> list[str]:
    selected = []
    for component in netlist.components:
        if component.name not in tunable_names:
            continue
        nominal = component.value or 1.0
        component.variable = True
        component.minVal = max(nominal * 1e-2, 1e-3)
        component.maxVal = (
            nominal * 1e3 if component.maxVal == inf else max(component.maxVal, nominal * 1e3)
        )
        component.modified = True
        selected.append(component.name)
    return selected


def build_curve_data() -> dict:
    return {
        "analysis_type": "ac",
        "x_parameter": "FREQ",
        "y_units": "dB",
        "y_parameter_expression": "VM(VOUT)",
        "constraints": [
            {"type": "node", "left": "VM(VOUT)", "operator": "<=", "right": "80.0"},
            {"type": "node", "left": "VM(VOUT)", "operator": ">=", "right": "-140.0"},
        ],
        "ac_settings": {
            "sweep_type": "DEC",
            "points": 200,
            "start_frequency": 10.0,
            "stop_frequency": 1_000_000.0,
            "response": "magnitude_db",
        },
    }


def main() -> None:
    if not os.path.exists(TARGET_CSV):
        raise FileNotFoundError(f"Target CSV not found: {TARGET_CSV}")
    if not os.path.exists(NETLIST_PATH):
        raise FileNotFoundError(f"Instrumentation netlist not found: {NETLIST_PATH}")

    target_rows = load_target_rows(TARGET_CSV)
    if len(target_rows) < 1000:
        raise ValueError(f"Target curve is too small for the stress test ({len(target_rows)} rows).")

    netlist = Netlist(NETLIST_PATH)
    selected_parameters = configure_netlist(netlist, TUNABLE_COMPONENTS)
    if not selected_parameters:
        raise RuntimeError("No tunable components were located in the netlist.")

    queue = ConsoleQueue()
    curve_data = build_curve_data()
    tolerances = [1e-14, 1e-14, 1e-14]

    print("Starting instrumentation amplifier AC stress test...")
    print(f"  Target samples  : {len(target_rows)}")
    print(f"  Tunable parts   : {', '.join(selected_parameters)}")
    print(f"  Tolerances      : {tolerances}")
    print(f"  Netlist path    : {NETLIST_PATH}")
    print(f"  Target CSV path : {TARGET_CSV}")

    optimizeProcess(
        queue=queue,
        curveData=curve_data,
        testRows=target_rows,
        netlistPath=NETLIST_PATH,
        netlistObject=netlist,
        selectedParameters=selected_parameters,
        optimizationTolerances=tolerances,
        RLCBounds=[False, False, False],
    )

    print("\nStress test finished.")
    print(f"  Log messages   : {queue.total_logs}")
    print(f"  Other updates  : {queue.total_updates}")
    print(f"  Waveform pushes: {queue.ydata_updates}")


if __name__ == "__main__":
    main()
