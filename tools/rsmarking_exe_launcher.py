from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_TITLE = "RSMarking Launcher"
LAUNCH_BATCH = "launch_rsmarking.bat"
LAUNCH_SCRIPT = "launch_rsmarking.ps1"
WRAPPER_CHECK_ARG = "--rsmarking-wrapper-check"


def show_error(message: str) -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, APP_TITLE, 0x10)
            return
        except Exception:
            pass

    print(f"{APP_TITLE}: {message}", file=sys.stderr)


def app_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[1]


def candidate_roots() -> list[Path]:
    starts = [app_directory(), Path.cwd().resolve()]
    candidates: list[Path] = []
    seen: set[str] = set()

    for start in starts:
        for path in (start, *start.parents):
            key = str(path).lower()
            if key not in seen:
                seen.add(key)
                candidates.append(path)

    return candidates


def looks_like_repo_root(path: Path) -> bool:
    return (
        (path / LAUNCH_SCRIPT).is_file()
        and (path / "client").is_dir()
        and (path / "services").is_dir()
        and (path / "infrastructure").is_dir()
        and (path / "worker_cluster").is_dir()
    )


def find_repo_root() -> Path | None:
    fallback: Path | None = None

    for path in candidate_roots():
        if looks_like_repo_root(path):
            return path

        if fallback is None and (path / LAUNCH_SCRIPT).is_file():
            fallback = path

    return fallback


def find_powershell() -> str | None:
    for executable in ("powershell.exe", "pwsh.exe"):
        found = shutil.which(executable)
        if found:
            return found

    return None


def find_cmd() -> str:
    return shutil.which("cmd.exe") or "cmd.exe"


def launch_command() -> list[str] | None:
    if Path(LAUNCH_BATCH).is_file():
        return [find_cmd(), "/d", "/c", f".\\{LAUNCH_BATCH}", *sys.argv[1:]]

    if Path(LAUNCH_SCRIPT).is_file():
        powershell = find_powershell()
        if powershell is None:
            return None

        return [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            f".\\{LAUNCH_SCRIPT}",
            *sys.argv[1:],
        ]

    return None


def main() -> int:
    repo_root = find_repo_root()
    if repo_root is None:
        show_error(
            "Could not find launch_rsmarking.ps1. Place rsmarking.exe in the "
            "RSMarking repository root, next to launch_rsmarking.ps1."
        )
        return 1

    try:
        os.chdir(repo_root)
    except OSError as exc:
        show_error(f"Failed to enter the RSMarking directory: {exc}")
        return 1

    command = launch_command()
    if command is None:
        show_error("Could not find launch_rsmarking.bat or launch_rsmarking.ps1.")
        return 1

    if WRAPPER_CHECK_ARG in sys.argv[1:]:
        print("working_directory=.")
        print(f"repo_name={repo_root.name}")
        print(f"launcher_arg={command[3] if command[0].lower().endswith('cmd.exe') else command[5]}")
        print(f"launcher_exists={Path(command[3] if command[0].lower().endswith('cmd.exe') else command[5]).is_file()}")
        return 0

    try:
        return subprocess.call(command)
    except OSError as exc:
        show_error(f"Failed to start RSMarking: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
