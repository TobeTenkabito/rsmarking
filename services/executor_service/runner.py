import asyncio
import docker
import os
import re
import uuid
import logging
import shutil
from docker.errors import ContainerError, ImageNotFound, APIError
from typing import List, Dict, Optional

from services.executor_service.config import (
    HOST_TMP_DIR, HOST_RAW_DIR, HOST_COG_DIR,
    CONTAINER_INPUT_DIR, CONTAINER_OUTPUT_DIR, CONTAINER_SCRIPT_DIR,
    SANDBOX_MEM_LIMIT, SANDBOX_CPU_LIMIT, SANDBOX_TIMEOUT_SEC, DOCKER_IMAGE_NAME
)

logger = logging.getLogger("executor_service.runner")

# Docker客户端初始化
try:
    client = docker.from_env()
    logger.info("Docker客户端初始化成功")
except Exception as e:
    logger.error(f"Docker客户端初始化失败: {str(e)}")
    client = None


class DockerRunner:
    """Docker容器执行器"""

    def __init__(self):
        self.client = client

    async def prepare_docker_image(self):
        """准备Docker镜像"""
        try:
            # 检查镜像是否存在
            self.client.images.get(DOCKER_IMAGE_NAME)
            logger.info(f"Docker镜像 {DOCKER_IMAGE_NAME} 已存在")
        except ImageNotFound:
            logger.info(f"构建Docker镜像 {DOCKER_IMAGE_NAME}...")
            dockerfile_path = os.path.join(
                os.path.dirname(__file__),
                "runtime"
            )
            # 修复3：镜像构建放到独立线程，避免阻塞事件循环
            await asyncio.to_thread(
                self.client.images.build,
                path=dockerfile_path,
                dockerfile="python_base.Dockerfile",
                tag=DOCKER_IMAGE_NAME,
                rm=True,
                forcerm=True
            )
            logger.info("Docker镜像构建完成")

    def validate_script(self, script: str) -> bool:
        """
        验证脚本安全性
        - 大小写敏感，避免误杀正常变量名
        - 移除 open( 拦截，避免误杀 rasterio.open()
        - exec 单独用词边界正则匹配，避免误中 execute/executor
        """
        dangerous_keywords = [
            '__import__',
            'subprocess',
            'os.system',
            'os.popen',
            'os.execv',
            'os.execve',
            'socket',
            'eval(',
            'compile(',
            'raw_input(',
            'file(',
        ]

        # 修复2：不再 .lower()，保持大小写敏感匹配
        for keyword in dangerous_keywords:
            if keyword in script:
                logger.warning(f"脚本包含危险关键字: {keyword}")
                return False

        # 修复2：exec 单独用词边界检测，避免误中 execute/executor 等正常词
        if re.search(r'\bexec\s*\(', script):
            logger.warning("脚本包含危险关键字: exec()")
            return False

        return True

    async def run_script(
            self,
            script_id: str,
            script: str,
            input_files: List[Dict[str, str]],
            output_name: str
    ) -> dict:
        """执行脚本的包装方法"""
        # 修复1：实际调用安全校验，不通过直接拒绝
        if not self.validate_script(script):
            return {
                "status": "error",
                "message": "脚本包含危险关键字，执行已拒绝"
            }

        # 修复3：用 asyncio.to_thread 包装同步阻塞调用，避免卡死事件循环
        return await asyncio.to_thread(
            run_in_sandbox,
            script_content=script,
            input_filenames=[],
            output_filename=output_name,
            script_id=script_id,
            input_files=input_files
        )

    async def cleanup(self):
        """清理资源"""
        # 清理临时文件
        if os.path.exists(HOST_TMP_DIR):
            for file in os.listdir(HOST_TMP_DIR):
                try:
                    os.remove(os.path.join(HOST_TMP_DIR, file))
                except Exception:
                    pass

        # 修复4：清理可能因异常未自动删除的残留容器
        try:
            containers = self.client.containers.list(
                filters={"ancestor": DOCKER_IMAGE_NAME, "status": "exited"}
            )
            for c in containers:
                c.remove(force=True)
                logger.info(f"清理残留容器: {c.short_id}")
        except Exception as e:
            logger.warning(f"容器清理失败: {e}")


