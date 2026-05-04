from __future__ import annotations

import multiprocessing
import subprocess
import sys
from pathlib import Path


_PATCHED_SUBPROCESS = False


def _prefer_pythonw_executable() -> None:
    if sys.platform != "win32":
        return

    pythonw_exe = Path(sys.executable).with_name("pythonw.exe")
    if pythonw_exe.exists():
        multiprocessing.set_executable(str(pythonw_exe))


def _patch_subprocess_popen() -> None:
    global _PATCHED_SUBPROCESS
    if _PATCHED_SUBPROCESS or sys.platform != "win32":
        return

    original_popen = subprocess.Popen
    if getattr(original_popen, "_pdf2zh_no_console", False):
        _PATCHED_SUBPROCESS = True
        return

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    create_new_console = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
    startf_use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
    sw_hide = getattr(subprocess, "SW_HIDE", 0)

    class NoConsolePopen(original_popen):
        _pdf2zh_no_console = True

        def __init__(self, *args, **kwargs):
            creationflags = kwargs.get("creationflags", 0) or 0
            if not creationflags & create_new_console:
                kwargs["creationflags"] = creationflags | create_no_window

            startupinfo = kwargs.get("startupinfo")
            if startupinfo is None:
                startupinfo = subprocess.STARTUPINFO()
                kwargs["startupinfo"] = startupinfo
            startupinfo.dwFlags |= startf_use_show_window
            startupinfo.wShowWindow = sw_hide

            super().__init__(*args, **kwargs)

    subprocess.Popen = NoConsolePopen
    _PATCHED_SUBPROCESS = True


def enable_no_console_subprocesses() -> None:
    _prefer_pythonw_executable()
    _patch_subprocess_popen()