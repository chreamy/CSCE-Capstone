import tkinter as tk
from tkinter import ttk
import queue
import threading as th
from typing import Optional
from backend.optimization_process import optimizeProcess
from datetime import datetime
import math
import numpy as np

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .ui_theme import COLORS as THEME_COLORS, apply_modern_theme


class OptimizationSummary(tk.Frame):
    COLORS = THEME_COLORS

    def __init__(self, parent: tk.Tk, controller: "AppController"):
        super().__init__(parent)
        self.controller = controller
        self.parent = parent
        self.parent.title("Optimization Dashboard")
        # Set minimum window size to accommodate sidebar
        self.parent.minsize(800, 600)
        self.pack(fill=tk.BOTH, expand=True)

        self.queue: Optional[queue.Queue] = None
        self.thread: Optional[th.Thread] = None
        self.optimization_active = False
        self.sidebar_visible = False
        self.realtime_logs = []
        self.convergence_window = tk.Toplevel(self.parent)
        self.convergence_window.title("Convergence")
        self.convergence_window.geometry("240x150")
        self.convergence_window.transient(self.parent)
        self.convergence_window.resizable(False, False)
        self.convergence_label = tk.Label(
            self.convergence_window,
            text="Convergence: -- %",
            font=("Segoe UI", 12)
        )
        self.convergence_label.pack(padx=20, pady=(18, 5))
        self.error_label = tk.Label(
            self.convergence_window,
            text="Max Error: --\nRMS Error: --",
            font=("Segoe UI", 11)
        )
        self.error_label.pack(padx=20, pady=(0, 12))
        self.convergence_window.protocol("WM_DELETE_WINDOW", lambda: None)
        self._graph_update_counter = 0
        self._message_batch_limit = 40
        self._initial_cost: Optional[float] = None
        self._latest_simulation = None

        # Configure main container
        self.configure(bg=self.COLORS['bg_primary'])
        
        # Create main layout
        self._create_main_layout()
        self._create_sidebar()
        self._create_status_cards()
        self._create_plot_section()
        self._create_control_buttons()
        
        # Load data and start
        self._load_context()
        self._prepare_target_data()
        self._build_plot()
        
        self.parent.after(100, self.update_ui)
        self.start_optimization()
        
        # Bind window resize event to maintain proper layout
        self.parent.bind('<Configure>', self._on_window_resize)

    def _create_main_layout(self):
        """Create the main layout container"""
        # Main content area
        self.content_frame = tk.Frame(self, bg=self.COLORS['bg_primary'])
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Don't propagate size changes to parent
        self.content_frame.pack_propagate(False)
        
        # Header
        self.header_frame = tk.Frame(self.content_frame, bg=self.COLORS['bg_secondary'], height=80, relief=tk.FLAT, bd=1)
        self.header_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        self.header_frame.pack_propagate(False)
        
        # Status label
        self.status_label = tk.Label(
            self.header_frame,
            text="Optimization In Progress",
            font=("Segoe UI", 24, "bold"),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_secondary']
        )
        self.status_label.pack(side=tk.LEFT, padx=30, pady=20)
        
        # Toggle sidebar button
        self.sidebar_toggle = tk.Button(
            self.header_frame,
            text="📋 Logs",
            font=("Segoe UI", 12),
            bg=self.COLORS['accent'],
            fg=self.COLORS['text_primary'],
            bd=1,
            relief=tk.FLAT,
            padx=20,
            pady=10,
            command=self._toggle_sidebar,
            cursor="hand2"
        )
        self.sidebar_toggle.pack(side=tk.RIGHT, padx=30, pady=20)

    def _create_sidebar(self):
        """Create the collapsible sidebar for logs"""
        self.sidebar = tk.Frame(self, bg=self.COLORS['sidebar_bg'], width=300, relief=tk.FLAT, bd=1)
        # Prevent sidebar from expanding beyond its specified width
        self.sidebar.pack_propagate(False)
        
        # Sidebar header
        sidebar_header = tk.Frame(self.sidebar, bg=self.COLORS['bg_tertiary'], height=60, relief=tk.FLAT, bd=1)
        sidebar_header.pack(fill=tk.X, padx=0, pady=0)
        sidebar_header.pack_propagate(False)
        
        tk.Label(
            sidebar_header,
            text="Real-time Logs",
            font=("Segoe UI", 16, "bold"),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_tertiary']
        ).pack(side=tk.LEFT, padx=20, pady=15)
        
        
        # Close sidebar button
        close_btn = tk.Button(
            sidebar_header,
            text="✕",
            font=("Segoe UI", 14),
            bg=self.COLORS['bg_tertiary'],
            fg=self.COLORS['text_secondary'],
            bd=1,
            relief=tk.FLAT,
            command=self._toggle_sidebar,
            cursor="hand2"
        )
        close_btn.pack(side=tk.RIGHT, padx=20, pady=15)
        
        # Logs container
        logs_container = tk.Frame(self.sidebar, bg=self.COLORS['log_bg'])
        logs_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Logs text widget
        self.logs_text = tk.Text(
            logs_container,
            bg=self.COLORS['log_bg'],
            fg=self.COLORS['text_primary'],
            font=("Consolas", 10),
            wrap=tk.WORD,
            bd=1,
            relief=tk.FLAT,
            padx=15,
            pady=15,
            state=tk.DISABLED
        )
        
        # Scrollbar for logs
        logs_scrollbar = tk.Scrollbar(logs_container, orient="vertical", command=self.logs_text.yview)
        self.logs_text.configure(yscrollcommand=logs_scrollbar.set)
        
        self.logs_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        logs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_status_cards(self):
        """Create status display for optimization progress and results"""
        self.status_display_frame = tk.Frame(self.content_frame, bg=self.COLORS['bg_primary'])
        self.status_display_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Main status container
        self.status_container = tk.Frame(self.status_display_frame, bg=self.COLORS['bg_secondary'], relief=tk.FLAT, bd=1)
        self.status_container.pack(fill=tk.X, padx=5)
        
        # Computing message and loading indicator
        self.computing_frame = tk.Frame(self.status_container, bg=self.COLORS['bg_secondary'])
        self.computing_frame.pack(fill=tk.X, pady=20)
        
        # Loading indicator (spinning circle)
        self.loading_label = tk.Label(
            self.computing_frame,
            text="◐",
            font=("Segoe UI", 24),
            bg=self.COLORS['bg_secondary'],
            fg=self.COLORS['accent']
        )
        self.loading_label.pack(pady=(0, 10))
        
        # Computing message
        self.computing_label = tk.Label(
            self.computing_frame,
            text="Xyce computing...",
            font=("Segoe UI", 16, "bold"),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_secondary']
        )
        self.computing_label.pack()
        
        # Run count display
        self.run_count_label = tk.Label(
            self.computing_frame,
            text="Runs: 0",
            font=("Segoe UI", 14),
            fg=self.COLORS['accent'],
            bg=self.COLORS['bg_secondary']
        )
        self.run_count_label.pack(pady=(5, 0))
        
        # Results display (initially hidden)
        self.results_frame = tk.Frame(self.status_container, bg=self.COLORS['bg_secondary'])
        
        # Results title
        self.results_title = tk.Label(
            self.results_frame,
            text="Optimization Results",
            font=("Segoe UI", 16, "bold"),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_secondary']
        )
        self.results_title.pack(pady=(20, 10))
        
        # Results display
        self.results_label = tk.Label(
            self.results_frame,
            text="",
            font=("Consolas", 14, "bold"),
            fg=self.COLORS['success'],
            bg=self.COLORS['bg_secondary'],
            justify=tk.CENTER
        )
        self.results_label.pack(pady=(0, 10))
        
        # Action buttons in results frame
        self.results_buttons_frame = tk.Frame(self.results_frame, bg=self.COLORS['bg_secondary'])
        self.results_buttons_frame.pack(pady=(0, 20))
        
        # Restart button
        self.restart_button = tk.Button(
            self.results_buttons_frame,
            text="Restart",
            font=("Segoe UI", 12),
            bg=self.COLORS['success'],
            fg=self.COLORS['text_primary'],
            bd=1,
            relief=tk.FLAT,
            padx=25,
            pady=12,
            command=self.restart_optimization,
            cursor="hand2"
        )
        self.restart_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Close button
        self.close_button = tk.Button(
            self.results_buttons_frame,
            text="Close",
            font=("Segoe UI", 12),
            bg=self.COLORS['accent'],
            fg=self.COLORS['text_primary'],
            bd=1,
            relief=tk.FLAT,
            padx=25,
            pady=12,
            command=self.close_window,
            cursor="hand2"
        )
        self.close_button.pack(side=tk.LEFT)
        
        # Initialize with computing state
        self._show_computing_state()

    def _show_computing_state(self):
        """Show the computing state with loading indicator"""
        self.computing_frame.pack(fill=tk.X, pady=20)
        self.results_frame.pack_forget()
        self.run_count_label.config(text="Runs: 0")
        self._animate_loading()

    def _show_results_state(self, results):
        """Show the final optimization results"""
        self.computing_frame.pack_forget()
        self.results_frame.pack(fill=tk.X, pady=20)
        
        # Format results as requested: [10, 2, 17189.0, 17189.0, 9.54e-13]
        results_text = str(results)
        self.results_label.config(text=results_text)
        if isinstance(results, (list, tuple)) and len(results) >= 4:
            try:
                initial_cost = float(results[2])
                final_cost = float(results[3])
            except (TypeError, ValueError):
                initial_cost = None
                final_cost = None
            if initial_cost is not None:
                self._update_convergence_label(initial_cost, final_cost)
                self._update_error_label()


    def _update_convergence_label(self, initial_cost: float, final_cost: float) -> None:
        label = getattr(self, 'convergence_label', None)
        if label is None:
            return
        try:
            if initial_cost and initial_cost != 0:
                improvement = (initial_cost - final_cost) / abs(initial_cost) * 100.0
            else:
                improvement = 0.0
        except Exception:
            improvement = 0.0
        improvement = max(0.0, improvement)
        label.config(text=f"Convergence: {improvement:.2f} %")
        self._initial_cost = initial_cost

    def _update_error_label(self) -> None:
        label = getattr(self, "error_label", None)
        if label is None:
            return
        if not hasattr(self, "target_x") or not hasattr(self, "target_y"):
            return
        if not self.target_x or not self.target_y:
            return
        data = getattr(self, "_latest_simulation", None)
        if not data:
            return
        x_data, y_data = data
        if not x_data or not y_data:
            return
        try:
            target_interp = np.interp(x_data, self.target_x, self.target_y)
            diff = np.array(y_data) - target_interp
            max_err = float(np.max(np.abs(diff)))
            rms_err = float(np.sqrt(np.mean(diff ** 2)))
        except Exception:
            label.config(text="Max Error: --\nRMS Error: --")
            return
        label.config(text=f"Max Error: {max_err:.3g}\nRMS Error: {rms_err:.3g}")

    def _animate_loading(self):
        """Animate the loading indicator with spinning icons"""
        if hasattr(self, 'loading_label') and self.optimization_active:
            # Use spinning/rotating symbols that are closer together
            symbols = ["◐", "◓", "◑", "◒"]  # Spinning circle segments
            current_symbol = self.loading_label.cget("text")
            try:
                current_index = symbols.index(current_symbol)
                next_index = (current_index + 1) % len(symbols)
            except ValueError:
                next_index = 0
            
            self.loading_label.config(text=symbols[next_index])
            # Faster animation for smoother spinning effect
            self.parent.after(150, self._animate_loading)

    def _create_plot_section(self):
        """Create the plot section"""
        self.plot_frame = tk.Frame(self.content_frame, bg=self.COLORS['bg_secondary'], relief=tk.FLAT, bd=1)
        self.plot_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Plot title
        tk.Label(
            self.plot_frame,
            text="Optimization Progress",
            font=("Segoe UI", 16, "bold"),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_secondary']
        ).pack(pady=(20, 10))

    def _create_control_buttons(self):
        """Create control buttons"""
        self.buttons_frame = tk.Frame(self.content_frame, bg=self.COLORS['bg_primary'])
        self.buttons_frame.pack(fill=tk.X, padx=20, pady=(10, 20))
        
        # Modify Settings button (shown during optimization)
        self.back_to_settings_button = tk.Button(
            self.buttons_frame,
            text="Modify Settings",
            font=("Segoe UI", 12),
            bg=self.COLORS['bg_tertiary'],
            fg=self.COLORS['text_primary'],
            bd=1,
            relief=tk.FLAT,
            padx=25,
            pady=12,
            command=self.return_to_settings,
            state=tk.DISABLED,
            cursor="hand2"
        )
        self.back_to_settings_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Restart button (shown when optimization is complete)
        self.restart_button = tk.Button(
            self.buttons_frame,
            text="Restart",
            font=("Segoe UI", 12),
            bg=self.COLORS['success'],
            fg=self.COLORS['text_primary'],
            bd=1,
            relief=tk.FLAT,
            padx=25,
            pady=12,
            command=self.restart_optimization,
            cursor="hand2"
        )
        # Initially hidden
        self.restart_button.pack_forget()
        
        # Close button
        self.continue_button = tk.Button(
            self.buttons_frame,
            text="Close",
            font=("Segoe UI", 12),
            bg=self.COLORS['accent'],
            fg=self.COLORS['text_primary'],
            bd=1,
            relief=tk.FLAT,
            padx=25,
            pady=12,
            command=self.close_window,
            cursor="hand2"
        )
        self.continue_button.pack(side=tk.RIGHT)

    def _toggle_sidebar(self):
        """Toggle sidebar visibility with proper resizing"""
        if self.sidebar_visible:
            # Hide sidebar and expand main content to full width
            self.sidebar.pack_forget()
            self.sidebar_visible = False
            # Remove width constraint from content frame
            self.content_frame.configure(width=0)  # Reset to auto-size
            self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        else:
            # Show sidebar first
            self.sidebar.pack(side=tk.RIGHT, fill=tk.Y, expand=False)
            self.sidebar_visible = True
            
            # Force update to get current window size
            self.parent.update_idletasks()
            
            # Calculate and set content frame width to (screen width - 300px)
            window_width = self.parent.winfo_width()
            content_width = window_width - 300  # Reserve 300px for sidebar
            
            # Repack content frame with new width
            self.content_frame.pack_forget()
            self.content_frame.configure(width=content_width)
            self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
            
            # Force update to ensure proper layout
            self.parent.update_idletasks()

    def _on_window_resize(self, event):
        """Handle window resize to maintain proper layout when sidebar is open"""
        # Only handle main window resize events
        if event.widget == self.parent and self.sidebar_visible:
            # Debounce resize events
            if hasattr(self, '_resize_timer'):
                self.parent.after_cancel(self._resize_timer)
            self._resize_timer = self.parent.after(100, self._adjust_content_width)

    def _adjust_content_width(self):
        """Adjust content frame width when window is resized"""
        if self.sidebar_visible:
            window_width = self.parent.winfo_width()
            content_width = window_width - 300  # Reserve 300px for sidebar
            
            # Repack content frame with new width
            self.content_frame.pack_forget()
            self.content_frame.configure(width=content_width)
            self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

    def _clear_logs(self):
        """Clear all logs from the sidebar"""
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.delete(1.0, tk.END)
        self.logs_text.config(state=tk.DISABLED)
        self.realtime_logs.clear()
        self._add_log_entry("Logs cleared", "INFO")

    def _add_log_entry(self, message, level="INFO"):
        """Add a log entry to the real-time logs"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"
        
        self.realtime_logs.append(log_entry)
        
        # Keep only last 1000 entries
        if len(self.realtime_logs) > 1000:
            self.realtime_logs = self.realtime_logs[-1000:]
        
        # Always update logs display, regardless of sidebar visibility
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.insert(tk.END, log_entry)
        self.logs_text.see(tk.END)
        self.logs_text.config(state=tk.DISABLED)

    def _load_context(self) -> None:
        self.curveData = self.controller.get_app_data("optimization_settings") or {}
        self.testRows = self.controller.get_app_data("generated_data") or []
        self.netlistPath = self.controller.get_app_data("netlist_path")
        self.netlistObject = self.controller.get_app_data("netlist_object")
        self.selectedParameters = self.controller.get_app_data("selected_parameters")
        self.optimizationTolerances = self.controller.get_app_data("optimization_tolerances")
        self.RLCBounds = self.controller.get_app_data("RLC_bounds")
        self.analysis_type = (self.curveData.get("analysis_type") or "transient").lower()
        self.ac_settings = self.curveData.get("ac_settings") or {}
        self.ac_response = (self.ac_settings.get("response") or "magnitude").lower()
        self.noise_settings = self.curveData.get("noise_settings") or {}
        self.noise_quantity = (self.noise_settings.get("quantity") or "onoise").lower()
        if self.noise_quantity not in {"onoise", "onoise_db", "inoise", "inoise_db"}:
            self.noise_quantity = "onoise"
        self.x_parameter = self.curveData.get("x_parameter", "TIME")
        default_x_label = "Frequency (Hz)" if self.analysis_type in {"ac", "noise"} else "Time (s)"
        self.x_parameter_display = self.curveData.get("x_parameter_display") or default_x_label
        self.y_parameter_display = (
            self.curveData.get("y_parameter_display")
            or self.curveData.get("y_units")
            or self.curveData.get("y_parameter")
            or ""
        )
        self.y_parameter_expression = (
            self.curveData.get("y_parameter_expression") or self.curveData.get("y_parameter") or ""
        )

    def _prepare_target_data(self) -> None:
        self.target_x = []
        self.target_y = []
        processed_rows = []
        if self.testRows:
            for row in self.testRows:
                try:
                    x_val = float(row[0])
                    y_val = float(row[1])
                except (TypeError, ValueError, IndexError):
                    continue
                needs_db = (
                    self.analysis_type == "ac" and self.ac_response == "magnitude_db"
                ) or (
                    self.analysis_type == "noise" and self.noise_quantity.endswith("_db")
                )
                if needs_db:
                    if y_val <= 0:
                        y_val = 1e-30
                    y_val = 20.0 * math.log10(y_val)
                processed_rows.append([x_val, y_val])

        if processed_rows:
            self.target_x = [row[0] for row in processed_rows]
            self.target_y = [row[1] for row in processed_rows]
            range_y = max(self.target_y) - min(self.target_y)
            needs_db_margin = (
                self.analysis_type == "ac" and self.ac_settings.get("response") == "magnitude_db"
            ) or (
                self.analysis_type == "noise" and self.noise_quantity.endswith("_db")
            )
            default_margin = 5 if needs_db_margin else 1
            margin = max(range_y * 0.25, default_margin)
            self.minBound = min(self.target_y) - margin
            self.maxBound = max(self.target_y) + margin
        else:
            self.minBound = 0
            self.maxBound = 1
        self.processed_test_rows = processed_rows

    def _build_plot(self) -> None:
        self.figure = Figure(figsize=(8, 4), dpi=100, facecolor=self.COLORS['bg_secondary'])
        self.ax = self.figure.add_subplot(111, facecolor=self.COLORS['bg_secondary'])
        
        # Configure plot styling
        self.ax.set_xlabel(self.x_parameter_display, color=self.COLORS['text_secondary'], fontsize=12)
        self.ax.set_ylabel(self.y_parameter_display, color=self.COLORS['text_secondary'], fontsize=12)
        if self.analysis_type in {"ac", "noise"}:
            try:
                self.ax.set_xscale("log")
            except ValueError:
                pass
        
        # Style the axes
        self.ax.tick_params(colors=self.COLORS['text_secondary'])
        self.ax.spines['bottom'].set_color(self.COLORS['border'])
        self.ax.spines['top'].set_color(self.COLORS['border'])
        self.ax.spines['right'].set_color(self.COLORS['border'])
        self.ax.spines['left'].set_color(self.COLORS['border'])
        
        self.figure.subplots_adjust(bottom=0.15, left=0.1, right=0.95, top=0.9)
        
        # Plot lines
        self.line, = self.ax.plot([], [], color=self.COLORS['accent'], linewidth=2, label="Simulation")
        self.line2, = self.ax.plot(
            [], [], color=self.COLORS['success'], linestyle="--", linewidth=2, label="Target"
        )
        
        if self.target_x and self.target_y:
            self.line2.set_data(self.target_x, self.target_y)
        self.ax.set_ylim(self.minBound, self.maxBound)
        
        # Legend
        self.ax.legend(loc='upper right', frameon=True, facecolor=self.COLORS['bg_tertiary'], 
                      edgecolor=self.COLORS['border'], labelcolor=self.COLORS['text_primary'])

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

    def start_optimization(self) -> None:
        if getattr(self, "convergence_label", None):
            self.convergence_label.config(text="Convergence: -- %")
        self._initial_cost = None
        if getattr(self, "error_label", None):
            self.error_label.config(text="Max Error: --\nRMS Error: --")
        self._latest_simulation = None
        if self.thread and self.thread.is_alive():
            return
        self._load_context()
        self._prepare_target_data()
        self._update_target_plot()
        self.back_to_settings_button.config(state=tk.DISABLED)
        self._graph_update_counter = 0
        self.optimization_active = True
        self._reset_status_view()
        self.queue = queue.Queue()
        self.thread = th.Thread(
            target=optimizeProcess,
            args=(
                self.queue,
                self.curveData,
                self.processed_test_rows,
                self.netlistPath,
                self.netlistObject,
                self.selectedParameters,
                self.optimizationTolerances,
                self.RLCBounds,
            ),
        )
        self.thread.daemon = True
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
        self.status_label.config(text="Optimization In Progress", fg=self.COLORS['text_primary'])
        if hasattr(self, "line"):
            self.line.set_data([], [])
        self.ax.set_ylim(self.minBound, self.maxBound)
        if hasattr(self, "canvas"):
            self.canvas.draw()
        
        # Reset to computing state
        self._show_computing_state()

    def _cleanup_worker(self) -> None:
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.1)
        self.thread = None
        self.queue = None
        self.optimization_active = False

    def return_to_settings(self) -> None:
        self._cleanup_worker()
        self.controller.navigate("optimization_settings")

    def restart_optimization(self) -> None:
        """Restart from netlist upload step"""
        self._cleanup_worker()
        # Navigate back to netlist uploader to start fresh
        self.controller.navigate("netlist_uploader")

    def update_ui(self) -> None:
        try:
            if self.queue:
                messages_processed = 0
                drained_queue = True
                while messages_processed < self._message_batch_limit:
                    try:
                        msg_type, msg_value = self.queue.get_nowait()
                    except queue.Empty:
                        drained_queue = True
                        break
                    except Exception as msg_error:
                        self._add_log_entry(f"Error processing message: {msg_error}", "ERROR")
                        continue

                    drained_queue = False
                    messages_processed += 1

                    if msg_type == "Update":
                        if "total runs completed:" in msg_value:
                            try:
                                run_count = int(msg_value.split(":")[-1].strip())
                                self.run_count_label.config(text=f"Runs: {run_count}")
                            except Exception:
                                pass
                        else:
                            self._add_log_entry(msg_value, "INFO")
                    elif msg_type == "Log":
                        continue
                    elif msg_type == "Done":
                        self._add_log_entry(msg_value, "SUCCESS")
                        self.status_label.config(text="Optimization Complete", fg=self.COLORS['success'])
                        self.optimization_active = False
                        self.back_to_settings_button.pack_forget()
                        self.restart_button.pack(side=tk.LEFT, padx=(0, 10))
                    elif msg_type == "Failed":
                        self._add_log_entry(f"Optimization Failed: {msg_value}", "ERROR")
                        self.status_label.config(text="Optimization Failed", fg=self.COLORS['error'])
                        self.optimization_active = False
                        self.back_to_settings_button.pack_forget()
                        self.restart_button.pack(side=tk.LEFT, padx=(0, 10))
                    elif msg_type == "UpdateNetlist":
                        self.controller.update_app_data("netlist_object", msg_value)
                        self._add_log_entry("Netlist updated", "INFO")
                    elif msg_type == "UpdateOptimizationResults":
                        self.controller.update_app_data("optimization_results", msg_value)
                        self._show_results_state(msg_value)
                        self._add_log_entry("Optimization results updated", "SUCCESS")
                    elif msg_type == "UpdateYData":
                        self.update_graph(msg_value)
                    else:
                        self._add_log_entry(f"Unknown message type: {msg_type} - {msg_value}", "WARNING")

                if messages_processed > 1:
                    self._add_log_entry(f"Processed {messages_processed} messages in this update cycle", "DEBUG")

                self.parent.update_idletasks()
                if not drained_queue:
                    self.parent.after(10, self.update_ui)
                    return

        except Exception as e:
            print("UI Update Error:", e)
            self._add_log_entry(f"UI Update Error: {e}", "ERROR")

        if not self.optimization_active:
            self._cleanup_worker()

        # Continue the update loop every 100ms
        self.parent.after(100, self.update_ui)


    def update_graph(self, xy_data) -> None:
        self._graph_update_counter += 1
        data = tuple(xy_data)
        if len(data) == 4:
            analysis_mode, response_mode, x_raw, y_raw = data
            x_data = list(x_raw)
            y_data = list(y_raw)
            if analysis_mode:
                self.analysis_type = analysis_mode
            current_mode = analysis_mode or self.analysis_type
            if response_mode:
                if current_mode == "ac":
                    self.ac_response = response_mode
                elif current_mode == "noise":
                    self.noise_quantity = response_mode
        else:
            current_mode = self.analysis_type
            if current_mode == "ac":
                response_mode = getattr(self, "ac_response", "magnitude")
            elif current_mode == "noise":
                response_mode = getattr(self, "noise_quantity", "onoise")
            else:
                response_mode = None
            y_data = list(data[1])
            x_data = list(data[0])
        if current_mode == "ac" and response_mode == "magnitude_db":
            y_data = [20.0 * math.log10(max(val, 1e-30)) for val in y_data]
        elif current_mode == "noise" and response_mode and response_mode.endswith("_db"):
            y_data = [20.0 * math.log10(max(val, 1e-30)) for val in y_data]

        self._latest_simulation = (list(x_data), list(y_data))
        if self._graph_update_counter % 5 == 0 or not self.optimization_active:
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
            self.canvas.draw_idle()
            self._update_error_label()

        # Update plot styling
        self.ax.tick_params(colors=self.COLORS['text_secondary'])
        self.ax.spines['bottom'].set_color(self.COLORS['border'])
        self.ax.spines['top'].set_color(self.COLORS['border'])
        self.ax.spines['right'].set_color(self.COLORS['border'])
        self.ax.spines['left'].set_color(self.COLORS['border'])
        if self.analysis_type in {"ac", "noise"}:
            try:
                self.ax.set_xscale("log")
            except ValueError:
                pass
        
        self.canvas.draw()

    def close_window(self) -> None:
        try:
            if getattr(self, "convergence_window", None):
                self.convergence_window.destroy()
                self.convergence_window = None
        except Exception:
            pass
        self.parent.quit()
