#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Native folder picker for the board. Never writes harness files."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def configure_stdio() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def pick_directory(title: str = "选择 harness / 项目目录") -> str | None:
    if os.name == "nt":
        path = _pick_winforms(title)
        if path is not None:
            return path or None
    return _pick_tk(title)


def pick_directory_subprocess(title: str = "选择 harness / 项目目录") -> str | None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["TASK_HARNESS_PICK_TITLE"] = title
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(HERE / "pick_dir.py")],
            capture_output=True,
            timeout=600,
            env=env,
            creationflags=flags,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (result.stdout or b"").decode("utf-8", errors="replace").strip()
    return text or None


def _pick_winforms(title: str) -> str | None:
    escaped = title.replace("'", "''")
    ps = (
        "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false\n"
        "Add-Type -AssemblyName System.Windows.Forms\n"
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog\n"
        "$d.Description = '%s'\n"
        "try { $d.UseDescriptionForTitle = $true } catch {}\n"
        "$d.ShowNewFolderButton = $false\n"
        "try { $d.AutoUpgradeEnabled = $true } catch {}\n"
        "$r = $d.ShowDialog()\n"
        "if ($r -eq [System.Windows.Forms.DialogResult]::OK -and $d.SelectedPath) {\n"
        "  [Console]::Out.Write($d.SelectedPath)\n"
        "}\n"
    ) % escaped
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps,
            ],
            capture_output=True,
            timeout=600,
            creationflags=flags,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode not in (0, None):
        return None
    return (result.stdout or b"").decode("utf-8", errors="replace").strip()


def _pick_tk(title: str) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    root = tk.Tk()
    root.withdraw()
    try:
        root.wm_attributes("-topmost", True)
    except Exception:
        pass
    try:
        path = filedialog.askdirectory(title=title, mustexist=True)
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    return str(path).strip() if path else None


if __name__ == "__main__":
    configure_stdio()
    title = os.environ.get("TASK_HARNESS_PICK_TITLE") or "选择 harness / 项目目录"
    path = pick_directory(title) or ""
    sys.stdout.buffer.write((path + "\n").encode("utf-8"))
