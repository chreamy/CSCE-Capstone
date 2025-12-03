import tkinter as tk
from tkinter import ttk, StringVar, BooleanVar, simpledialog
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from ..ui_theme import (
    COLORS,
    create_primary_button,
    create_secondary_button,
    apply_modern_theme,
)


def _apply_axis_labels(ax, axis_labels):
    """
    Apply contextual axis labels if provided, otherwise fall back to x/y.
    """
    if axis_labels and len(axis_labels) == 2:
        x_label = axis_labels[0] or "x"
        y_label = axis_labels[1] or "y"
    else:
        x_label = "x"
        y_label = "y"
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)

class LegacyConstraintsBar:
    """
    Matches your 'Add Constraint' dialog:
      Left (combobox) | Operator (=, >=, <=) | Right | From x | To x
    - Saves a dict: {"left", "op", "right", "x_start", "x_end"}
    - Previews on the graph ONLY if Left matches the current Y signal (e.g. V(out)).
    """
    def __init__(self, parent, ax, *,
                 left_options,
                 current_y_signal,
                 on_save_constraint=None,
                 default_x_range=None):
        self.ax = ax
        self.left_options = left_options or []
        self.current_y_signal = (current_y_signal or "").strip()
        self.on_save_constraint = on_save_constraint
        self._overlay_artists = []

        x0, x1 = default_x_range if default_x_range else ax.get_xbound()

        self.frame = ttk.Frame(parent, style="Card.TFrame")

        row = ttk.Frame(self.frame, style="Card.TFrame"); row.pack(fill="x", pady=4)

        ttk.Label(row, text="Left:").pack(side="left")
        self.left = ttk.Combobox(row, values=self.left_options, state="readonly", width=16)
        if self.left_options:
            self.left.current(0)
        self.left.pack(side="left", padx=(4,10))

        ttk.Label(row, text="Operator:").pack(side="left")
        self.op_var = StringVar(value="=")
        ttk.Radiobutton(row, text="=",  variable=self.op_var, value="=", style="TRadiobutton").pack(side="left")
        ttk.Radiobutton(row, text=">=", variable=self.op_var, value=">=", style="TRadiobutton").pack(side="left")
        ttk.Radiobutton(row, text="<=", variable=self.op_var, value="<=", style="TRadiobutton").pack(side="left")

        ttk.Label(row, text="Right:").pack(side="left", padx=(12,4))
        self.right = tk.Entry(row, width=10); self.right.pack(side="left")

        ttk.Label(row, text="From x:").pack(side="left", padx=(12,4))
        self.x0 = tk.Entry(row, width=8); self.x0.insert(0, str(x0)); self.x0.pack(side="left")
        ttk.Label(row, text="To x:").pack(side="left", padx=(6,4))
        self.x1 = tk.Entry(row, width=8); self.x1.insert(0, str(x1)); self.x1.pack(side="left")

        btns = ttk.Frame(self.frame, style="Card.TFrame"); btns.pack(fill="x", pady=4)
        create_secondary_button(btns, text="Preview on Graph", command=self._preview).pack(side="left")
        create_secondary_button(btns, text="Clear Previews", command=self._clear).pack(side="left", padx=6)
        create_primary_button(btns, text="Save to Constraints", command=self._save).pack(side="left", padx=10)

        self.note = ttk.Label(
            self.frame,
            foreground=COLORS["text_secondary"],
            text="Preview enabled only when Left matches current Y (e.g., V(node)).",
            style="Hint.TLabel",
        )
        self.note.pack(anchor="w")

    def _clear(self):
        for a in self._overlay_artists:
            try: a.remove()
            except: pass
        self._overlay_artists.clear()
        self.ax.figure.canvas.draw_idle()

    def _preview(self):
        try:
            left = (self.left.get() or "").strip()
            op   = self.op_var.get()
            val  = float(self.right.get())
            x0   = float(self.x0.get()); x1 = float(self.x1.get())
            if x0 > x1:
                x0, x1 = x1, x0

            # Ensure the time window is visible
            ax_x0, ax_x1 = self.ax.get_xbound()
            self.ax.set_xbound(min(ax_x0, x0), max(ax_x1, x1))

            # Decide emphasis: strong if plotting same Y, faint otherwise
            matches_y = bool(self.current_y_signal) and \
                        left.upper() == self.current_y_signal.upper()
            alpha_band = 0.18 if matches_y else 0.07
            line_style = "-" if matches_y else "--"

            # Ensure horizontal value is within view
            ylo, yhi = self.ax.get_ybound()
            if op == "=":
                ylo = min(ylo, val - 1e-6); yhi = max(yhi, val + 1e-6)
            else:
                ylo = min(ylo, val); yhi = max(yhi, val)
            self.ax.set_ybound(ylo, yhi)

            # Draw overlay
            if op == "=":
                eps = max(1e-6, 0.002*(yhi - ylo))
                r = Rectangle((x0, val - eps), x1 - x0, 2*eps, alpha=alpha_band, edgecolor=None)
                self.ax.add_patch(r); self._overlay_artists.append(r)
                ln, = self.ax.plot([x0, x1], [val, val], linestyle=line_style)
                self._overlay_artists.append(ln)
            elif op == ">=":
                ln, = self.ax.plot([x0, x1], [val, val], linestyle=line_style)
                self._overlay_artists.append(ln)
                top = self.ax.get_ybound()[1]
                r = Rectangle((x0, val), x1 - x0, top - val, alpha=alpha_band, edgecolor=None)
                self.ax.add_patch(r); self._overlay_artists.append(r)
            elif op == "<=":
                ln, = self.ax.plot([x0, x1], [val, val], linestyle=line_style)
                self._overlay_artists.append(ln)
                bottom = self.ax.get_ybound()[0]
                r = Rectangle((x0, bottom), x1 - x0, val - bottom, alpha=alpha_band, edgecolor=None)
                self.ax.add_patch(r); self._overlay_artists.append(r)

            self.ax.figure.canvas.draw_idle()
        except Exception as e:
            print("Preview error:", e)

    def preview_constraint(self, constraint: dict):
        """External callers can feed a saved constraint to re-draw it."""
        if not constraint:
            return
        self.left.set(constraint.get("left", ""))
        self.op_var.set(constraint.get("operator", "="))
        self.right.delete(0, tk.END)
        self.right.insert(0, str(constraint.get("right", "")))
        self.x0.delete(0, tk.END); self.x0.insert(0, str(constraint.get("x_start", "")))
        self.x1.delete(0, tk.END); self.x1.insert(0, str(constraint.get("x_end", "")))
        self._preview()

    def _save(self):
        if not callable(self.on_save_constraint):
            return
        try:
            cdict = {
                "left":  (self.left.get() or "").strip(),
                "op":    self.op_var.get(),
                "right": float(self.right.get()),
                "x_start": float(self.x0.get()),
                "x_end":   float(self.x1.get()),
            }
            self.on_save_constraint(cdict)
        except Exception as e:
            print("Save constraint error:", e)


