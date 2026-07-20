import asyncio
import hashlib
import logging
import os
import json
import re
import shutil
import uuid
from typing import Any

import docker
from docker.errors import APIError, ContainerError, ImageNotFound
from requests.exceptions import ReadTimeout

from services.executor_service.config import (
    CONTAINER_INPUT_DIR,
    CONTAINER_OUTPUT_DIR,
    CONTAINER_SCRIPT_DIR,
    DOCKER_IMAGE_NAME,
    HOST_RAW_DIR,
    HOST_TMP_DIR,
    SANDBOX_ALLOWED_INPUT_ROOTS,
    SANDBOX_CPU_LIMIT,
    SANDBOX_FORCE_REBUILD,
    SANDBOX_MEM_LIMIT,
    SANDBOX_PIDS_LIMIT,
    SANDBOX_SHM_SIZE,
    SANDBOX_TMPFS_SIZE,
    SANDBOX_TIMEOUT_SEC,
    SANDBOX_DOCKERFILE_NAME,
    SANDBOX_IMAGE_CONTEXT_DIR,
)
from services.executor_service.security import validate_script_content

logger = logging.getLogger("executor_service.runner")
SANDBOX_SPEC_HASH_LABEL = "rsmarking.sandbox.spec_hash"
MAX_VECTOR_INPUT_BYTES = 16 * 1024 * 1024
MAX_VECTOR_TOTAL_BYTES = 64 * 1024 * 1024
MAX_VECTOR_INPUTS = 100
MAX_SANDBOX_LOG_CHARS = 128 * 1024
MAX_SANDBOX_LOG_LINES = 2000

try:
    client = docker.from_env()
    logger.info("Docker client initialized")
except Exception as e:
    logger.error("Failed to initialize Docker client: %s", e)
    client = None


def _safe_name(value: str, fallback: str) -> str:
    candidate = os.path.basename((value or "").strip())
    return candidate or fallback


def _safe_task_token(value: str | None) -> str:
    """Return a filesystem-safe, collision-resistant token for task workdirs."""
    raw = str(value or uuid.uuid4())
    readable = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._-")[:48] or "task"
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{readable}_{digest}"


def _unique_name(value: str, fallback: str, used_names: set[str]) -> str:
    candidate = _safe_name(value, fallback)
    stem, suffix = os.path.splitext(candidate)
    sequence = 1
    while candidate.casefold() in used_names:
        sequence += 1
        candidate = f"{stem}_{sequence}{suffix}"
    used_names.add(candidate.casefold())
    return candidate


def _json_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Vector input is not valid GeoJSON-compatible JSON: {exc}") from exc
    if len(encoded) > MAX_VECTOR_INPUT_BYTES:
        raise ValueError(
            f"Vector input exceeds the {MAX_VECTOR_INPUT_BYTES // (1024 * 1024)} MiB sandbox limit"
        )
    return encoded


def _validated_input_path(value: str) -> str:
    resolved = os.path.realpath(os.path.abspath(str(value or "")))
    if not os.path.isfile(resolved):
        raise ValueError(f"Input file does not exist: {value}")

    for root in SANDBOX_ALLOWED_INPUT_ROOTS:
        try:
            common = os.path.commonpath([resolved, root])
            if os.path.normcase(common) == os.path.normcase(root):
                return resolved
        except ValueError:
            continue
    raise ValueError("Input file is outside the configured sandbox storage roots")


