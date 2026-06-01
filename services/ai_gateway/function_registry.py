import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.annotation_service.router.spatial_router import (
    ClipVectorByRasterRequest as ClipVectorByGeometryArgs,
    clip_vector_by_raster_endpoint,
)
from services.data_service.processor import RasterProcessor
from services.data_service.routers.change_router import (
    BandDiffRequest,
    BandRatioRequest,
    IndexDiffRequest,
    detect_band_diff,
    detect_band_ratio,
    detect_index_diff,
)
from services.data_service.routers.clip_router import (
    clip_raster_by_vector as clip_raster_by_vector_api,
)
from services.data_service.routers.indices_router import calculate_index_task
from services.data_service.routers.upload_router import (
    extract_raster_bands_task,
    merge_raster_bands_task,
)
from services.data_service.bridges.executor_bridge import dispatch_user_script
from services.data_service.schemas import (
    ClipRasterByVectorRequest as ClipRasterByGeometryArgs,
)
from services.executor_service.security import validate_script_content

logger = logging.getLogger("ai_gateway.function_registry")


class RasterCalculatorArgs(BaseModel):
    expression: str = Field(..., description="Raster calculator expression.")
    new_name: str = Field(..., description="Name for the generated raster.")
    var_mapping: dict[str, int] = Field(
        ...,
        description="Mapping from expression variable names to raster index_id values.",
    )


class BandSynthesisArgs(BaseModel):
    raster_ids: list[int] = Field(
        ...,
        min_length=2,
        description="Ordered raster index_id list to stack into a synthesized multi-band raster.",
    )
    new_name: str = Field(..., description="Name for the generated raster.")


class BandExtractionArgs(BaseModel):
    raster_id: int = Field(..., description="Source raster index_id.")
    band_indices: list[int] = Field(
        ...,
        min_length=1,
        description="One-based source band numbers to extract, preserving this order.",
    )
    new_name: str = Field(..., description="Name for the generated raster.")


class ResampleRasterArgs(BaseModel):
    raster_id: int = Field(..., description="Source raster index_id.")
    target_resolution_x: float = Field(
        ...,
        gt=0,
        description="Target pixel width. Degrees for degree mode, meters for meter mode, source CRS units for source mode.",
    )
    target_resolution_y: float | None = Field(
        default=None,
        gt=0,
        description="Target pixel height. Uses target_resolution_x when omitted.",
    )
    resolution_unit: Literal["source", "degrees", "meters"] = Field(
        default="source",
        description="Unit for the target resolution.",
    )
    resampling_method: Literal[
        "nearest",
        "bilinear",
        "cubic",
        "cubic_spline",
        "lanczos",
        "average",
        "mode",
        "max",
        "min",
        "med",
        "q1",
        "q3",
    ] = Field(default="bilinear", description="Rasterio resampling method.")
    new_name: str = Field(..., description="Name for the generated raster.")


class ScriptSandboxArgs(BaseModel):
    raster_ids: list[int] = Field(
        ...,
        min_length=1,
        description="Raster index_id inputs exposed as input_file, input_0, input_1, ... inside the sandbox.",
    )
    output_name: str = Field(
        ...,
        description="Name for the generated raster output. The script must write OUTPUT_FILE.",
    )
    script: str = Field(
        ...,
        min_length=20,
        max_length=20000,
        description=(
            "Safe Python script for the isolated executor sandbox. Use rasterio/numpy/scipy/skimage; "
            "read input_file or input_0..N and write the final GeoTIFF to OUTPUT_FILE."
        ),
    )


class ExtractionArgs(BaseModel):
    band_ids: list[int] = Field(
        ...,
        min_length=1,
        description="Ordered raster band index_id list required by the algorithm.",
    )
    new_name: str = Field(..., description="Name for the generated raster.")
    threshold: float | None = Field(
        default=None,
        description="Optional threshold for the extraction algorithm.",
    )
    mode: str | None = Field(
        default=None,
        description="Optional algorithm mode, such as mndwi, ndwi, otsu, or ga.",
    )