# ------------------------
# HEAVISIDE editor (single step)
# ------------------------
def open_heaviside_editor(owner, a_init, t0_init, x1_init, on_change=None, on_apply=None, on_save_constraint=None, axis_labels=None, constraint_left_options=None, current_y_signal=None):
    """
    Numeric-first API to match curve_fit_settings:
      a_init, t0_init, x1_init : floats
      on_change(a,t0,x1)  -> called on every live change
      on_apply(a,t0,x1)   -> called when user clicks Apply
    """
    win = tk.Toplevel(owner)
    win.title("Heaviside Editor")
    win.geometry("860x560")
    apply_modern_theme(win)
    win.configure(bg=COLORS["bg_primary"])

    fig = Figure(figsize=(7.8, 4.2))
    ax = fig.add_subplot(111); ax.grid(True); _apply_axis_labels(ax, axis_labels)
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas_widget = canvas.get_tk_widget()
    canvas_widget.configure(bg=COLORS["bg_primary"], highlightthickness=0)
    canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    bar = ttk.Frame(win, style="Card.TFrame"); bar.pack(fill=tk.X, padx=8, pady=6)

    ttk.Label(bar, text="Amplitude:", style="Secondary.TLabel").pack(side=tk.LEFT)
    v_a = tk.StringVar(value=str(a_init))
    ttk.Entry(bar, width=10, textvariable=v_a).pack(side=tk.LEFT, padx=(4, 12))

    ttk.Label(bar, text="Start x0:", style="Secondary.TLabel").pack(side=tk.LEFT)
    v_x0 = tk.StringVar(value=str(t0_init))
    ttk.Entry(bar, width=10, textvariable=v_x0).pack(side=tk.LEFT, padx=(4, 12))

    ttk.Label(bar, text="End x1:", style="Secondary.TLabel").pack(side=tk.LEFT)
    v_x1 = tk.StringVar(value=str(x1_init))
    ttk.Entry(bar, width=10, textvariable=v_x1).pack(side=tk.LEFT, padx=(4, 12))

    # NEW: autoscale toggle + Fit button
    autoscale = tk.BooleanVar(value=False)  # NEW
    ttk.Checkbutton(bar, text="Auto-rescale", variable=autoscale, style="TCheckbutton").pack(side=tk.LEFT, padx=(8, 6))
    def _fit():
        _redraw(rescale=True, emit=False)
    ttk.Button(bar, text="Fit", command=_fit, style="Secondary.TButton").pack(side=tk.LEFT, padx=(2, 8))



    # Create the embedded constraints panel
    bar = LegacyConstraintsBar(
        parent=win,                         # or the frame/shell holding your buttons
        ax=ax,
        left_options=constraint_left_options or [],
        current_y_signal=current_y_signal or "",
        on_save_constraint=on_save_constraint,
        default_x_range=ax.get_xbound()
    )
    if hasattr(owner, "controller"):
        setattr(owner.controller, "constraint_preview", bar.preview_constraint)

    bar.frame.pack(fill="x", padx=8, pady=6)

    # State
    drag = {"amp": False, "t0": False}

    step_line = None
    t0_vline = None
    amp_handle = None

    def _ensure_artists():
        nonlocal step_line, t0_vline, amp_handle
        if step_line is None:
            step_line, = ax.plot([], [], lw=2)
        if t0_vline is None:
            t0_vline = ax.axvline(0.0, ls="--", lw=1.2)
        if amp_handle is None:
            amp_handle = ax.scatter([], [], s=90, zorder=3, picker=6)  # NEW: easier to grab

    def _get_vals():
        return float(v_a.get()), float(v_x0.get()), float(v_x1.get())

    def _stair_xy(a, t0, x1):
        xs = np.linspace(t0, x1, 200)
        ys = np.where(xs >= t0, a, 0.0)
        return xs, ys

    def _bounds(a, t0, x1):
        X, Y = _stair_xy(a, t0, x1)
        xmin, xmax = float(min(X)), float(max(X))
        ymin, ymax = float(min(Y)), float(max(Y))
        if xmax <= xmin: xmax = xmin + 1.0
        px = 0.08 * (xmax - xmin)
        py = 0.25 * max(1.0, abs(ymax - ymin))
        return xmin - px, xmax + px, ymin - py, ymax + py

    def _redraw(rescale=False, emit=True):
        _ensure_artists()
        try:
            a, t0, x1 = _get_vals()
        except ValueError:
            canvas.draw_idle(); return

        if x1 <= t0:
            x1 = t0 + 1e-6
            v_x1.set(str(x1))

        X, Y = _stair_xy(a, t0, x1)
        step_line.set_data(X, Y)
        t0_vline.set_xdata([t0, t0])
        # handle is a small dot near the plateau
        hx = t0 + 0.1 * (x1 - t0)
        amp_handle.set_offsets(np.c_[[hx], [a]])

        if rescale or autoscale.get():  # NEW: only rescale when asked or toggled
            xmin, xmax, ymin, ymax = _bounds(a, t0, x1)
            ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax)

        _apply_axis_labels(ax, axis_labels)
        canvas.draw_idle()
        if emit and on_change:
            on_change(a, t0, x1)

    # Drag handlers
    def _press(ev):
        if ev.inaxes != ax: return
        try:
            a, t0, x1 = _get_vals()
        except ValueError:
            return
        # hit-test near amplitude handle first
        hx = t0 + 0.1 * (x1 - t0)
        tol_x = 0.03 * max(1.0, x1 - t0)
        tol_y = 0.12 * max(1.0, abs(a) if a != 0 else 1.0)
        if abs(ev.xdata - hx) < tol_x and abs(ev.ydata - a) < tol_y:
            drag["amp"] = True; drag["t0"] = False; return
        # else check near the t0 vertical
        if abs(ev.xdata - t0) < 0.02 * max(1.0, x1 - t0):
            drag["t0"] = True; drag["amp"] = False; return

    def _motion(ev):
        if ev.inaxes != ax: return
        try:
            a, t0, x1 = _get_vals()
        except ValueError:
            return
        if drag["amp"]:
            a = float(ev.ydata); v_a.set(str(a))
        elif drag["t0"]:
            t0 = min(float(ev.xdata), x1 - 1e-6); v_x0.set(str(t0))
        _redraw(rescale=False, emit=True)  # NEW: stable limits while dragging

    def _release(_ev):
        drag["amp"] = drag["t0"] = False
        _redraw(rescale=False, emit=True)

    def _apply():
        try:
            a, t0, x1 = _get_vals()
        except ValueError:
            return
        if on_apply:
            on_apply(a, t0, x1)
        _redraw(rescale=True, emit=True)

    fig.canvas.mpl_connect("button_press_event", _press)
    fig.canvas.mpl_connect("motion_notify_event", _motion)
    fig.canvas.mpl_connect("button_release_event", _release)

    for var in (v_a, v_x0, v_x1):
        var.trace_add("write", lambda *_: _redraw(rescale=False, emit=True))

    _redraw(rescale=True, emit=True)