def _decode_logs(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _container_logs(container: Any) -> str:
    try:
        raw_logs = container.logs(
            stdout=True,
            stderr=True,
            tail=MAX_SANDBOX_LOG_LINES,
        )
    except TypeError:
        # Compatibility with older Docker clients and lightweight test doubles.
        raw_logs = container.logs(stdout=True, stderr=True)
    logs = _decode_logs(raw_logs)
    if len(logs) <= MAX_SANDBOX_LOG_CHARS:
        return logs
    return "[... sandbox logs truncated ...]\n" + logs[-MAX_SANDBOX_LOG_CHARS:]


def _image_context_hash() -> str:
    digest = hashlib.sha256()
    for file_name in (SANDBOX_DOCKERFILE_NAME, "sandbox_entry.py"):
        file_path = os.path.join(SANDBOX_IMAGE_CONTEXT_DIR, file_name)
        digest.update(file_name.encode("utf-8"))
        with open(file_path, "rb") as handle:
            digest.update(handle.read())
    return digest.hexdigest()


def _image_labels(image: Any) -> dict[str, str]:
    attrs = getattr(image, "attrs", {}) or {}
    config = attrs.get("Config") or {}
    return config.get("Labels") or {}


def _ensure_image_available() -> None:
    if client is None:
        raise RuntimeError("Docker service is unavailable")

    spec_hash = _image_context_hash()
    try:
        image = client.images.get(DOCKER_IMAGE_NAME)
        current_hash = _image_labels(image).get(SANDBOX_SPEC_HASH_LABEL)
        if current_hash == spec_hash and not SANDBOX_FORCE_REBUILD:
            return
        logger.info(
            "Rebuilding sandbox image %s because the runtime spec changed",
            DOCKER_IMAGE_NAME,
        )
    except ImageNotFound:
        logger.info("Building sandbox image %s", DOCKER_IMAGE_NAME)

    client.images.build(
        path=SANDBOX_IMAGE_CONTEXT_DIR,
        dockerfile=SANDBOX_DOCKERFILE_NAME,
        tag=DOCKER_IMAGE_NAME,
        buildargs={"RS_SANDBOX_SPEC_HASH": spec_hash},
        rm=True,
        forcerm=True,
    )
    logger.info("Sandbox image build completed")


class DockerRunner:
    """Helper wrapper for async executor-service flows."""

    def __init__(self):
        self.client = client

    async def prepare_docker_image(self):
        await asyncio.to_thread(_ensure_image_available)

    def validate_script(self, script: str) -> bool:
        is_valid, blocked_label = validate_script_content(script)
        if not is_valid:
            logger.warning("Script rejected by validator: %s", blocked_label)
        return is_valid

    async def run_script(
        self,
        script_id: str,
        script: str,
        input_files: list[dict[str, Any]],
        output_name: str,
        vector_inputs: list[dict[str, Any]] | None = None,
        output_required: bool = True,
    ) -> dict[str, Any]:
        is_valid, blocked_label = validate_script_content(script)
        if not is_valid:
            return {
                "status": "error",
                "message": f"Script contains a blocked operation: {blocked_label}",
            }

        return await asyncio.to_thread(
            run_in_sandbox,
            script_content=script,
            input_filenames=[],
            output_filename=output_name,
            script_id=script_id,
            input_files=input_files,
            vector_inputs=vector_inputs,
            output_required=output_required,
        )

    async def cleanup(self):
        if os.path.exists(HOST_TMP_DIR):
            for file_name in os.listdir(HOST_TMP_DIR):
                file_path = os.path.join(HOST_TMP_DIR, file_name)
                try:
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path, ignore_errors=True)
                    else:
                        os.remove(file_path)
                except Exception:
                    pass


