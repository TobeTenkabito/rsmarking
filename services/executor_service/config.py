import os
import platform

# --- 路径配置（跨平台兼容） ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

# 使用os.path.join确保跨平台兼容
HOST_RAW_DIR = os.path.join(BASE_DIR, "storage", "raw")
HOST_COG_DIR = os.path.join(BASE_DIR, "storage", "cog")
HOST_TMP_DIR = os.path.join(BASE_DIR, "storage", "tmp_scripts")

# 确保目录存在
os.makedirs(HOST_RAW_DIR, exist_ok=True)
os.makedirs(HOST_COG_DIR, exist_ok=True)
os.makedirs(HOST_TMP_DIR, exist_ok=True)

# 容器内路径（Linux格式，不变）
CONTAINER_INPUT_DIR = "/data/inputs"
CONTAINER_OUTPUT_DIR = "/data/outputs"
CONTAINER_SCRIPT_DIR = "/data/scripts"

# --- 沙箱资源配额限制 ---
SANDBOX_MEM_LIMIT = "2g"
SANDBOX_CPU_LIMIT = 1
SANDBOX_TIMEOUT_SEC = 120

# Docker镜像名称
DOCKER_IMAGE_NAME = "rs-worker-python:latest"

# Windows特殊处理
IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    # Windows下Docker Desktop的特殊配置
    import subprocess

    def check_docker():
        """检查Docker是否运行"""
        try:
            subprocess.run(["docker", "version"],
                           capture_output=True,
                           check=True,
                           shell=True)
            return True
        except:
            return False

    if not check_docker():
        print("警告: Docker Desktop未运行，请先启动Docker Desktop")