# ------------------------
# PIECEWISE-LINEAR editor
# ------------------------
def open_piecewise_editor(owner, pts_init, on_change=None, on_apply=None, on_save_constraint=None, axis_labels=None, constraint_left_options=None, current_y_signal=None):
    """
    pts_init : list[(x,y)]
    on_change(new_pts) called whenever points change (drag, insert, remove, apply)
    on_apply(new_pts) called when the user clicks Apply/Use in target
    """
    win = tk.Toplevel(owner)
    win.title("Piecewise Linear Editor")
    win.geometry("900x610")
    apply_modern_theme(win)
    win.configure(bg=COLORS["bg_primary"])

    # --- figure & axes
    fig = Figure(figsize=(7.9, 4.3))
    ax = fig.add_subplot(111); ax.grid(True); _apply_axis_labels(ax, axis_labels)
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas_widget = canvas.get_tk_widget()
    canvas_widget.configure(bg=COLORS["bg_primary"], highlightthickness=0)
    canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # --- toolbar (entries + buttons)
    bar = ttk.Frame(win, style="Card.TFrame"); bar.pack(fill=tk.X, padx=8, pady=6)

    # CHANGED: “Add Point” now uses the fields and appends (x-sorted)
    ttk.Button(bar, text="Add Point", command=lambda: _insert_from_fields(append=True), style="Secondary.TButton").pack(side=tk.LEFT, padx=(0,6))
    ttk.Button(bar, text="Remove Point", command=lambda: _remove_selected(), style="Secondary.TButton").pack(side=tk.LEFT, padx=(0,12))

    ttk.Label(bar, text="x:", style="Secondary.TLabel").pack(side=tk.LEFT)
    v_x = tk.StringVar(value="")
    e_x = ttk.Entry(bar, width=12, textvariable=v_x); e_x.pack(side=tk.LEFT, padx=(4,10))

    ttk.Label(bar, text="y:", style="Secondary.TLabel").pack(side=tk.LEFT)
    v_y = tk.StringVar(value="")
    e_y = ttk.Entry(bar, width=12, textvariable=v_y); e_y.pack(side=tk.LEFT, padx=(4,10))

    # NEW: autoscale toggle + Fit button
    autoscale = tk.BooleanVar(value=True)  # NEW: default ON for PWL
    ttk.Checkbutton(bar, text="Auto-rescale", variable=autoscale, style="TCheckbutton").pack(side=tk.LEFT, padx=(4,6))  # NEW
    ttk.Button(bar, text="Fit", command=lambda: _redraw(rescale=True, emit=False), style="Secondary.TButton").pack(side=tk.LEFT, padx=(2,10))  # NEW
    create_primary_button(bar, text="Apply to Target", command=lambda: _apply_current()).pack(side=tk.RIGHT, padx=(8, 0))

    bar = LegacyConstraintsBar(
        parent=win,                         # or the frame/shell holding your buttons
        ax=ax,
        left_options=constraint_left_options or [],
        current_y_signal=current_y_signal or "",
        on_save_constraint=on_save_constraint,
        default_x_range=ax.get_xbound()
    )
    if hasattr(owner, "controller"):
        setattr(owner.controller, "constraint_preview", bar.preview_constraint)
    bar.frame.pack(fill="x", padx=8, pady=6)
    # --- table
    table = ttk.Treeview(win, columns=("idx","x","y"), show="headings", height=7)
    for c, w, a in (("idx", 60, "center"), ("x", 220, "w"), ("y", 220, "w")):
        table.heading(c, text=c)
        table.column(c, width=w, anchor=a)
    table.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))

    # --- state
    pts = sorted([(float(x), float(y)) for (x, y) in (pts_init or [(0.0, 0.0), (1.0, 1.0)])], key=lambda p: p[0])
    drag = {"i": None}
    line_artist = None
    scatter_artist = None

    def _ensure_artists():
        nonlocal line_artist, scatter_artist
        if line_artist is None:
            line_artist, = ax.plot([], [], "-o", lw=2, ms=7, color="#d33")
        if scatter_artist is None:
            scatter_artist = ax.scatter([], [], s=70, zorder=3, color="#d33")

    def _refresh_table(select_idx=None):
        table.delete(*table.get_children())
        for i, (x, y) in enumerate(pts):
            table.insert("", "end", values=(i, f"{x}", f"{y}"))
        if select_idx is not None and 0 <= select_idx < len(pts):
            rowid = table.get_children()[select_idx]
            table.selection_set(rowid)
            table.see(rowid)

    # --- axis helpers -------------------------------------------------------
    def _set_limits():
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        if xmax <= xmin: xmax = xmin + 1.0
        pad_x = 0.08 * (xmax - xmin)
        pad_y = 0.25 * max(1.0, abs(ymax - ymin))
        ax.set_xlim(xmin - pad_x, xmax + pad_x)
        ax.set_ylim(ymin - pad_y, ymax + pad_y)

    def _expand_to_fit(x, y):
        """NEW: expand axes if (x,y) is out of view, with gentle padding."""
        xlim = ax.get_xlim(); ylim = ax.get_ylim()
        need = False
        xmin, xmax = xlim; ymin, ymax = ylim
        if x <= xmin or x >= xmax:
            span = max(1e-9, xmax - xmin)
            pad = 0.08 * span
            xmin = min(xmin, x) - pad if x <= xmin else xmin
            xmax = max(xmax, x) + pad if x >= xmax else xmax
            need = True
        if y <= ymin or y >= ymax:
            span = max(1.0, abs(ymax - ymin))
            pad = 0.25 * span
            ymin = min(ymin, y) - pad if y <= ymin else ymin
            ymax = max(ymax, y) + pad if y >= ymax else ymax
            need = True
        if need:
            ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax)

    # --- core redraw
    def _redraw(rescale=False, emit=True, select_idx=None):
        _ensure_artists()
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        line_artist.set_data(xs, ys)
        scatter_artist.set_offsets(np.c_[xs, ys])
        ax.grid(True)
        _apply_axis_labels(ax, axis_labels)
        if rescale or autoscale.get():  # NEW
            _set_limits()
        canvas.draw_idle()
        _refresh_table(select_idx=select_idx)
        if emit and on_change: on_change(list(pts))

    def _emit():
        if on_change: on_change(list(pts))

    def _apply_current():
        _emit()
        if callable(on_apply):
            on_apply(list(pts))

    def _selected_index():
        sel = table.selection()
        if not sel: return None
        return table.index(sel[0])

    def _remove_selected():
        i = _selected_index()
        if i is None or len(pts) <= 2:
            return
        pts.pop(i)
        _redraw(rescale=False, emit=True, select_idx=max(0, i-1))

    # ---------- INSERT HELPERS ----------
    def _insert_sorted(x, y, preferred_index=None):
        new_pt = (float(x), float(y))
        # x-sorted insertion
        idx = 0
        while idx < len(pts) and pts[idx][0] <= new_pt[0]:
            idx += 1
        if preferred_index is not None:
            idx = max(0, min(idx, len(pts)))
            if 0 < preferred_index < len(pts):
                if new_pt[0] <= pts[preferred_index][0]:
                    idx = min(idx, preferred_index)
                else:
                    idx = max(idx, preferred_index)
        pts.insert(idx, new_pt)
        # NEW: expand axes if out of view (when autoscale is OFF)
        if not autoscale.get():
            _expand_to_fit(new_pt[0], new_pt[1])
        return idx

    # --- mouse interactions --------------------------------------------------
    def _on_press(ev):
        if ev.inaxes != ax: return
        if ev.dblclick:
            _add_point_at_click(ev)  # NEW
        else:
            _start_drag(ev)

    def _start_drag(ev):
        if ev.inaxes != ax: return
        xs = [p[0] for p in pts]
        if not xs: return
        i = int(np.argmin(np.abs(np.array(xs) - float(ev.xdata))))
        drag["i"] = i

    def _on_motion(ev):
        if ev.inaxes != ax or drag["i"] is None: return
        i = drag["i"]
        # monotone x
        x_left  = pts[i-1][0] + 1e-9 if i > 0 else -np.inf
        x_right = pts[i+1][0] - 1e-9 if i < len(pts)-1 else np.inf
        new_x = float(np.clip(ev.xdata, x_left, x_right))
        new_y = float(ev.ydata)
        pts[i] = (new_x, new_y)
        if not autoscale.get():
            _expand_to_fit(new_x, new_y)  # NEW: keep visible while dragging
        _redraw(rescale=False, emit=True, select_idx=i)

    def _on_release(_ev):
        drag["i"] = None
        _redraw(rescale=False, emit=True)

    # NEW: double-click add (also supports outside current span)
    def _add_point_at_click(ev):
        x_click = float(ev.xdata)
        xs = [p[0] for p in pts]
        # inside span -> interpolate on that segment
        if xs[0] < x_click < xs[-1]:
            i = max(0, min(len(pts)-2, np.searchsorted(xs, x_click) - 1))
            x0, y0 = pts[i]; x1, y1 = pts[i+1]
            t = (x_click - x0) / max(1e-12, (x1 - x0))
            y_click = y0 + t * (y1 - y0)
            ins_idx = i + 1
            pts.insert(ins_idx, (x_click, y_click))
            if not autoscale.get():
                _expand_to_fit(x_click, y_click)
            _redraw(rescale=False, emit=True, select_idx=ins_idx)
            return
        # left/outside -> add at left end with left y
        if x_click <= xs[0]:
            y_click = pts[0][1]
            pts.insert(0, (x_click, y_click))
            if not autoscale.get():
                _expand_to_fit(x_click, y_click)
            _redraw(rescale=False, emit=True, select_idx=0)
            return
        # right/outside -> add at right end with right y
        if x_click >= xs[-1]:
            y_click = pts[-1][1]
            pts.append((x_click, y_click))
            if not autoscale.get():
                _expand_to_fit(x_click, y_click)
            _redraw(rescale=False, emit=True, select_idx=len(pts)-1)

    # ADDED: Insert via fields (before selected row if any; append otherwise)
    def _insert_from_fields(append):
        try:
            x = float(v_x.get()); y = float(v_y.get())
        except ValueError:
            return
        sel = _selected_index()
        preferred = None if append else sel
        idx = _insert_sorted(x, y, preferred_index=preferred)
        _redraw(rescale=(autoscale.get()), emit=True, select_idx=idx)  # NEW

    # --- wire events
    fig.canvas.mpl_connect("button_press_event", _on_press)
    fig.canvas.mpl_connect("motion_notify_event", _on_motion)
    fig.canvas.mpl_connect("button_release_event", _on_release)

    # initial draw
    _set_limits()
    _redraw(rescale=False, emit=True, select_idx=0)
    
    def _edit_point(idx):
        if not (0 <= idx < len(pts)):
            return
        x_old, y_old = pts[idx]
        new_x = simpledialog.askfloat("Edit Point", "x value:", parent=win, initialvalue=x_old)
        if new_x is None:
            return
        new_y = simpledialog.askfloat("Edit Point", "y value:", parent=win, initialvalue=y_old)
        if new_y is None:
            return
        pts.pop(idx)  # remove old entry
        insert_idx = _insert_sorted(new_x, new_y, preferred_index=idx)  # keeps the list x-sorted
        _redraw(rescale=False, emit=True, select_idx=insert_idx)

    def _on_table_double_click(_event):
        sel = _selected_index()
        if sel is not None:
            _edit_point(sel)

    table.bind("<Double-1>", _on_table_double_click)


