# csce483CapstoneSpring2025

Use a venv and the requirements.txt file

**make a virtual environment:** \
    python -m venv <venv name>

**open your virtual environment:**\
    .\<venv name>\Scripts\activate

**leave the virtual environment:** \
    exit

**install the requirements:** \
    pip install -r requirements.txt

**For Mac :** \
    python -m venv \
    source venv/bin/activate \
    exit

**To run the frontend in development:** \
  python -m frontend.main


## Long-Running Optimization Stress Test

Use the instrumentation amplifier stress harness to provoke a lengthy optimization run:

- Activate the virtual environment and install requirements (`pip install -r requirements.txt`).
- Ensure Xyce is available on your `PATH`.
- From the repository root run `python -m backend.manual_tests.long_instr_amp_test`.

The script consumes the dense waveform at `csv/instrumentation_amp_slow_target.csv`, widens resistor bounds, and tightens solver tolerances so the optimizer takes substantially longer than the default examples.

### AC Optimization Stress Test

- Upload `netlists/InstrumentationAmp.cir` in the UI.
- Select resistors R1_1, R1_2, R2_1, R2_2, R3_1, R3_2, RGAIN as variables.
- On the curve-fit screen choose `Upload` and load `csv/instrumentation_amp_ac_slow_target.csv`.
- Switch analysis type to AC, configure DEC sweep (200 points, 10 Hz start, 1e6 Hz stop) and set response to Magnitude (dB).
- Add constraints `VM(VOUT) <= 80` and `VM(VOUT) >= -140`, set xtol/gtol/ftol to `1e-14`, then run optimization.

Command-line equivalent: `python -m backend.manual_tests.long_instr_amp_ac_test`.