def run_in_sandbox(
    script_content: str,
    input_filenames: list[str],
    output_filename: str,
    script_id: str | None = None,
    input_files: list[dict[str, Any]] | None = None,
    vector_inputs: list[dict[str, Any]] | None = None,
    output_required: bool = True,
) -> dict[str, Any]:
    del input_filenames

    is_valid, blocked_label = validate_script_content(script_content)
    if not is_valid:
        return {
            "status": "error",
            "message": f"Script contains a blocked operation: {blocked_label}",
        }

    if client is None:
        return {"status": "error", "message": "Docker service is unavailable"}

    task_id = script_id or str(uuid.uuid4())
    task_token = _safe_task_token(task_id)
    safe_output_name = _safe_name(output_filename, f"{task_token}_result.tif")
    script_host_path = os.path.join(HOST_TMP_DIR, f"script_{task_token}.py")
    temp_input_dir = os.path.join(HOST_TMP_DIR, f"input_{task_token}")
    temp_output_dir = os.path.join(HOST_TMP_DIR, f"output_{task_token}")
    os.makedirs(temp_input_dir, exist_ok=True)
    os.makedirs(temp_output_dir, exist_ok=True)
    os.makedirs(HOST_RAW_DIR, exist_ok=True)
    container = None

    try:
        _ensure_image_available()

        with open(script_host_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        copied_inputs: list[str] = []
        sandbox_input_map: list[dict[str, Any]] = []
        used_input_names: set[str] = set()
        for idx, file_info in enumerate(input_files or []):
            src_path = file_info.get("path", "")
            try:
                src_path = _validated_input_path(src_path)
            except ValueError as exc:
                return {
                    "status": "error",
                    "message": str(exc),
                }

            file_name = _unique_name(
                file_info.get("name", ""),
                f"input_{idx}.tif",
                used_input_names,
            )
            dst_path = os.path.join(temp_input_dir, file_name)
            shutil.copy2(src_path, dst_path)
            copied_inputs.append(file_name)
            sandbox_input_map.append(
                {
                    "index": idx,
                    "name": file_name,
                    "raster_id": file_info.get("raster_id"),
                    "alias": file_info.get("alias"),
                }
            )

        sandbox_vector_map: list[dict[str, Any]] = []
        total_vector_bytes = 0
        if len(vector_inputs or []) > MAX_VECTOR_INPUTS:
            return {
                "status": "error",
                "message": f"Too many vector inputs; maximum is {MAX_VECTOR_INPUTS}",
            }

        for idx, vector_info in enumerate(vector_inputs or []):
            geojson = vector_info.get("geojson")
            if not isinstance(geojson, dict) or geojson.get("type") not in {
                "Feature",
                "FeatureCollection",
            }:
                return {
                    "status": "error",
                    "message": (
                        f"Vector input {idx} must be a GeoJSON Feature or FeatureCollection"
                    ),
                }

            fallback = f"vector_{idx}.geojson"
            file_name = _unique_name(
                vector_info.get("name", ""),
                fallback,
                used_input_names,
            )
            if not file_name.lower().endswith((".geojson", ".json")):
                file_name = _unique_name(
                    f"{os.path.splitext(file_name)[0]}.geojson",
                    fallback,
                    used_input_names,
                )
            encoded = _json_bytes(geojson)
            total_vector_bytes += len(encoded)
            if total_vector_bytes > MAX_VECTOR_TOTAL_BYTES:
                return {
                    "status": "error",
                    "message": (
                        "Combined vector inputs exceed the "
                        f"{MAX_VECTOR_TOTAL_BYTES // (1024 * 1024)} MiB sandbox limit"
                    ),
                }
            dst_path = os.path.join(temp_input_dir, file_name)
            with open(dst_path, "wb") as handle:
                handle.write(encoded)

            sandbox_vector_map.append(
                {
                    "index": idx,
                    "name": file_name,
                    "alias": vector_info.get("alias"),
                    "feature_id": vector_info.get("feature_id"),
                    "layer_id": vector_info.get("layer_id"),
                    "geojson_type": geojson.get("type"),
                }
            )

        volumes = {
            script_host_path: {
                "bind": f"{CONTAINER_SCRIPT_DIR}/user_code.py",
                "mode": "ro",
            },
            temp_output_dir: {
                "bind": CONTAINER_OUTPUT_DIR,
                "mode": "rw",
            },
            temp_input_dir: {
                "bind": CONTAINER_INPUT_DIR,
                "mode": "ro",
            },
        }

        cpu_limit = int(float(SANDBOX_CPU_LIMIT) * 1e9)
        thread_limit = str(max(1, int(float(SANDBOX_CPU_LIMIT))))

        logger.info("Starting sandbox container for script %s", task_id)
        container = client.containers.run(
            image=DOCKER_IMAGE_NAME,
            environment={
                "OUTPUT_FILENAME": safe_output_name,
                "SANDBOX_INPUT_MAP": json.dumps(sandbox_input_map, ensure_ascii=False),
                "SANDBOX_VECTOR_MAP": json.dumps(sandbox_vector_map, ensure_ascii=False),
                "HOME": "/tmp",
                "MPLCONFIGDIR": "/tmp/matplotlib",
                "OMP_NUM_THREADS": thread_limit,
                "OPENBLAS_NUM_THREADS": thread_limit,
                "MKL_NUM_THREADS": thread_limit,
                "NUMEXPR_MAX_THREADS": thread_limit,
            },
            volumes=volumes,
            mem_limit=SANDBOX_MEM_LIMIT,
            nano_cpus=cpu_limit,
            pids_limit=SANDBOX_PIDS_LIMIT,
            shm_size=SANDBOX_SHM_SIZE,
            read_only=True,
            tmpfs={
                "/tmp": f"rw,nosuid,nodev,size={SANDBOX_TMPFS_SIZE}",
            },
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            network_disabled=True,
            detach=True,
            auto_remove=False,
            stderr=True,
            stdout=True,
        )

        try:
            wait_result = container.wait(
                timeout=SANDBOX_TIMEOUT_SEC,
                condition="not-running",
            )
        except ReadTimeout:
            logger.error("Sandbox timeout after %s seconds for %s", SANDBOX_TIMEOUT_SEC, task_id)
            return {
                "status": "error",
                "message": f"Script execution timed out after {SANDBOX_TIMEOUT_SEC} seconds",
                "logs": _container_logs(container),
            }

        logs = _container_logs(container)
        exit_code = int(wait_result.get("StatusCode", 1))
        if exit_code != 0:
            return {
                "status": "error",
                "message": f"Sandbox exited with status code {exit_code}",
                "logs": logs,
            }

        sandbox_output_path = os.path.join(temp_output_dir, safe_output_name)
        if not os.path.exists(sandbox_output_path):
            created_files = [
                name for name in os.listdir(temp_output_dir)
                if name.lower().endswith((".tif", ".tiff"))
            ]

            if len(created_files) == 1:
                sandbox_output_path = os.path.join(temp_output_dir, created_files[0])
                logger.warning(
                    "Renamed sandbox output %s to expected name %s",
                    created_files[0],
                    safe_output_name,
                )
            elif not output_required and not created_files:
                return {
                    "status": "success",
                    "logs": logs,
                    "output_path": None,
                    "output_filename": None,
                    "input_files": copied_inputs,
                    "vector_inputs": sandbox_vector_map,
                }
            else:
                return {
                    "status": "error",
                    "message": "Script completed but did not produce the expected output raster",
                    "logs": logs,
                }

        output_path = os.path.join(HOST_RAW_DIR, safe_output_name)
        os.replace(sandbox_output_path, output_path)

        return {
            "status": "success",
            "logs": logs,
            "output_path": output_path,
            "output_filename": safe_output_name,
            "input_files": copied_inputs,
            "vector_inputs": sandbox_vector_map,
        }

    except ContainerError as e:
        error_logs = _decode_logs(getattr(e, "stderr", None) or str(e))
        logger.error("Sandbox container error for %s: %s", task_id, error_logs)
        return {
            "status": "error",
            "message": "Sandboxed script execution failed",
            "logs": error_logs,
        }
    except ImageNotFound:
        logger.error("Sandbox image not found: %s", DOCKER_IMAGE_NAME)
        return {
            "status": "error",
            "message": f"Sandbox image not found: {DOCKER_IMAGE_NAME}",
        }
    except APIError as e:
        logger.error("Docker API error: %s", e, exc_info=True)
        return {
            "status": "error",
            "message": f"Docker API call failed: {e}",
        }
    except Exception as e:
        logger.error("Sandbox execution failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "message": f"Executor dispatch failed: {e}",
        }
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass

        if os.path.exists(script_host_path):
            try:
                os.remove(script_host_path)
            except Exception:
                pass

        if os.path.exists(temp_input_dir):
            shutil.rmtree(temp_input_dir, ignore_errors=True)

        if os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir, ignore_errors=True)