def _constraint_dict_from_fields(kind, name, y_min, y_max, x0, x1, hard, weight, target_signal):
    c = {
        "name": name or "constraint",
        "type": kind,  # "range" | "upper" | "lower"
        "x_start": float(x0),
        "x_end": float(x1),
        "target_signal": target_signal,
        "hard": bool(hard),
        "weight": float(weight) if weight not in ("", None) else 1.0,
    }
    if kind == "range":
        c["y_min"] = float(y_min)
        c["y_max"] = float(y_max)
    elif kind == "upper":
        c["y_max"] = float(y_max)
    elif kind == "lower":
        c["y_min"] = float(y_min)
    return c

def _draw_constraint_overlay(ax, cdict, artists_bucket):
    """
    Draw translucent overlays for the constraint on given axes.
    artists_bucket: list to retain patches/lines so we can clear them later.
    """
    xs, xe = cdict["x_start"], cdict["x_end"]
    kind = cdict["type"]

    # normalize: always show as a rectangle over the time window
    if kind == "range":
        ymin, ymax = cdict["y_min"], cdict["y_max"]
        rect = Rectangle((xs, ymin), xe - xs, ymax - ymin, alpha=0.15, edgecolor=None)
        ax.add_patch(rect); artists_bucket.append(rect)
        # outline
        ax.plot([xs, xe], [ymin, ymin], linestyle="--"); artists_bucket.append(ax.lines[-1])
        ax.plot([xs, xe], [ymax, ymax], linestyle="--"); artists_bucket.append(ax.lines[-1])
    elif kind == "upper":
        ymax = cdict["y_max"]
        # fill from ymax up to current top just to indicate forbidden region
        top = ax.get_ylim()[1]
        rect = Rectangle((xs, ymax), xe - xs, top - ymax, alpha=0.10, edgecolor=None)
        ax.add_patch(rect); artists_bucket.append(rect)
        ax.plot([xs, xe], [ymax, ymax], linestyle="--"); artists_bucket.append(ax.lines[-1])
    elif kind == "lower":
        ymin = cdict["y_min"]
        bottom = ax.get_ylim()[0]
        rect = Rectangle((xs, bottom), xe - xs, ymin - bottom, alpha=0.10, edgecolor=None)
        ax.add_patch(rect); artists_bucket.append(rect)
        ax.plot([xs, xe], [ymin, ymin], linestyle="--"); artists_bucket.append(ax.lines[-1])

    ax.figure.canvas.draw_idle()
