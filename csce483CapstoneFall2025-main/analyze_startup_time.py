#!/usr/bin/env python3
"""
Startup Time Analysis for main_app.py

This script analyzes factors that might be contributing to slow startup times
by measuring import times, library loading, and initialization overhead.
"""

import sys
import time
import importlib
import subprocess
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

class StartupAnalyzer:
    """Analyzes application startup performance."""
    
    def __init__(self):
        self.measurements: Dict[str, float] = {}
        self.import_times: Dict[str, float] = {}
        self.errors: List[str] = []
        
    def time_function(self, name: str, func, *args, **kwargs):
        """Time a function execution."""
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            self.measurements[name] = end_time - start_time
            return result
        except Exception as e:
            self.errors.append(f"{name}: {str(e)}")
            self.measurements[name] = float('inf')
            return None
    
    def time_import(self, module_name: str, from_module: str = None):
        """Time how long it takes to import a module."""
        start_time = time.perf_counter()
        try:
            if from_module:
                module = __import__(from_module, fromlist=[module_name])
                getattr(module, module_name)
                full_name = f"{from_module}.{module_name}"
            else:
                importlib.import_module(module_name)
                full_name = module_name
            
            end_time = time.perf_counter()
            self.import_times[full_name] = end_time - start_time
            
        except Exception as e:
            self.errors.append(f"Import {module_name}: {str(e)}")
            self.import_times[module_name] = float('inf')
    
    def analyze_heavy_libraries(self):
        """Analyze import times for heavy libraries used in the project."""        
        # Heavy libraries from requirements.txt
        heavy_libs = [
            "numpy",
            "scipy", 
            "matplotlib",
            "tkinter",
            "PIL" 
        ]
        
        for lib in heavy_libs:
            print(f"Testing {lib}")
            self.time_import(lib)

    def analyze_project_imports(self):
        """Analyze import times for project modules."""
        print("\nAnalyzing project module import times")
        
        project_modules = [
            ("frontend", None),
            ("backend", None),
            ("main", "frontend"),
            ("app_controller", "frontend"),
            ("netlist_uploader", "frontend"),
            ("parameter_selection", "frontend"),
            ("netlist_parse", "backend"),
            ("curvefit_optimization", "backend"),
            ("xyce_parsing_function", "backend"),
        ]
        
        for module, from_module in project_modules:
            print(f"   Testing {module}")
            self.time_import(module, from_module)
    
    def analyze_gui_initialization(self):
        """Analyze GUI initialization overhead."""
        print("\nAnalyzing GUI initialization")
        
        def create_root():
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()  # Hide the window
            return root
            
        def create_controller():
            import tkinter as tk
            from frontend.app_controller import AppController
            root = tk.Tk()
            root.withdraw()
            app = AppController(root)
            return app
        
        # Time tkinter root creation
        self.time_function("tkinter_root_creation", create_root)
        
        # Time AppController creation
        self.time_function("app_controller_creation", create_controller)
    
    def check_file_system_overhead(self):
        """Check for file system operations that might slow startup."""
        print("\nChecking file system overhead")
        
        def check_directory_exists():
            paths_to_check = [
                PROJECT_ROOT / "frontend",
                PROJECT_ROOT / "backend", 
                PROJECT_ROOT / "netlists",
                PROJECT_ROOT / "docs",
                PROJECT_ROOT / "xyclopsvenv"
            ]
            
            for path in paths_to_check:
                path.exists()
        
        def count_files_in_project():
            return len(list(PROJECT_ROOT.rglob("*.py")))
        
        self.time_function("directory_checks", check_directory_exists)
        self.time_function("file_counting", count_files_in_project)
    
    def measure_cold_start(self):
        """Measure actual application cold start time."""
        print("\nMeasuring cold start time...")
        
        venv_python = PROJECT_ROOT / "xyclopsvenv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = "python3"
        
        # Create a minimal test script that imports main_app
        test_script = '''
import sys
import time
start_time = time.perf_counter()

# Add path and import main_app
sys.path.insert(0, ".")
from frontend.main import main

end_time = time.perf_counter()
print(f"IMPORT_TIME:{end_time - start_time:.4f}")
'''
        
        try:
            result = subprocess.run(
                [str(venv_python), "-c", test_script],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(PROJECT_ROOT)
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith("IMPORT_TIME:"):
                        import_time = float(line.split(':')[1])
                        self.measurements["cold_start_import"] = import_time
                        break
            else:
                self.errors.append(f"Cold start failed: {result.stderr}")
                
        except Exception as e:
            self.errors.append(f"Cold start measurement failed: {e}")
    
    def generate_report(self):
        """Generate a comprehensive startup analysis report."""
        print("STARTUP TIME ANALYSIS REPORT")
        
        # Heavy libraries analysis
        print("\nHEAVY LIBRARY IMPORT TIMES:")
        heavy_imports = {k: v for k, v in self.import_times.items() 
                        if k in ["numpy", "scipy", "matplotlib", "tkinter", "PIL"]}
        
        for lib, time_taken in sorted(heavy_imports.items(), key=lambda x: x[1], reverse=True):
            if time_taken == float('inf'):
                print(f"   ❌ {lib:<15} FAILED TO IMPORT")
            else:
                status = "🐌" if time_taken > 0.5 else "⚡" if time_taken < 0.1 else "🟡"
                print(f"   {status} {lib:<15} {time_taken:.3f}s")
        
        # Project modules analysis
        print("\nPROJECT MODULE IMPORT TIMES:")
        project_imports = {k: v for k, v in self.import_times.items() 
                          if k not in heavy_imports}
        
        for module, time_taken in sorted(project_imports.items(), key=lambda x: x[1], reverse=True):
            if time_taken == float('inf'):
                print(f"   ❌ {module:<25} FAILED TO IMPORT")
            else:
                status = "🐌" if time_taken > 0.1 else "⚡" if time_taken < 0.01 else "🟡"
                print(f"   {status} {module:<25} {time_taken:.4f}s")
        
        # GUI initialization analysis
        print("\nGUI INITIALIZATION TIMES:")
        gui_measurements = {k: v for k, v in self.measurements.items() 
                           if 'gui' in k.lower() or 'tkinter' in k.lower() or 'controller' in k.lower()}
        
        for component, time_taken in sorted(gui_measurements.items(), key=lambda x: x[1], reverse=True):
            if time_taken == float('inf'):
                print(f"   ❌ {component:<25} FAILED")
            else:
                status = "🐌" if time_taken > 0.2 else "⚡" if time_taken < 0.05 else "🟡"
                print(f"   {status} {component:<25} {time_taken:.4f}s")
        
        # File system overhead
        print("\nFILE SYSTEM OVERHEAD:")
        fs_measurements = {k: v for k, v in self.measurements.items() 
                          if 'directory' in k.lower() or 'file' in k.lower()}
        
        for operation, time_taken in sorted(fs_measurements.items(), key=lambda x: x[1], reverse=True):
            if time_taken == float('inf'):
                print(f"   ❌ {operation:<25} FAILED")
            else:
                status = "🐌" if time_taken > 0.1 else "⚡" if time_taken < 0.01 else "🟡"
                print(f"   {status} {operation:<25} {time_taken:.4f}s")
        
        # Cold start measurement
        if "cold_start_import" in self.measurements:
            cold_start = self.measurements["cold_start_import"]
            print(f"\nCOLD START TIME: {cold_start:.3f}s")
        
        # Total estimated startup time
        total_heavy = sum(t for t in heavy_imports.values() if t != float('inf'))
        total_project = sum(t for t in project_imports.values() if t != float('inf'))
        total_gui = sum(t for t in gui_measurements.values() if t != float('inf'))
        
        print(f"\nESTIMATED BREAKDOWN:")
        print(f"   Heavy libraries: {total_heavy:.3f}s")
        print(f"   Project modules: {total_project:.3f}s") 
        print(f"   GUI initialization: {total_gui:.3f}s")
        print(f"   Total estimated: {total_heavy + total_project + total_gui:.3f}s")

def main():
    """Run the startup analysis."""
    print("Starting startup time analysis for main_app.py...")
    print("This may take a moment as we measure import and initialization times.\n")
    
    analyzer = StartupAnalyzer()
    
    # Run all analyses
    analyzer.analyze_heavy_libraries()
    analyzer.analyze_project_imports()
    analyzer.analyze_gui_initialization()
    analyzer.check_file_system_overhead()
    analyzer.measure_cold_start()
    
    # Generate comprehensive report
    analyzer.generate_report()

if __name__ == "__main__":
    main()
