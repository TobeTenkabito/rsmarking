import docker
import os
import uuid
import logging
from docker.errors import ContainerError, ImageNotFound, APIError
from services.executor_service.config import (
    HOST_TMP_DIR, HOST_RAW_DIR, HOST_COG_DIR,
    CONTAINER_INPUT_DIR, CONTAINER_OUTPUT_DIR, CONTAINER_SCRIPT_DIR,
    SANDBOX_MEM_LIMIT, SANDBOX_CPU_LIMIT, SANDBOX_TIMEOUT_SEC, DOCKER_IMAGE_NAME
)

logger = logging.getLogger("executor_service.runner")
client = docker.from_env()


def run_in_sandbox(script_content: str, input_filenames: list[str], output_filename: str) -> dict:
    """
    在 Docker 沙箱中执行用户脚本
    :param script_content: 用户输入的 Python 代码字符串
    :param input_filenames: 需要挂载的源影像文件名列表 (相对 storage/raw 的名称)
    :param output_filename: 期望生成的输出文件名
    :return: 包含执行状态和日志的字典
    """
    task_id = str(uuid.uuid4())
    script_host_path = os.path.join(HOST_TMP_DIR, f"script_{task_id}.py")

    # 1. 将代码写入宿主机临时文件，避免命令行注入漏洞
    with open(script_host_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    # 2. 构建挂载卷 (Volumes)
    volumes = {
        # 只读挂载临时脚本
        script_host_path: {'bind': f"{CONTAINER_SCRIPT_DIR}/user_code.py", 'mode': 'ro'},
        # 读写挂载输出目录
        HOST_COG_DIR: {'bind': CONTAINER_OUTPUT_DIR, 'mode': 'rw'}
    }

    # 为了防止目录遍历漏洞，明确挂载指定的文件，而非整个 raw 目录
    for idx, fname in enumerate(input_filenames):
        host_file = os.path.join(HOST_RAW_DIR, fname)
        if not os.path.exists(host_file):
            return {"status": "error", "message": f"输入文件不存在: {fname}"}
        # 容器内按顺序重命名为 00_input.tif, 01_input.tif ...
        container_file = f"{CONTAINER_INPUT_DIR}/{idx:02d}_{fname}"
        volumes[host_file] = {'bind': container_file, 'mode': 'ro'}

    container = None
    try:
        # 3. 启动容器 (同步阻塞等待执行结果)
        # 工业级：禁用网络防止数据泄露，设置 auto_remove 避免僵尸容器堆积
        output = client.containers.run(
            image=DOCKER_IMAGE_NAME,
            environment={"OUTPUT_FILENAME": output_filename},
            volumes=volumes,
            mem_limit=SANDBOX_MEM_LIMIT,
            nano_cpus=SANDBOX_CPU_LIMIT,
            network_disabled=True,
            detach=False,  # 阻塞模式，等待执行结束
            remove=True,  # 执行完毕后自动销毁容器
            stderr=True,
            stdout=True
        )
        return {"status": "success", "logs": output.decode("utf-8")}

    except ContainerError as e:
        # 容器内发生错误 (exit code != 0)
        error_logs = e.stderr.decode("utf-8") if e.stderr else str(e)
        logger.error(f"任务 {task_id} 脚本错误: {error_logs}")
        return {"status": "error", "message": "脚本执行抛出异常", "logs": error_logs}

    except ImageNotFound:
        return {"status": "error", "message": f"未找到基础镜像 {DOCKER_IMAGE_NAME}，请先执行 docker build"}

    except Exception as e:
        logger.error(f"Docker API 异常: {str(e)}")
        return {"status": "error", "message": "执行服务调度失败"}

    finally:
        # 4. 清理宿主机临时脚本
        if os.path.exists(script_host_path):
            os.remove(script_host_path)