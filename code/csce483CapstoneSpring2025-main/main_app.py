# main_app.py (in project root directory)

import sys
import os

# This block helps ensure Python can find the 'frontend' package
# when this script is run directly or by PyInstaller.
# try:
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     if script_dir not in sys.path:
#         sys.path.insert(0, script_dir)
# except NameError: # __file__ might not be defined when frozen
#      pass

# Import the main function from your actual entry point
from frontend.main import main

if __name__ == "__main__":
    # Call the imported main function from frontend/main.py
    main()