class NdviArgs(BaseModel):
    red_id: int = Field(..., description="Raster index_id for the red band.")
    nir_id: int = Field(..., description="Raster index_id for the near-infrared band.")
    new_name: str = Field(..., description="Name for the generated raster.")


class NdwiArgs(BaseModel):
    green_id: int = Field(..., description="Raster index_id for the green band.")
    nir_id: int = Field(..., description="Raster index_id for the near-infrared band.")
    new_name: str = Field(..., description="Name for the generated raster.")


class NdbiArgs(BaseModel):
    swir_id: int = Field(..., description="Raster index_id for the SWIR band.")
    nir_id: int = Field(..., description="Raster index_id for the near-infrared band.")
    new_name: str = Field(..., description="Name for the generated raster.")


class MndwiArgs(BaseModel):
    green_id: int = Field(..., description="Raster index_id for the green band.")
    swir_id: int = Field(..., description="Raster index_id for the SWIR band.")
    new_name: str = Field(..., description="Name for the generated raster.")


class AIFunctionInvokeRequest(BaseModel):
    name: str = Field(..., description="Registered tool name.")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments passed to the registered tool.",
    )


ToolHandler = Callable[[BaseModel, AsyncSession, AsyncSession], Awaitable[Any]]


@dataclass(frozen=True)
class RegisteredFunction:
    name: str
    description: str
    category: str
    arguments_model: type[BaseModel]
    handler: ToolHandler

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments_model.model_json_schema(),
            },
        }

    def to_catalog_entry(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.arguments_model.model_json_schema(),
        }


def _normalize_result(result: Any) -> Any:
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result


async def _execute_index_task(
    name: str,
    band_ids: list[int],
    new_name: str,
    db: AsyncSession,
    processor_func: Callable[..., None],
) -> dict[str, Any]:
    return await calculate_index_task(name, band_ids, new_name, db, processor_func)


