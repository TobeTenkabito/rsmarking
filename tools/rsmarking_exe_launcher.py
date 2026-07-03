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
STOP_BATCH = "stop_rsmarking.bat"
STOP_SCRIPT = "stop_rsmarking.ps1"
WRAPPER_CHECK_ARG = "--rsmarking-wrapper-check"

STOP_ACTION_ARGS = {"stop", "shutdown", "--stop", "--shutdown", "/stop", "/shutdown", "-stop", "-shutdown"}
STOP_DOCKER_ARGS = {"--stop-docker", "/stop-docker", "-stopdocker", "-stop-docker", "-stopdocker"}
NO_PAUSE_ARGS = {"--no-pause", "/no-pause", "-nopause", "-no-pause", "-NoPause"}
PAUSE_ARGS = {"--pause", "/pause", "-pause", "-Pause"}


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


def executable_requests_stop() -> bool:
    stem = Path(sys.executable if getattr(sys, "frozen", False) else sys.argv[0]).stem.lower()
    return stem in {"rsmarking-stop", "stop-rsmarking", "stop_rsmarking", "rsmarking_shutdown"}


def parse_action() -> tuple[str, list[str]]:
    action = "stop" if executable_requests_stop() else "launch"
    args: list[str] = []
    pause_requested = False

    for arg in sys.argv[1:]:
        lowered = arg.lower()

        if lowered in STOP_ACTION_ARGS:
            action = "stop"
            continue

        if lowered in STOP_DOCKER_ARGS:
            args.append("-StopDocker")
            continue

        if lowered in NO_PAUSE_ARGS:
            args.append("-NoPause")
            continue

        if lowered in PAUSE_ARGS:
            pause_requested = True
            continue

        args.append(arg)

    if action == "stop" and "-NoPause" not in args and not pause_requested:
        args.append("-NoPause")

    return action, args


def powershell_script_command(script_name: str, args: list[str]) -> list[str] | None:
    powershell = find_powershell()
    if powershell is None:
        return None

    return [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        f".\\{script_name}",
        *args,
    ]


def launch_command(args: list[str]) -> list[str] | None:
    if Path(LAUNCH_BATCH).is_file():
        return [find_cmd(), "/d", "/c", f".\\{LAUNCH_BATCH}", *args]

    if Path(LAUNCH_SCRIPT).is_file():
        return powershell_script_command(LAUNCH_SCRIPT, args)

    return None


def stop_command(args: list[str]) -> list[str] | None:
    if Path(STOP_SCRIPT).is_file():
        return powershell_script_command(STOP_SCRIPT, args)

    if Path(STOP_BATCH).is_file():
        return [find_cmd(), "/d", "/c", f".\\{STOP_BATCH}", *args]

    return None


def command_for_action(action: str, args: list[str]) -> list[str] | None:
    if action == "stop":
        return stop_command(args)

    return launch_command(args)


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

    action, args = parse_action()
    command = command_for_action(action, args)
    if command is None:
        script_names = (
            f"{STOP_SCRIPT} or {STOP_BATCH}"
            if action == "stop"
            else f"{LAUNCH_BATCH} or {LAUNCH_SCRIPT}"
        )
        show_error(f"Could not find {script_names}.")
        return 1

    if WRAPPER_CHECK_ARG in sys.argv[1:]:
        print("working_directory=.")
        print(f"repo_name={repo_root.name}")
        print(f"action={action}")
        script_arg = command[3] if command[0].lower().endswith("cmd.exe") else command[5]
        print(f"launcher_arg={script_arg}")
        print(f"launcher_exists={Path(script_arg).is_file()}")
        return 0

    try:
        return subprocess.call(command)
    except OSError as exc:
        show_error(f"Failed to start RSMarking: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
