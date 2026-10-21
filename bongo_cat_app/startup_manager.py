#!/usr/bin/env python3
"""
Startup Manager for Bongo Cat Application
Manages Windows registry auto-start (Start with Windows)

Two registry locations are involved:
- HKCU\\...\\CurrentVersion\\Run holds the command Windows runs at login.
- HKCU\\...\\Explorer\\StartupApproved\\Run is where Task Manager's
  "Startup apps" tab stores enabled/disabled. Disabling the app there does NOT
  remove the Run entry, it only sets a flag here, so both must be checked.
"""

import sys
import os
import winreg

KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
APP_NAME = "BongoCat"


def is_frozen() -> bool:
    """True when running as the PyInstaller-built exe (not from source)"""
    return bool(getattr(sys, 'frozen', False))


def _get_app_command() -> str:
    """Build the command line used to launch the app on startup"""
    if is_frozen():
        # Running as compiled executable (PyInstaller)
        return f'"{sys.executable}" --startup'
    # Running as a python script: prefer pythonw.exe so no console window pops up at login
    interpreter = sys.executable
    pythonw = os.path.join(os.path.dirname(interpreter), "pythonw.exe")
    if os.path.exists(pythonw):
        interpreter = pythonw
    script_path = os.path.abspath(sys.argv[0])
    return f'"{interpreter}" "{script_path}" --startup'


def is_disabled_in_task_manager() -> bool:
    """True if the user disabled the app in Task Manager's Startup apps tab.

    The value is binary; Windows uses an even first byte (0x02, 0x06) for
    enabled and an odd one (0x03, 0x07) for disabled. A missing value means enabled.
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY_PATH, 0, winreg.KEY_READ)
    except FileNotFoundError:
        return False
    try:
        data, _ = winreg.QueryValueEx(key, APP_NAME)
        return bool(data) and (data[0] & 1) == 1
    except FileNotFoundError:
        return False
    finally:
        winreg.CloseKey(key)


def _clear_task_manager_flag():
    """Remove the Task Manager enabled/disabled flag (missing = enabled)"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY_PATH, 0, winreg.KEY_SET_VALUE)
    except FileNotFoundError:
        return
    try:
        winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        pass
    finally:
        winreg.CloseKey(key)


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
        # Enabling from the app must also undo a "Disabled" set in Task Manager,
        # otherwise the checkbox flips but Windows still skips the app at login.
        # When disabling, drop the flag too so no stale entry is left behind.
        _clear_task_manager_flag()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update Windows startup registry: {e}")
        return False


def get_startup() -> bool:
    """Check if the app will actually start with Windows"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
        return not is_disabled_in_task_manager()
    except Exception as e:
        print(f"[ERROR] Failed to read Windows startup registry: {e}")
        return False


def sync_with_config(config) -> None:
    """Make the registry match the config on launch (keeps the exe path current).

    - Running from source: do nothing, so test runs from VS Code don't replace
      the exe's startup entry with the dev interpreter.
    - Disabled in Task Manager: respect that and turn the setting off in the
      config instead of silently re-enabling it.
    """
    if not is_frozen():
        print("[INFO] Running from source - leaving Windows startup registry untouched")
        return

    start_with_windows = config.get_startup_settings().get('start_with_windows', True)

    if start_with_windows and is_disabled_in_task_manager():
        print("[INFO] Startup was disabled in Task Manager - turning the setting off")
        config.set_setting('startup', 'start_with_windows', False)
        config.save_config()
        return

    if not set_startup(start_with_windows):
        print("[WARN] Could not sync Windows startup registry")


if __name__ == "__main__":
    print("[TEST] Testing StartupManager...")
    print("Currently enabled:", get_startup())
    print("Disabled in Task Manager:", is_disabled_in_task_manager())
    set_startup(True)
    print("After enabling:", get_startup())
    set_startup(False)
    print("After disabling:", get_startup())
