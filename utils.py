import os
import sys

def app_dir():
    """
    Returns base directory of app
    Works for:
    - normal python run
    - pyinstaller onefile exe
    """
    env_base = os.getenv("APP_BASE_DIR", "").strip()
    if env_base:
        os.makedirs(env_base, exist_ok=True)
        return env_base

    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    
    return os.path.dirname(os.path.abspath(__file__))
