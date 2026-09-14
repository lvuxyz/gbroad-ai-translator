"""Windows Registry Run-at-Startup integration.

Manages registry entries under HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
so the application starts minimized to the system tray on Windows logon.
"""

import sys
import winreg
from pathlib import Path
from typing import Optional
from utils.logger import get_logger

logger = get_logger()

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "AITranslator"


def get_startup_command() -> str:
    """Constructs the command to start the application with --tray flag."""
    if getattr(sys, "frozen", False):
        # Compiled executable
        exe_path = Path(sys.executable).resolve()
        return f'"{exe_path}" --tray'
    else:
        # Running from Python script: use pythonw.exe if available for windowless start
        py_exe = sys.executable
        if py_exe.lower().endswith("python.exe"):
            pyw_exe = py_exe[:-10] + "pythonw.exe"
            if Path(pyw_exe).exists():
                py_exe = pyw_exe

        main_py = Path(__file__).resolve().parent.parent / "main.py"
        return f'"{py_exe}" "{main_py}" --tray'


def is_run_at_startup_enabled() -> bool:
    """Checks if the application is configured to run at Windows startup."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_READ
        ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
                return bool(val)
            except FileNotFoundError:
                return False
    except Exception as e:
        logger.warning("Could not read Windows startup registry: %s", e)
        return False


def set_run_at_startup(enabled: bool) -> bool:
    """Enables or disables starting the application with Windows."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                cmd = get_startup_command()
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
                logger.info("Enabled run-at-startup: %s", cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                    logger.info("Disabled run-at-startup")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        logger.error("Failed to update Windows startup registry: %s", e)
        return False
