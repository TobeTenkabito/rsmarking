import uvicorn
import asyncio
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

from services.executor_service.runner import run_in_sandbox

app = FastAPI(title="RSMarking Executor Service", description="远程沙箱代码执行器")


# DTO 定义
class ScriptExecutionRequest(BaseModel):
    script_content: str
    input_filenames: list[str]
    output_filename: str


class ExecutionResponse(BaseModel):
    status: str
    message: str = ""
    logs: str = ""


@app.post("/execute", response_model=ExecutionResponse)
async def execute_script_api(request: ScriptExecutionRequest):
    if not request.script_content.strip():
        raise HTTPException(status_code=400, detail="脚本内容不能为空")

    if not request.input_filenames:
        raise HTTPException(status_code=400, detail="未提供输入影像")

    # 使用 to_thread 将阻塞的 Docker 调用放入线程池，避免阻塞 FastAPI 事件循环
    result = await asyncio.to_thread(
        run_in_sandbox,
        script_content=request.script_content,
        input_filenames=request.input_filenames,
        output_filename=request.output_filename
    )

    if result["status"] == "error":
        return ExecutionResponse(status="failed", message=result.get("message", ""), logs=result.get("logs", ""))

    return ExecutionResponse(status="success", logs=result.get("logs", ""))


if __name__ == "__main__":
    uvicorn.run("services.executor_service.main:app", host="0.0.0.0", port=8004, reload=True)
