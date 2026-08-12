#!/usr/bin/env python3
"""
Startup Manager for Bongo Cat Application
Manages Windows registry auto-start (Start with Windows)
"""

import sys
import os
import winreg

KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "BongoCat"


def _get_app_command() -> str:
    """Build the command line used to launch the app on startup"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller)
        return f'"{sys.executable}" --startup'
    else:
        # Running as a python script
        script_path = os.path.abspath(sys.argv[0])
        return f'"{sys.executable}" "{script_path}" --startup'


def set_startup(enabled: bool) -> bool:
    """Enable or disable start with Windows via the Registry Run key"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, KEY_PATH, 0,
            winreg.KEY_SET_VALUE | winreg.KEY_READ
        )
        try:
            if enabled:
                app_path = _get_app_command()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, app_path)
                print(f"[OK] Added to Windows startup: {app_path}")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    print("[OK] Removed from Windows startup")
                except FileNotFoundError:
                    # Already not present, nothing to do
                    pass
        finally:
            winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update Windows startup registry: {e}")
        return False


def get_startup() -> bool:
    """Check if the app is currently registered to start with Windows"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        print(f"[ERROR] Failed to read Windows startup registry: {e}")
        return False


if __name__ == "__main__":
    print("[TEST] Testing StartupManager...")
    print("Currently enabled:", get_startup())
    set_startup(True)
    print("After enabling:", get_startup())
    set_startup(False)
    print("After disabling:", get_startup())
