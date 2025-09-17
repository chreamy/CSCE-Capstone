import tkinter as tk
from tkinter import ttk
import multiprocessing as mp
import threading as th
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

        # Main frame for centering content
        main_frame = ttk.Frame(self)
        main_frame.pack(expand=True, fill=tk.BOTH)
        self.complete_label = ttk.Label(main_frame, text="Optimization In Progress", font=("Arial", 16, "bold"))
        self.complete_label.grid(row=0, column=0, pady=20, padx=20, sticky="nsew")

        # Frame to contain treeview and scrollbar
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, pady=10, padx=20, sticky="nsew")

        # Treeview
        self.tree = ttk.Treeview(tree_frame, columns=("Parameter", "Value"), show="headings")
        self.tree.heading("Parameter", text="Parameter")
        self.tree.heading("Value", text="Value")
        self.tree.column("Parameter", anchor="w", width=200)
        self.tree.column("Value", anchor="w", width=150)
        self.tree.grid(row=0, column=0, sticky="nsew")

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Make the treeview expand inside its container
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Also expand the tree_frame in the main layout
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        curveData = self.controller.get_app_data("optimization_settings")
        testRows = self.controller.get_app_data("generated_data")
        netlistPath = self.controller.get_app_data("netlist_path")
        netlistObject = self.controller.get_app_data("netlist_object")
        selectedParameters = self.controller.get_app_data("selected_parameters")
        optimizationTolerances = self.controller.get_app_data("optimization_tolerances")
        RLCBounds = self.controller.get_app_data("RLC_bounds")

        self.figure = Figure(figsize=(5, 2), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Optimization Progress")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel(f"{curveData["y_parameter"]}")
        self.figure.subplots_adjust(bottom=0.2)
        self.line, = self.ax.plot([], [])  
        self.line2, = self.ax.plot([], [], color="red", linestyle="--", label="Second Line")
        xTargets=[]
        yTargets=[]
        for row in testRows:
            xTargets.append(row[0])
            yTargets.append(row[1])
        self.line2.set_data(xTargets,yTargets)
        range = max(yTargets) - min(yTargets)
        self.minBound = (min(yTargets)- max(range*0.25,1))
        self.maxBound = (max(yTargets)+ max(range*0.25,1))
        self.ax.set_ylim(self.minBound,self.maxBound)

        self.canvas = FigureCanvasTkAgg(self.figure, master=main_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=2, column=0, pady=10, padx=20, sticky="nsew")

        self.continue_button = ttk.Button(main_frame, text="Close", command=self.close_window)
        self.continue_button.grid(row=3, column=0, pady=5, padx=20)

        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_rowconfigure(3, weight=0)
        main_frame.grid_columnconfigure(0, weight=1)

        self.queue = mp.Queue()
        self.thread = th.Thread(
            target=optimizeProcess,
            args=(self.queue, curveData, testRows, netlistPath, netlistObject, selectedParameters, optimizationTolerances, RLCBounds)
        )
        self.thread.start()

        self.update_ui()

    def update_ui(self):
        try:
            while not self.queue.empty():
                msg_type, msg_value = self.queue.get_nowait()
                if msg_type == "Update":
                    self.tree.insert("", 0, values=("Update:", msg_value))
                elif msg_type == "Done":
                    self.tree.insert("", 0, values=("", msg_value))
                    self.complete_label.config(text="Optimization Complete")
                    return
                elif msg_type == "Failed":
                    self.tree.insert("", 0, values=("Optimization Failed", msg_value))
                elif msg_type == "UpdateNetlist":
                    self.controller.update_app_data("netlist_object", msg_value)
                elif msg_type == "UpdateOptimizationResults":
                    self.controller.update_app_data("optimization_results", msg_value)
                elif msg_type == "UpdateYData":
                    self.update_graph(msg_value)  
        except Exception as e:
            print("UI Update Error:", e)

        self.parent.after(100, self.update_ui)

    def update_graph(self, xy_data):
        data = tuple(xy_data)
        y_data = list(data[1])
        x_data = list(data[0])
        if isinstance(y_data, list):
            self.line.set_data(x_data, y_data)
            self.ax.relim()
            self.ax.autoscale_view()
            self.ax.set_ylim(min(self.minBound,min(y_data) - 1),max(self.maxBound,max(y_data) + 1))
            self.canvas.draw()

    def close_window(self):
        self.parent.quit()
