import uvicorn
import asyncio
import logging
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from typing import List, Dict, Optional

from services.executor_service.runner import run_in_sandbox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("executor_service.main")

app = FastAPI(title="RSMarking Executor Service", description="远程沙箱代码执行器")


# DTO 定义 - 修改为匹配executor_bridge.py发送的格式
class ScriptExecutionRequest(BaseModel):
    script_id: str
    script: str  # 修改字段名
    input_files: List[Dict[str, str]]  # 修改为字典列表
    output_name: str  # 修改字段名


class ExecutionResponse(BaseModel):
    status: str
    output_path: Optional[str] = None
    logs: Optional[str] = None
    error: Optional[str] = None


@app.post("/execute", response_model=ExecutionResponse)
async def execute_script_api(request: ScriptExecutionRequest):
    """执行用户提交的Python脚本"""
    try:
        if not request.script.strip():
            raise HTTPException(status_code=400, detail="脚本内容不能为空")

        if not request.input_files:
            raise HTTPException(status_code=400, detail="未提供输入影像")

        # 从input_files中提取文件名
        input_filenames = []
        for file_info in request.input_files:
            # 从完整路径中提取文件名
            file_path = file_info.get("path", "")
            file_name = file_info.get("name", "")

            # 如果是COG文件，使用原始文件名
            if "cog" in file_path.lower():
                # 使用提供的name字段
                input_filenames.append(file_name)
            else:
                # 使用路径中的文件名
                input_filenames.append(file_path.split("/")[-1])

        logger.info(f"执行脚本 {request.script_id}，输入文件: {input_filenames}")

        # 使用 to_thread 将阻塞的 Docker 调用放入线程池
        result = await asyncio.to_thread(
            run_in_sandbox,
            script_content=request.script,
            input_filenames=input_filenames,
            output_filename=request.output_name,
            script_id=request.script_id,
            input_files=request.input_files  # 传递完整的文件信息
        )

        if result["status"] == "error":
            return ExecutionResponse(
                status="error",
                error=result.get("message", "未知错误"),
                logs=result.get("logs", "")
            )

        # 构建输出路径
        import os
        from services.executor_service.config import HOST_COG_DIR
        output_path = os.path.join(HOST_COG_DIR, request.output_name)

        return ExecutionResponse(
            status="success",
            output_path=output_path,
            logs=result.get("logs", "")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"脚本执行失败: {str(e)}", exc_info=True)
        return ExecutionResponse(
            status="error",
            error=str(e),
            logs=""
        )


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "executor"}


if __name__ == "__main__":
    uvicorn.run("services.executor_service.main:app", host="0.0.0.0", port=8004, reload=True)
