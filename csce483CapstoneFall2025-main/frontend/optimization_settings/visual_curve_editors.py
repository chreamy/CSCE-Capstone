import tkinter as tk
from tkinter import ttk
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ------------------------
# LINE editor (two points)
# ------------------------
def open_line_editor(owner, m, b, x0, x1, on_change, on_apply=None):
    """Open a draggable 2-point line editor.
    Args:
        owner: parent Tk widget
        m, b, x0, x1: floats (initial slope, intercept, range)
        on_change: callback(m, b, x0, x1) called on drag/release/apply
        on_apply: optional callback called when Apply is clicked (for auto-adding line)
    """
    if x1 <= x0:
        x1 = x0 + 1.0

    # initial endpoints
    y0 = m * x0 + b
    y1 = m * x1 + b

    win = tk.Toplevel(owner)
    win.title("Line Visual Editor")
    win.geometry("760x520")

    fig = Figure(figsize=(7.2, 4.2))
    ax = fig.add_subplot(111)
    ax.grid(True)
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    # ---- helper: set axes from current endpoints (no jitter while dragging) ----
    def _set_limits_line(xa, ya, xb, yb):
        xmin, xmax = (xa, xb) if xa <= xb else (xb, xa)
        ymin, ymax = (ya, yb) if ya <= yb else (yb, ya)
        px = 0.05 * (xmax - xmin if xmax > xmin else 1.0)
        py = 0.10 * (ymax - ymin if ymax > ymin else 1.0)
        ax.set_xlim(xmin - px, xmax + px)
        ax.set_ylim(ymin - py, ymax + py)

    _set_limits_line(x0, y0, x1, y1)

    (line_plot,) = ax.plot([x0, x1], [y0, y1], lw=2)
    pts = ax.scatter([x0, x1], [y0, y1], s=100, zorder=3)

    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # small toolbar for exact typing
    bar = ttk.Frame(win); bar.pack(fill=tk.X, padx=6, pady=4)
    v_m  = tk.StringVar(value=str(m))
    v_b  = tk.StringVar(value=str(b))
    v_x0 = tk.StringVar(value=str(x0))
    v_x1 = tk.StringVar(value=str(x1))
    for lab, var in [("Slope", v_m), ("Intercept", v_b), ("x0", v_x0), ("x1", v_x1)]:
        ttk.Label(bar, text=lab).pack(side=tk.LEFT, padx=(0,4))
        ttk.Entry(bar, width=10, textvariable=var).pack(side=tk.LEFT, padx=(0,12))
    ttk.Button(bar, text="Apply", command=lambda: _apply_line_inputs()).pack(side=tk.LEFT)

    selected = None  # 0 or 1 when dragging

    def _recalc_from_points(xa, ya, xb, yb):
        if xb == xa:
            xb = xa + 1e-9
        m_ = (yb - ya) / (xb - xa)
        b_ = ya - m_ * xa
        xa2, xb2 = (xa, xb) if xa <= xb else (xb, xa)
        ya2, yb2 = (ya, yb) if xa <= xb else (yb, ya)
        return m_, b_, xa2, xb2, ya2, yb2

    def _redraw_line_only(m_, b_, xa, xb):
        ya, yb = m_ * xa + b_, m_ * xb + b_
        line_plot.set_data([xa, xb], [ya, yb])
        pts.set_offsets(np.column_stack(([xa, xb], [ya, yb])))
        canvas.draw_idle()

    def _redraw_and_emit(m_, b_, xa, xb):
        _redraw_line_only(m_, b_, xa, xb)
        on_change(m_, b_, xa, xb)

    def _nearest_point(x, y):
        offs = pts.get_offsets()
        d0 = (offs[0,0]-x)**2 + (offs[0,1]-y)**2
        d1 = (offs[1,0]-x)**2 + (offs[1,1]-y)**2
        return 0 if d0 < d1 else 1

    def on_press(ev):
        nonlocal selected
        if ev.inaxes != ax: return
        selected = _nearest_point(ev.xdata, ev.ydata)

    def on_motion(ev):
        if selected is None or ev.inaxes != ax: return
        offs = pts.get_offsets()
        xs = offs[:,0].copy(); ys = offs[:,1].copy()
        xs[selected] = float(ev.xdata)
        ys[selected] = float(ev.ydata)
        m_, b_, xa, xb, ya, yb = _recalc_from_points(xs[0], ys[0], xs[1], ys[1])
        # no autoscale while dragging:
        _redraw_line_only(m_, b_, xa, xb)
        # update toolbar fields continuously
        v_m.set(f"{m_}"); v_b.set(f"{b_}"); v_x0.set(f"{xa}"); v_x1.set(f"{xb}")

    def on_release(ev):
        nonlocal selected, m, b, x0, x1
        if selected is None: return
        selected = None
        offs = pts.get_offsets()
        m, b, x0, x1, ya, yb = _recalc_from_points(offs[0,0], offs[0,1], offs[1,0], offs[1,1])
        # rescale **after** the drag ends:
        _set_limits_line(x0, m * x0 + b, x1, m * x1 + b)
        _redraw_and_emit(m, b, x0, x1)
        v_m.set(f"{m}"); v_b.set(f"{b}"); v_x0.set(f"{x0}"); v_x1.set(f"{x1}")

    def _apply_line_inputs():
        nonlocal m, b, x0, x1
        try:
            m  = float(v_m.get()); b = float(v_b.get())
            x0 = float(v_x0.get()); x1 = float(v_x1.get())
        except ValueError:
            return
        if x1 <= x0: x1 = x0 + 1e-6
        # rescale when Apply is clicked:
        _set_limits_line(x0, m * x0 + b, x1, m * x1 + b)
        _redraw_and_emit(m, b, x0, x1)
        # Call on_apply callback if provided (for auto-adding line)
        if on_apply:
            on_apply(m, b, x0, x1)
        # Close the visual editor window after applying
        win.destroy()

    fig.canvas.mpl_connect("button_press_event", on_press)
    fig.canvas.mpl_connect("motion_notify_event", on_motion)
    fig.canvas.mpl_connect("button_release_event", on_release)

    # initial emit so caller can sync immediately
    on_change(m, b, x0, x1)


