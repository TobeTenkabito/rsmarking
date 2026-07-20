import asyncio
import logging
import os
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.executor_service.config import HOST_RAW_DIR
from services.executor_service.runner import run_in_sandbox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("executor_service.main")

app = FastAPI(
    title="RSMarking Executor Service",
    description="Docker-isolated Python 3 script executor",
)


class InputFilePayload(BaseModel):
    path: str = Field(..., description="Absolute host path to an input raster.")
    name: Optional[str] = Field(default=None, description="Filename exposed inside the sandbox.")
    raster_id: Optional[int] = Field(default=None, description="RSMarking raster index_id for alias mapping.")
    alias: Optional[str] = Field(default=None, description="Python variable alias exposed inside the sandbox.")


class VectorInputPayload(BaseModel):
    name: Optional[str] = Field(default=None, description="GeoJSON filename exposed inside the sandbox.")
    alias: Optional[str] = Field(default=None, description="Python variable alias exposed inside the sandbox.")
    feature_id: Optional[str] = Field(default=None, description="Source vector feature UUID.")
    layer_id: Optional[str] = Field(default=None, description="Source vector layer UUID.")
    geojson: dict[str, Any] = Field(
        ...,
        description="A GeoJSON Feature or FeatureCollection copied into the isolated sandbox.",
    )


class ScriptExecutionRequest(BaseModel):
    script_id: str
    script: str
    input_files: list[InputFilePayload] = Field(default_factory=list)
    vector_inputs: list[VectorInputPayload] = Field(default_factory=list)
    output_name: str
    output_required: bool = True


class ExecutionResponse(BaseModel):
    status: str
    output_path: Optional[str] = None
    logs: Optional[str] = None
    error: Optional[str] = None


@app.post("/execute", response_model=ExecutionResponse)
async def execute_script_api(request: ScriptExecutionRequest):
    try:
        if not request.script.strip():
            raise HTTPException(status_code=400, detail="Script content cannot be empty")

        input_file_names = [
            os.path.basename(item.name or item.path)
            for item in request.input_files
        ]
        logger.info(
            "Executing script %s with raster inputs %s and %s vector input(s)",
            request.script_id,
            input_file_names,
            len(request.vector_inputs),
        )

        result = await asyncio.to_thread(
            run_in_sandbox,
            script_content=request.script,
            input_filenames=input_file_names,
            output_filename=request.output_name,
            script_id=request.script_id,
            input_files=[item.model_dump() for item in request.input_files],
            vector_inputs=[item.model_dump() for item in request.vector_inputs],
            output_required=request.output_required,
        )

        if result.get("status") != "success":
            return ExecutionResponse(
                status="error",
                error=result.get("message", "Unknown sandbox error"),
                logs=result.get("logs", ""),
            )

        output_path = result.get("output_path")
        if not output_path and request.output_required:
            output_path = os.path.join(HOST_RAW_DIR, request.output_name)
        return ExecutionResponse(
            status="success",
            output_path=output_path,
            logs=result.get("logs", ""),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Script execution failed: %s", e, exc_info=True)
        return ExecutionResponse(
            status="error",
            error=str(e),
            logs="",
        )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "executor"}


if __name__ == "__main__":
    uvicorn.run("services.executor_service.main:app", host="0.0.0.0", port=8004, reload=True)
