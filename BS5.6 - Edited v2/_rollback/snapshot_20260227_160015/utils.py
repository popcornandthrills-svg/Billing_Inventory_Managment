import os
import sys

def app_dir():
    """
    Returns base directory of app
    Works for:
    - normal python run
    - pyinstaller onefile exe
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    
    return os.path.dirname(os.path.abspath(__file__))