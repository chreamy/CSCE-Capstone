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
3. **Simulator:** Xyce must be installed and added to your system’s `PATH`.
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

```bash
# Ensure your virtual environment is active!
python main_app.py
```

> **Note for Windows Users:** `multiprocessing.freeze_support()` makes it safe to package with PyInstaller.

---

## 📖 User Workflows

### 1. Upload Netlist
* Click **"Upload Netlist"** and select a valid SPICE file (`.cir`, `.net`, `.txt`).
* The system parses components and resets stale session state.

### 2. Parameter Selection
* The tool lists all tunable components.
* Select parts (e.g., `R1`, `C3`) for parameter optimization.

### 3. Optimization Settings

#### 📈 Transient Analysis
* Configure: `Stop Time`, `Time Step`, `Start Time`, `Max Step`
* Toggle **UIC** to skip operating point calculation
* Set a visual target using the **Heaviside Editor**

#### 🔊 AC Analysis
* Configure sweep type (**DEC/LIN/OCT**) and frequency range
* Upload a target Bode CSV (Gain vs. Frequency)
* Response metric: **Magnitude (dB)** or **Phase**

#### 📉 Noise Analysis
* Select **Output Node** and **Input Source**
* Target a noise spectrum (e.g., `10 nV/√Hz`)
* Optimize **onoise** or **inoise**

### 4. Run & Monitor
* Click **Begin Optimization**
* Real-time simulation overlay on target plot
* Live backend logs in sidebar
* A convergence window shows optimization progress

---

## 🔧 Developer Tools & Testing

### Startup Profiler
```bash
python analyze_startup_time.py
```

### Stress Test Harnesses
Located in `backend/manual_tests/`

*Transient Test*
```bash
python -m backend.manual_tests.long_instr_amp_test
```

*AC Test*
```bash
python -m backend.manual_tests.long_instr_amp_ac_test
```

---

## 📂 Project Structure

* `main_app.py` — Application entry
* `frontend/` — UI (Tkinter)  
* `backend/` — Optimization + netlist parsing  
* `runs/` — Auto-generated outputs & logs

---

## ⚠️ Troubleshooting

* **“Xyce not found”** → Ensure Xyce is added to PATH
* **Flatlined graph** → Enable **Default Bounds**
* **Slow startup** → Use `analyze_startup_time.py`