async def _run_ndvi(
    args: NdviArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return await _execute_index_task(
        "ndvi",
        [args.red_id, args.nir_id],
        args.new_name,
        db,
        RasterProcessor.calculate_ndvi,
    )


async def _run_ndwi(
    args: NdwiArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return await _execute_index_task(
        "ndwi",
        [args.green_id, args.nir_id],
        args.new_name,
        db,
        RasterProcessor.calculate_ndwi,
    )


async def _run_ndbi(
    args: NdbiArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return await _execute_index_task(
        "ndbi",
        [args.swir_id, args.nir_id],
        args.new_name,
        db,
        RasterProcessor.calculate_ndbi,
    )


async def _run_mndwi(
    args: MndwiArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return await _execute_index_task(
        "mndwi",
        [args.green_id, args.swir_id],
        args.new_name,
        db,
        RasterProcessor.calculate_mndwi,
    )


async def _run_raster_calculator(
    args: RasterCalculatorArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return await db_ops.process_calculator_task(
        db,
        args.var_mapping,
        args.expression,
        args.new_name,
        "calc",
    )


async def _run_band_synthesis(
    args: BandSynthesisArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return await merge_raster_bands_task(
        ",".join(str(raster_id) for raster_id in args.raster_ids),
        args.new_name,
        db,
    )


async def _run_band_extraction(
    args: BandExtractionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return await extract_raster_bands_task(
        args.raster_id,
        ",".join(str(index) for index in args.band_indices),
        args.new_name,
        db,
    )


async def _run_resample_raster(
    args: ResampleRasterArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return await db_ops.process_resampling_task(
        db=db,
        raster_id=args.raster_id,
        target_resolution_x=args.target_resolution_x,
        target_resolution_y=args.target_resolution_y,
        resolution_unit=args.resolution_unit,
        resampling_method=args.resampling_method,
        new_name=args.new_name,
    )


async def _run_script_sandbox(
    args: ScriptSandboxArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    is_valid, blocked_label = validate_script_content(args.script)
    if not is_valid:
        raise ValueError(f"Script contains a blocked operation: {blocked_label}")

    return await dispatch_user_script(
        db=db,
        script=args.script,
        raster_ids=args.raster_ids,
        output_name=args.output_name,
    )


async def _run_extraction(
    args: ExtractionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
    *,
    prefix: str,
    processor_func: Callable[..., None],
) -> dict[str, Any]:
    del vector_db
    return await db_ops.process_extraction_task(
        db,
        args.band_ids,
        args.new_name,
        prefix,
        processor_func,
        threshold=args.threshold,
        mode=args.mode,
    )


async def _run_extract_vegetation(
    args: ExtractionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    return await _run_extraction(
        args,
        db,
        vector_db,
        prefix="veg",
        processor_func=RasterProcessor.run_vegetation_extraction,
    )


async def _run_extract_water(
    args: ExtractionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    return await _run_extraction(
        args,
        db,
        vector_db,
        prefix="water",
        processor_func=RasterProcessor.run_water_extraction,
    )


async def _run_extract_buildings(
    args: ExtractionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    return await _run_extraction(
        args,
        db,
        vector_db,
        prefix="building",
        processor_func=RasterProcessor.run_building_extraction,
    )


async def _run_extract_clouds(
    args: ExtractionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    return await _run_extraction(
        args,
        db,
        vector_db,
        prefix="cloud",
        processor_func=RasterProcessor.run_cloud_extraction,
    )


async def _run_clip_raster_by_geometry(
    args: ClipRasterByGeometryArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return await clip_raster_by_vector_api(args, db)


async def _run_clip_vector_by_geometry(
    args: ClipVectorByGeometryArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db, vector_db
    return await clip_vector_by_raster_endpoint(args)


async def _run_band_diff(
    args: BandDiffRequest,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return _normalize_result(await detect_band_diff(args, db))


async def _run_band_ratio(
    args: BandRatioRequest,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return _normalize_result(await detect_band_ratio(args, db))


async def _run_index_diff(
    args: IndexDiffRequest,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    return _normalize_result(await detect_index_diff(args, db))


REGISTERED_FUNCTIONS: dict[str, RegisteredFunction] = {
    spec.name: spec
    for spec in [
        RegisteredFunction(
            name="calculate_ndvi",
            description="Generate an NDVI raster from red and near-infrared inputs.",
            category="spectral_indices",
            arguments_model=NdviArgs,
            handler=_run_ndvi,
        ),
        RegisteredFunction(
            name="calculate_ndwi",
            description="Generate an NDWI raster from green and near-infrared inputs.",
            category="spectral_indices",
            arguments_model=NdwiArgs,
            handler=_run_ndwi,
        ),
        RegisteredFunction(
            name="calculate_ndbi",
            description="Generate an NDBI raster from SWIR and near-infrared inputs.",
            category="spectral_indices",
            arguments_model=NdbiArgs,
            handler=_run_ndbi,
        ),
        RegisteredFunction(
            name="calculate_mndwi",
            description="Generate an MNDWI raster from green and SWIR inputs.",
            category="spectral_indices",
            arguments_model=MndwiArgs,
            handler=_run_mndwi,
        ),
        RegisteredFunction(
            name="run_raster_calculator",
            description="Execute a raster calculator expression against one or more raster inputs.",
            category="raster_manipulation",
            arguments_model=RasterCalculatorArgs,
            handler=_run_raster_calculator,
        ),
        RegisteredFunction(
            name="synthesize_raster_bands",
            description="Stack two or more raster products into a synthesized multi-band raster.",
            category="raster_manipulation",
            arguments_model=BandSynthesisArgs,
            handler=_run_band_synthesis,
        ),
        RegisteredFunction(
            name="extract_raster_bands",
            description="Extract one or more one-based bands from a raster and save them as a new raster.",
            category="raster_manipulation",
            arguments_model=BandExtractionArgs,
            handler=_run_band_extraction,
        ),
        RegisteredFunction(
            name="resample_raster",
            description="Resample a raster to a requested resolution in source CRS units, degrees, or meters.",
            category="raster_manipulation",
            arguments_model=ResampleRasterArgs,
            handler=_run_resample_raster,
        ),
        RegisteredFunction(
            name="run_script_sandbox",
            description=(
                "Generate and run a safe Python raster-processing script in the isolated sandbox when "
                "no dedicated gateway function can satisfy the request."
            ),
            category="script_sandbox",
            arguments_model=ScriptSandboxArgs,
            handler=_run_script_sandbox,
        ),
        RegisteredFunction(
            name="extract_vegetation",
            description="Run the vegetation extraction algorithm and save the generated mask raster.",
            category="extraction",
            arguments_model=ExtractionArgs,
            handler=_run_extract_vegetation,
        ),
        RegisteredFunction(
            name="extract_water",
            description="Run the water extraction algorithm and save the generated mask raster.",
            category="extraction",
            arguments_model=ExtractionArgs,
            handler=_run_extract_water,
        ),
        RegisteredFunction(
            name="extract_buildings",
            description="Run the building extraction algorithm and save the generated mask raster.",
            category="extraction",
            arguments_model=ExtractionArgs,
            handler=_run_extract_buildings,
        ),
        RegisteredFunction(
            name="extract_clouds",
            description="Run the cloud extraction algorithm and save the generated mask raster.",
            category="extraction",
            arguments_model=ExtractionArgs,
            handler=_run_extract_clouds,
        ),
        RegisteredFunction(
            name="clip_raster_by_vector",
            description="Clip a raster with one or more GeoJSON geometries and register the output raster.",
            category="clip",
            arguments_model=ClipRasterByGeometryArgs,
            handler=_run_clip_raster_by_geometry,
        ),
        RegisteredFunction(
            name="clip_vector_by_raster",
            description="Clip GeoJSON vector features with a raster-derived geometry and return a feature collection.",
            category="clip",
            arguments_model=ClipVectorByGeometryArgs,
            handler=_run_clip_vector_by_geometry,
        ),
        RegisteredFunction(
            name="detect_band_diff",
            description="Run absolute or directional change detection on a single raster band.",
            category="change_detection",
            arguments_model=BandDiffRequest,
            handler=_run_band_diff,
        ),
        RegisteredFunction(
            name="detect_band_ratio",
            description="Run ratio-based change detection on a single raster band.",
            category="change_detection",
            arguments_model=BandRatioRequest,
            handler=_run_band_ratio,
        ),
        RegisteredFunction(
            name="detect_index_diff",
            description="Run change detection on a derived spectral index across two time steps.",
            category="change_detection",
            arguments_model=IndexDiffRequest,
            handler=_run_index_diff,
        ),
    ]
}


def list_registered_functions(format_type: str = "openai") -> dict[str, Any]:
    functions = list(REGISTERED_FUNCTIONS.values())
    if format_type == "catalog":
        return {
            "status": "success",
            "functions": [function.to_catalog_entry() for function in functions],
        }

    return {
        "status": "success",
        "tools": [function.to_openai_tool() for function in functions],
    }


def select_registered_functions(names: list[str] | None = None) -> list[RegisteredFunction]:
    if names is None:
        return list(REGISTERED_FUNCTIONS.values())

    unknown = sorted(set(names) - set(REGISTERED_FUNCTIONS))
    if unknown:
        available = ", ".join(sorted(REGISTERED_FUNCTIONS))
        requested = ", ".join(unknown)
        raise ValueError(f"Unknown AI function(s): {requested}. Available: {available}")

    return [REGISTERED_FUNCTIONS[name] for name in names]


def get_registered_openai_tools(names: list[str] | None = None) -> list[dict[str, Any]]:
    return [function.to_openai_tool() for function in select_registered_functions(names)]


async def invoke_registered_function(
    request: AIFunctionInvokeRequest,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    function = REGISTERED_FUNCTIONS.get(request.name)
    if not function:
        available = ", ".join(sorted(REGISTERED_FUNCTIONS))
        raise ValueError(f"Unknown AI function '{request.name}'. Available: {available}")

    validated_arguments = function.arguments_model(**request.arguments)
    logger.info("[ai_gateway.function_registry] invoking %s", request.name)
    result = await function.handler(validated_arguments, db, vector_db)

    return {
        "status": "success",
        "name": request.name,
        "arguments": validated_arguments.model_dump(),
        "result": _normalize_result(result),
    }
