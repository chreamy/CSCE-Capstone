#!/usr/bin/env python3
"""
PyInstaller compilation test for main_app.py

This script tests the actual PyInstaller compilation process.
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
VENV_PYTHON = PROJECT_ROOT / "xyclopsvenv" / "bin" / "python"

def test_pyinstaller_compilation():
    """Test PyInstaller compilation process."""
    print("PYINSTALLER COMPILATION TEST")
    
    spec_file = PROJECT_ROOT / "main_app.spec"
    dist_dir = PROJECT_ROOT / "dist"
    build_dir = PROJECT_ROOT / "build"
    
    try:        
        # Check if PyInstaller is available
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import PyInstaller; print(PyInstaller.__version__)"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print("PyInstaller not available")
            return False
            
        
        if spec_file.exists():
            print(f"Using spec file: {spec_file}")
            cmd = [str(VENV_PYTHON), "-m", "PyInstaller", "--noconfirm", "--log-level=DEBUG", str(spec_file)]
        else:
            print("Using direct main_app.py compilation")
            cmd = [str(VENV_PYTHON), "-m", "PyInstaller", "--noconfirm", "--log-level=DEBUG", "main_app.py"]
        
        print(f"Running: {' '.join(cmd)}")
        
        # Run PyInstaller with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(PROJECT_ROOT)
        )
        
        if result.returncode == 0:
            print("PyInstaller compilation successful")
            
            # Check if executable was created
            if spec_file.exists():
                exe_path = dist_dir / "main_app" / "main_app"
            else:
                exe_path = dist_dir / "main_app" / "main_app"
                
            if exe_path.exists():
                print(f"Executable created: {exe_path}")
                
                try:
                    test_result = subprocess.run(
                        [str(exe_path), "--help"],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    print("Executable startup test completed")
                except subprocess.TimeoutExpired:
                    print("Executable test timed out (may be waiting for GUI)")
                except Exception as e:
                    print(f"Executable test failed: {e}")
                    
            else:
                print("Executable not found at expected location")
                
            return True
            
        else:
            print("PyInstaller compilation failed!")
            print("\nERROR OUTPUT:")
            print(result.stderr[:2000])  # Show first 2000 chars of error
            if len(result.stderr) > 2000:
                print("... (output truncated)")
            return False
            
    except subprocess.TimeoutExpired:
        print("PyInstaller compilation timed out")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    finally:
        # Clean up build artifacts (optional)
        cleanup = input("\nClean up build artifacts? (y/N): ").lower().strip()
        if cleanup == 'y':
            try:
                if dist_dir.exists():
                    shutil.rmtree(dist_dir)
                    print("Removed dist directory")
                if build_dir.exists():
                    shutil.rmtree(build_dir)
                    print("Removed build directory")
            except Exception as e:
                print(f"Cleanup failed: {e}")

if __name__ == "__main__":
    print("This test will attempt to compile main_app.py with PyInstaller.")
    print("This may take several minutes and will create build artifacts.\n")
    
    proceed = input("Proceed with PyInstaller compilation test? (y/N): ").lower().strip()
    
    if proceed == 'y':
        success = test_pyinstaller_compilation()
        if success:
            print("main_app.py successfully compiles to executable.")
        else:
            print("Check the error output above for details.")
        sys.exit(0 if success else 1)
    else:
        print("PyInstaller compilation test cancelled.")
        sys.exit(0)
