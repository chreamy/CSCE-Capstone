# CAPSTONE

### AC Optimization Stress Test

- Upload `netlists/InstrumentationAmp.cir` in the UI.
- Pick the same resistor set as variable parameters.
- On the curve-fit screen choose `Upload` and load `csv/instrumentation_amp_ac_slow_target.csv`.
- Switch analysis type to AC, set the sweep to DEC with 200 points, start 10 Hz, stop 1e6 Hz, response Magnitude (dB).
- Add `VM(VOUT) <= 80` and `VM(VOUT) >= -140` constraints, set xtol/gtol/ftol to `1e-14`, then run optimization.

From the command line you can mirror this scenario with `python -m backend.manual_tests.long_instr_amp_ac_test`.
