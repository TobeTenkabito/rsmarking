import os
import platform
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

HOST_RAW_DIR = os.path.join(BASE_DIR, "storage", "raw")
HOST_COG_DIR = os.path.join(BASE_DIR, "storage", "cog")
HOST_TMP_DIR = os.path.join(BASE_DIR, "storage", "tmp_scripts")

for directory in (HOST_RAW_DIR, HOST_COG_DIR, HOST_TMP_DIR):
    os.makedirs(directory, exist_ok=True)

CONTAINER_INPUT_DIR = "/data/inputs"
CONTAINER_OUTPUT_DIR = "/data/outputs"
CONTAINER_SCRIPT_DIR = "/data/scripts"

SANDBOX_MEM_LIMIT = os.getenv("SANDBOX_MEM_LIMIT", "4g")
SANDBOX_CPU_LIMIT = float(os.getenv("SANDBOX_CPU_LIMIT", "2"))
SANDBOX_TIMEOUT_SEC = int(os.getenv("SANDBOX_TIMEOUT_SEC", "300"))
SANDBOX_PIDS_LIMIT = int(os.getenv("SANDBOX_PIDS_LIMIT", "128"))
SANDBOX_SHM_SIZE = os.getenv("SANDBOX_SHM_SIZE", "512m")
SANDBOX_TMPFS_SIZE = os.getenv("SANDBOX_TMPFS_SIZE", "512m")
SANDBOX_FORCE_REBUILD = os.getenv("SANDBOX_FORCE_REBUILD", "").lower() in {"1", "true", "yes"}

DOCKER_IMAGE_NAME = os.getenv("SANDBOX_DOCKER_IMAGE", "rs-worker-python:latest")
SANDBOX_IMAGE_CONTEXT_DIR = os.path.join(CURRENT_DIR, "runtime")
SANDBOX_DOCKERFILE_NAME = "python_base.Dockerfile"

IS_WINDOWS = platform.system() == "Windows"


def check_docker() -> bool:
    try:
        subprocess.run(
            ["docker", "version"],
            capture_output=True,
            check=True,
            shell=False,
        )
        return True
    except Exception:
        return False


if IS_WINDOWS and not check_docker():
    print("Warning: Docker Desktop is not running. Start Docker before using executor_service.")
