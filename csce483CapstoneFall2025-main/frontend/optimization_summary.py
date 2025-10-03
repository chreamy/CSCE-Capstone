import tkinter as tk
from tkinter import ttk
import multiprocessing as mp
import threading as th
from typing import Optional
from backend.optimzation_process import optimizeProcess

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class OptimizationSummary(tk.Frame):

    def __init__(self, parent: tk.Tk, controller: "AppController"):
        super().__init__(parent)
        self.controller = controller
        self.parent = parent
        self.parent.title("Optimization In Progress")
        self.pack(fill=tk.BOTH, expand=True)

        self.queue: Optional[mp.Queue] = None
        self.thread: Optional[th.Thread] = None
        self.optimization_active = False

        main_frame = ttk.Frame(self)
        main_frame.pack(expand=True, fill=tk.BOTH)
        self.main_frame = main_frame
        self.complete_label = ttk.Label(
            main_frame,
            text="Optimization In Progress",
            font=("Arial", 16, "bold"),
        )
        self.complete_label.grid(row=0, column=0, pady=20, padx=20, sticky="nsew")

        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, pady=10, padx=20, sticky="nsew")

        self.tree = ttk.Treeview(
            tree_frame, columns=("Parameter", "Value"), show="headings"
        )
        self.tree.heading("Parameter", text="Parameter")
        self.tree.heading("Value", text="Value")
        self.tree.column("Parameter", anchor="w", width=200)
        self.tree.column("Value", anchor="w", width=150)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        self._load_context()
        self._prepare_target_data()
        self._build_plot()

        self.back_to_settings_button = ttk.Button(
            main_frame,
            text="Modify Settings",
            command=self.return_to_settings,
            state=tk.DISABLED,
        )
        self.back_to_settings_button.grid(row=3, column=0, pady=5, padx=20, sticky="w")

        self.continue_button = ttk.Button(
            main_frame,
            text="Close",
            command=self.close_window,
        )
        self.continue_button.grid(row=3, column=0, pady=5, padx=20, sticky="e")

        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_rowconfigure(3, weight=0)

        self.parent.after(100, self.update_ui)
        self.start_optimization()

    def _load_context(self) -> None:
        self.curveData = self.controller.get_app_data("optimization_settings") or {}
        self.testRows = self.controller.get_app_data("generated_data") or []
        self.netlistPath = self.controller.get_app_data("netlist_path")
        self.netlistObject = self.controller.get_app_data("netlist_object")
        self.selectedParameters = self.controller.get_app_data("selected_parameters")
        self.optimizationTolerances = self.controller.get_app_data("optimization_tolerances")
        self.RLCBounds = self.controller.get_app_data("RLC_bounds")

    def _prepare_target_data(self) -> None:
        self.target_x = []
        self.target_y = []
        if self.testRows:
            self.target_x = [row[0] for row in self.testRows]
            self.target_y = [row[1] for row in self.testRows]
            range_y = max(self.target_y) - min(self.target_y)
            margin = max(range_y * 0.25, 1)
            self.minBound = min(self.target_y) - margin
            self.maxBound = max(self.target_y) + margin
        else:
            self.minBound = 0
            self.maxBound = 1

    def _build_plot(self) -> None:
        self.figure = Figure(figsize=(5, 2), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Optimization Progress")
        self.ax.set_xlabel("Time")
        y_label = self.curveData.get("y_parameter", "")
        self.ax.set_ylabel(f"{y_label}")
        self.figure.subplots_adjust(bottom=0.2)
        self.line, = self.ax.plot([], [], label="Simulation")
        self.line2, = self.ax.plot(
            [], [], color="red", linestyle="--", label="Target"
        )
        if self.target_x and self.target_y:
            self.line2.set_data(self.target_x, self.target_y)
        self.ax.set_ylim(self.minBound, self.maxBound)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.main_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(
            row=2, column=0, pady=10, padx=20, sticky="nsew"
        )

    def start_optimization(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self._load_context()
        self._prepare_target_data()
        self._update_target_plot()
        self.back_to_settings_button.config(state=tk.DISABLED)
        self.optimization_active = True
        self._reset_status_view()
        self.queue = mp.Queue()
        self.thread = th.Thread(
            target=optimizeProcess,
            args=(
                self.queue,
                self.curveData,
                self.testRows,
                self.netlistPath,
                self.netlistObject,
                self.selectedParameters,
                self.optimizationTolerances,
                self.RLCBounds,
            ),
            daemon=True,
        )
        self.thread.start()

    def _update_target_plot(self) -> None:
        if hasattr(self, "line2"):
            if self.target_x and self.target_y:
                self.line2.set_data(self.target_x, self.target_y)
            else:
                self.line2.set_data([], [])
            self.ax.set_ylim(self.minBound, self.maxBound)
            if hasattr(self, "canvas"):
                self.canvas.draw()

    def _reset_status_view(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.complete_label.config(text="Optimization In Progress")
        if hasattr(self, "line"):
            self.line.set_data([], [])
        self.ax.set_ylim(self.minBound, self.maxBound)
        if hasattr(self, "canvas"):
            self.canvas.draw()

    def _cleanup_worker(self) -> None:
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.1)
        self.thread = None
        if self.queue is not None:
            try:
                self.queue.close()
            except Exception:
                pass
            finally:
                self.queue = None
        self.optimization_active = False

    def return_to_settings(self) -> None:
        self._cleanup_worker()
        self.controller.navigate("optimization_settings")

    def update_ui(self) -> None:
        try:
            if self.queue:
                while not self.queue.empty():
                    msg_type, msg_value = self.queue.get_nowait()
                    if msg_type == "Update":
                        self.tree.insert("", 0, values=("Update:", msg_value))
                    elif msg_type == "Done":
                        self.tree.insert("", 0, values=("", msg_value))
                        self.complete_label.config(text="Optimization Complete")
                        self.optimization_active = False
                        self.back_to_settings_button.config(state=tk.NORMAL)
                    elif msg_type == "Failed":
                        self.tree.insert(
                            "", 0, values=("Optimization Failed", msg_value)
                        )
                        self.complete_label.config(text="Optimization Failed")
                        self.optimization_active = False
                        self.back_to_settings_button.config(state=tk.NORMAL)
                    elif msg_type == "UpdateNetlist":
                        self.controller.update_app_data("netlist_object", msg_value)
                    elif msg_type == "UpdateOptimizationResults":
                        self.controller.update_app_data(
                            "optimization_results", msg_value
                        )
                    elif msg_type == "UpdateYData":
                        self.update_graph(msg_value)
        except Exception as e:
            print("UI Update Error:", e)

        if not self.optimization_active:
            self._cleanup_worker()

        self.parent.after(100, self.update_ui)

    def update_graph(self, xy_data) -> None:
        data = tuple(xy_data)
        y_data = list(data[1])
        x_data = list(data[0])
        self.line.set_data(x_data, y_data)
        self.ax.relim()
        self.ax.autoscale_view()
        if y_data:
            lower = min(self.minBound, min(y_data) - 1)
            upper = max(self.maxBound, max(y_data) + 1)
        else:
            lower = self.minBound
            upper = self.maxBound
        self.ax.set_ylim(lower, upper)
        self.canvas.draw()

    def close_window(self) -> None:
        self.parent.quit()