def run_in_sandbox(
        script_content: str,
        input_filenames: List[str],
        output_filename: str,
        script_id: str = None,
        input_files: List[Dict[str, str]] = None
) -> dict:
    """
    在 Docker 沙箱中执行用户脚本

    :param script_content: 用户输入的 Python 代码字符串
    :param input_filenames: 文件名列表（兼容旧接口，暂未使用）
    :param output_filename: 期望生成的输出文件名
    :param script_id: 脚本ID
    :param input_files: 完整的文件信息列表 [{"path": "...", "name": "..."}]
    :return: 包含执行状态和日志的字典
    """
    if not client:
        return {"status": "error", "message": "Docker服务未启动"}

    task_id = script_id or str(uuid.uuid4())
    script_host_path = os.path.join(HOST_TMP_DIR, f"script_{task_id}.py")

    # 创建临时输入目录
    temp_input_dir = os.path.join(HOST_TMP_DIR, f"input_{task_id}")
    os.makedirs(temp_input_dir, exist_ok=True)

    try:
        # 1. 将代码写入宿主机临时文件
        with open(script_host_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        # 2. 准备输入文件：复制到临时目录供容器挂载
        if input_files:
            for idx, file_info in enumerate(input_files):
                src_path = file_info.get("path", "")
                file_name = file_info.get("name", f"input_{idx}.tif")

                if os.path.exists(src_path):
                    dst_path = os.path.join(temp_input_dir, file_name)
                    shutil.copy2(src_path, dst_path)
                    logger.info(f"复制输入文件: {src_path} -> {dst_path}")
                else:
                    logger.warning(f"输入文件不存在: {src_path}")

        # 3. 构建挂载卷
        volumes = {
            # 只读挂载脚本
            script_host_path: {
                'bind': f"{CONTAINER_SCRIPT_DIR}/user_code.py",
                'mode': 'ro'
            },
            # 读写挂载输出目录
            HOST_COG_DIR: {
                'bind': CONTAINER_OUTPUT_DIR,
                'mode': 'rw'
            },
            # 只读挂载输入目录
            temp_input_dir: {
                'bind': CONTAINER_INPUT_DIR,
                'mode': 'ro'
            }
        }

        # 4. 运行容器
        logger.info(f"启动Docker容器执行脚本 {task_id}")

        # CPU 限制转换为纳秒整数
        cpu_limit = int(SANDBOX_CPU_LIMIT * 1e9) if isinstance(SANDBOX_CPU_LIMIT, (int, float)) else 1_000_000_000

        output = client.containers.run(
            image=DOCKER_IMAGE_NAME,
            command=None,
            environment={"OUTPUT_FILENAME": output_filename},
            volumes=volumes,
            mem_limit=SANDBOX_MEM_LIMIT,
            nano_cpus=cpu_limit,
            network_disabled=True,
            detach=False,
            remove=True,
            stderr=True,
            stdout=True,
            timeout=SANDBOX_TIMEOUT_SEC
        )

        logs = output.decode("utf-8") if isinstance(output, bytes) else str(output)
        logger.info(f"脚本执行成功: {task_id}")
        logger.debug(f"执行日志: {logs}")

        # 5. 检查输出文件是否生成
        output_path = os.path.join(HOST_COG_DIR, output_filename)
        if os.path.exists(output_path):
            logger.info(f"输出文件已生成: {output_path}")
        else:
            # 兜底：扫描输出目录中所有 tif 文件
            generated_files = [
                f for f in os.listdir(HOST_COG_DIR)
                if f.lower().endswith('.tif')
            ]
            if generated_files:
                logger.warning(f"未找到预期输出文件，但目录中存在: {generated_files}")
            else:
                logger.warning(f"未找到任何输出文件: {output_path}")

        return {"status": "success", "logs": logs}

    except ContainerError as e:
        # 容器内脚本抛出异常（exit code != 0）
        error_logs = e.stderr.decode("utf-8") if e.stderr else str(e)
        logger.error(f"任务 {task_id} 脚本错误: {error_logs}")
        return {
            "status": "error",
            "message": "脚本执行抛出异常",
            "logs": error_logs
        }

    except ImageNotFound:
        logger.error(f"Docker镜像不存在: {DOCKER_IMAGE_NAME}")
        return {
            "status": "error",
            "message": f"未找到基础镜像 {DOCKER_IMAGE_NAME}，请先构建镜像"
        }

    except APIError as e:
        logger.error(f"Docker API 错误: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Docker API 调用失败: {str(e)}"
        }

    except Exception as e:
        logger.error(f"Docker执行异常: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"执行服务调度失败: {str(e)}"
        }

    finally:
        # 清理临时脚本文件
        if os.path.exists(script_host_path):
            try:
                os.remove(script_host_path)
            except Exception:
                pass

        # 清理临时输入目录
        if os.path.exists(temp_input_dir):
            shutil.rmtree(temp_input_dir, ignore_errors=True)
