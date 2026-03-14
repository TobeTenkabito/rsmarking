import os

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

# 宿主机绝对路径
HOST_RAW_DIR = os.path.join(BASE_DIR, "storage", "raw")
HOST_COG_DIR = os.path.join(BASE_DIR, "storage", "cog")
HOST_TMP_DIR = os.path.join(BASE_DIR, "storage", "tmp_scripts")

# 确保临时脚本目录存在
os.makedirs(HOST_TMP_DIR, exist_ok=True)

# 容器内挂载路径规范
CONTAINER_INPUT_DIR = "/data/inputs"
CONTAINER_OUTPUT_DIR = "/data/outputs"
CONTAINER_SCRIPT_DIR = "/data/scripts"

# --- 沙箱资源配额限制 ---
SANDBOX_MEM_LIMIT = "2g"            # 最大内存 2GB
SANDBOX_CPU_LIMIT = 1_000_000_000   # 限制使用 1 个 CPU 核心 (单位: 纳秒)
SANDBOX_TIMEOUT_SEC = 120           # 脚本最大执行时间 (秒)

DOCKER_IMAGE_NAME = "rs-worker-python:latest"