# ------------------------
# HEAVISIDE editor
# ------------------------
def open_heaviside_editor(owner, amp, t0, x1, on_change, on_apply=None):
    """Open a heaviside step editor."""
    if x1 <= t0:
        x1 = t0 + 1.0

    win = tk.Toplevel(owner)
    win.title("Heaviside Visual Editor")
    win.geometry("760x520")

    fig = Figure(figsize=(7.2, 4.2))
    ax = fig.add_subplot(111)
    ax.grid(True); ax.set_xlabel("t"); ax.set_ylabel("v")

    def _set_limits_step(a, t_start, x_end):
        px = 0.05 * max(1.0, (x_end - t_start))
        ymin = min(0.0, a); ymax = max(0.0, a)
        py = 0.2 * max(1.0, abs(ymax - ymin))
        ax.set_xlim(t_start - px, x_end + px)
        ax.set_ylim(ymin - py - 0.5, ymax + py + 0.5)

    xs = np.linspace(t0, x1, 200)
    ys = np.where(xs >= t0, amp, 0.0)
    (step_plot,) = ax.plot(xs, ys, lw=2)
    vline = ax.axvline(t0, ls="--", lw=1.5)
    (amp_pt,) = ax.plot([t0 + 0.05*(x1 - t0)], [amp], "o", ms=8)

    _set_limits_step(amp, t0, x1)

    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    bar = ttk.Frame(win); bar.pack(fill=tk.X, padx=6, pady=4)
    v_amp = tk.StringVar(value=str(amp))
    v_t0  = tk.StringVar(value=str(t0))
    v_x1  = tk.StringVar(value=str(x1))
    for lab, var in [("Amplitude", v_amp), ("t0", v_t0), ("x1", v_x1)]:
        ttk.Label(bar, text=lab).pack(side=tk.LEFT, padx=(0,4))
        ttk.Entry(bar, width=10, textvariable=var).pack(side=tk.LEFT, padx=(0,12))
    ttk.Button(bar, text="Apply", command=lambda: _apply_vals()).pack(side=tk.LEFT)

    dragging = None  # "amp" or "t0"

    def _redraw_emit(a, t_start, x_end):
        xs = np.linspace(t_start, x_end, 200)
        ys = np.where(xs >= t_start, a, 0.0)
        step_plot.set_data(xs, ys)
        vline.set_xdata([t_start, t_start])
        amp_pt.set_data([t_start + 0.05*(x_end - t_start)], [a])
        canvas.draw_idle()
        on_change(a, t_start, x_end)

    def on_press(ev):
        nonlocal dragging
        if ev.inaxes != ax: return
        px, py = amp_pt.get_data()
        if abs(ev.xdata - px[0]) < 0.03*(x1 - t0) and abs(ev.ydata - py[0]) < 0.1*max(1.0, abs(amp)):
            dragging = "amp"
        elif abs(ev.xdata - t0) < 0.02*(x1 - t0):
            dragging = "t0"

    def on_motion(ev):
        nonlocal amp, t0
        if dragging is None or ev.inaxes != ax: return
        if dragging == "amp":
            amp = float(ev.ydata)
            v_amp.set(str(amp))
        elif dragging == "t0":
            t0 = min(float(ev.xdata), x1 - 1e-6)
            v_t0.set(str(t0))
        _redraw_emit(amp, t0, x1)

    def on_release(ev):
        nonlocal dragging
        dragging = None
        # rescale **after** drag ends
        _set_limits_step(float(v_amp.get()), float(v_t0.get()), float(v_x1.get()))

    def _apply_vals():
        nonlocal amp, t0, x1
        try:
            amp = float(v_amp.get()); t0 = float(v_t0.get()); x1 = float(v_x1.get())
        except ValueError:
            return
        if x1 <= t0: x1 = t0 + 1e-6
        # rescale when Apply is clicked:
        _set_limits_step(amp, t0, x1)
        _redraw_emit(amp, t0, x1)
        # Call on_apply callback if provided (for auto-adding step)
        if on_apply:
            on_apply(amp, t0, x1)
        # Close the visual editor window after applying
        win.destroy()

    fig.canvas.mpl_connect("button_press_event", on_press)
    fig.canvas.mpl_connect("motion_notify_event", on_motion)
    fig.canvas.mpl_connect("button_release_event", on_release)

    on_change(amp, t0, x1)