# XycLOps II: Automated Circuit Optimization Platform

**Version:** 2.0 (Fall 2025)  
**Backend Engine:** Xyce (Sandia National Labs)  
**Framework:** Python 3.10+ / Tkinter / SciPy

---

## 📖 Overview

XycLOps (**Xyc**e **L**oop **Op**timizer **s**ystem) is a desktop application that automates the tuning of analog circuit parameters. By interfacing with the **Xyce** parallel electronic simulator, it iteratively adjusts component values (resistors, capacitors, inductors) until the circuit's output matches a user-defined target curve.

**XycLOps II** represents a complete architectural overhaul, introducing support for **Multi-Physics Optimization** (Transient, AC, and Noise), interactive **Visual Target Editors**, and a modern, responsive user interface.

---

## ✨ Key Features in v2.0

* **Multi-Physics Support:** Optimize circuits for Time-Domain (Transient), Frequency Response (AC), and Noise Spectral Density.
* **Visual Target Editors:** Draw step responses and piecewise-linear curves interactively instead of manually creating CSV files. Includes a one-click "Apply to Target" workflow.
* **Modern UI:** A centralized theming engine provides a clean, professional interface with real-time plotting.
* **Workspace-Aware Logging:** Automated session management organizes logs and results into versioned folders (`netlist-results/<netlist>/<session>`).
* **Robust Parsing:** Enhanced support for LTSpice-style `.PARAM` definitions, complex netlist hierarchies, and UTF-8-SIG encoding.
* **Safe Execution:** Dedicated background threading for the solver ensures the UI never freezes, with a robust "Abort" capability.

---

## 🛠️ System Requirements

1. **Operating System:** Windows 10/11, macOS, or Linux.
2. **Python:** Version **3.10** or higher.
3. **Simulator:** Xyce must be installed and added to your system's `PATH`.
   * *Verification:* Open a terminal and type `Xyce -v`.

---

## 📦 Installation

It is recommended to run XycLOps II in a virtual environment to manage dependencies (`numpy`, `scipy`, `matplotlib`, `pillow`, etc.).

### 1. Setup Virtual Environment

**Windows:**
```powershell
# Create the environment
python -m venv xyclopsvenv

# Activate it
.\xyclopsvenv\Scripts\activate
```

**macOS / Linux:**
```bash
# Create the environment
python3 -m venv xyclopsvenv

# Activate it
source xyclopsvenv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🚀 Running the Application

To launch the XycLOps II user interface:

```bash
# Ensure your virtual environment is active!
python main_app.py
```

> **Note for Windows Users:** The application includes `multiprocessing.freeze_support()` handling, making it safe to package with PyInstaller if needed.

---

## 📖 User Workflows

### 1. Upload Netlist

* Click **"Upload Netlist"** and select a valid SPICE file (`.cir`, `.net`, `.txt`).
* The system parses components and automatically clears any stale state from previous sessions.

### 2. Parameter Selection

* The tool lists available components.
* Select the components (e.g., `R1`, `C3`) you want the optimizer to tune.

### 3. Optimization Settings

Choose your analysis type and configure targets:

#### 📈 Transient Analysis

* **Settings:** Configure `Stop Time`, `Time Step`, `Start Time`, and `Max Step`.
* **UIC:** Toggle "Use Initial Conditions" to bypass DC operating point calculation.
* **Target:** Use the **Heaviside Editor** to visually draw a step response target (e.g., 0V to 5V rise).

#### 🔊 AC Analysis

* **Settings:** Select **Sweep Type** (DEC/LIN/OCT) and frequency range (Start/Stop Hz).
* **Target:** Upload a CSV defining the target Bode plot (Gain vs. Frequency).
* **Response:** Optimize for **Magnitude (dB)** or **Phase**.

#### 📉 Noise Analysis

* **Settings:** Select **Output Node** (e.g., `V(out)`) and **Input Source**.
* **Target:** Define a target noise floor (e.g., `10 nV/√Hz`).
* **Quantity:** Optimize for **Output Noise** (`onoise`) or **Input Referred Noise** (`inoise`).

### 4. Run & Monitor

* Click **"Begin Optimization"**.
* The **Dashboard** shows a real-time plot of the simulation vs. your target.
* A **Sidebar** streams logs from the backend.
* A floating **Convergence Window** displays the real-time percentage improvement.

---

## 🔧 Developer Tools & Testing

XycLOps II includes utilities for profiling and regression testing.

### Startup Profiler

Diagnose slow launch times by measuring library import overhead:
```bash
python analyze_startup_time.py
```

### Stress Test Harnesses

Headless scripts located in `backend/manual_tests/` verify the solver engine without the UI.

*Transient Stress Test:*
```bash
python -m backend.manual_tests.long_instr_amp_test
```
*Optimizes a 7-variable Instrumentation Amplifier with strict tolerances (`10^{-14}`).*

*AC Stress Test:*
```bash
python -m backend.manual_tests.long_instr_amp_ac_test
```
*Performs frequency domain optimization from 10Hz to 1MHz.*

---

## 📂 Project Structure

* `main_app.py`: Application entry point.
* `frontend/`: UI code (Tkinter), including `ui_theme.py` and `visual_curve_editors.py`.
* `backend/`: Core logic. `curvefit_optimization.py` (Solver) and `netlist_parse.py` (SPICE Parser).
* `runs/`: Automatically generated session logs and result artifacts.

---

## ⚠️ Troubleshooting

* **"Xyce not found"**: Ensure the path to the Xyce executable is in your system Environment Variables.
* **Graph Flatlines**: Try enabling **"Default Bounds"** in the settings menu to give the optimizer a wider search space.
* **Slow Startup**: Run `analyze_startup_time.py` to identify if a specific library is causing delays.
