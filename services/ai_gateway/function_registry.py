import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Awaitable, Callable, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from services.annotation_service.schemas.geojson import FeatureCreate, FeatureUpdate
from services.annotation_service.schemas.layer_field import LayerFieldCreate, LayerFieldUpdate
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


class AtmosphericCorrectionArgs(BaseModel):
    raster_id: int = Field(..., description="Source raster index_id.")
    method: Literal[
        "auto",
        "surface_reflectance",
        "metadata_scale",
        "dos1",
        "quac",
        "lasrc",
        "ledaps",
        "sen2cor",
        "modis_sr",
        "flaash",
        "sixs",
    ] = Field(
        default="auto",
        description=(
            "Correction mode. auto normalizes official SR products and uses DOS1 for raw/TOA-like inputs; "
            "LaSRC/LEDAPS/Sen2Cor/MODIS/FLAASH/6S aliases apply compatible surface-reflectance scaling."
        ),
    )
    sensor: Literal["auto", "landsat", "sentinel2", "modis", "gaofen", "generic"] = Field(
        default="auto",
        description="Optional sensor/product family hint for compatibility detection.",
    )
    new_name: str = Field(..., description="Name for the generated corrected raster.")
    scale_factor: float | None = Field(
        default=None,
        description="Optional explicit scale factor applied before correction.",
    )
    offset: float | None = Field(
        default=None,
        description="Optional explicit reflectance offset applied before correction.",
    )
    dark_percentile: float = Field(
        default=1.0,
        ge=0,
        le=100,
        description="Dark-object percentile used by DOS1/QUAC modes.",
    )
    bright_percentile: float = Field(
        default=99.0,
        ge=0,
        le=100,
        description="Bright percentile used by QUAC mode.",
    )
    clamp: bool = Field(default=True, description="Clamp output reflectance to the [0, 1] interval.")


class RadiometricCalibrationArgs(BaseModel):
    raster_id: int = Field(..., description="Source raster index_id.")
    new_name: str = Field(..., description="Name for the generated calibrated raster.")
    calibration_type: Literal["auto", "radiance", "reflectance", "scale"] = Field(
        default="auto",
        description=(
            "Calibration target. auto uses product metadata when available; scale applies scale_factor/offset; "
            "radiance applies gain/bias; reflectance applies reflectance multipliers or radiance-to-reflectance conversion."
        ),
    )
    scale_factor: float | None = Field(default=None, description="Generic DN scale factor.")
    offset: float | None = Field(default=None, description="Generic DN offset.")
    radiance_mult: float | None = Field(default=None, description="Radiance multiplicative gain.")
    radiance_add: float | None = Field(default=None, description="Radiance additive bias.")
    reflectance_mult: float | None = Field(default=None, description="Reflectance multiplicative coefficient.")
    reflectance_add: float | None = Field(default=None, description="Reflectance additive coefficient.")
    sun_elevation: float | None = Field(default=None, description="Sun elevation angle in degrees.")
    earth_sun_distance: float = Field(default=1.0, gt=0, description="Earth-sun distance in astronomical units.")
    solar_irradiance: float | None = Field(default=None, description="Band solar irradiance/ESUN value.")
    sun_elevation_correction: bool = Field(default=True, description="Apply sun-angle correction for reflectance.")
    clamp: bool = Field(default=False, description="Clamp calibrated values to [0, 1].")


class GeometricCorrectionArgs(BaseModel):
    raster_id: int = Field(..., description="Source raster index_id.")
    new_name: str = Field(..., description="Name for the generated geometrically corrected raster.")
    dst_crs: str | None = Field(default=None, description="Optional target CRS, for example EPSG:4326.")
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
    ] = Field(default="bilinear", description="Raster resampling method used when reprojection/resampling is needed.")
    target_resolution_x: float | None = Field(default=None, gt=0, description="Optional target pixel width.")
    target_resolution_y: float | None = Field(default=None, gt=0, description="Optional target pixel height.")
    shift_x: float = Field(default=0.0, description="Affine x shift in source CRS units.")
    shift_y: float = Field(default=0.0, description="Affine y shift in source CRS units.")
    scale_x: float = Field(default=1.0, gt=0, description="Affine x scale around raster center.")
    scale_y: float = Field(default=1.0, gt=0, description="Affine y scale around raster center.")
    rotation_degrees: float = Field(default=0.0, description="Affine rotation around raster center.")
    gcps: list[dict[str, float]] | None = Field(
        default=None,
        description="Optional GCPs with row, col, x, and y. At least three are required when provided.",
    )


class SupervisedClassificationArgs(BaseModel):
    raster_id: int = Field(..., description="Source raster index_id to classify.")
    samples: list[dict[str, Any]] = Field(
        ...,
        min_length=2,
        description=(
            "Training samples. Each item needs class_id/class_value/label plus either row+col, "
            "x+y, lng+lat, or spectral features/values matching selected bands."
        ),
    )
    classifier: Literal["nearest_centroid", "random_forest", "svm"] = Field(
        default="nearest_centroid",
        description="Supervised classifier. nearest_centroid is robust for small training sets.",
    )
    band_indices: list[int] | None = Field(
        default=None,
        description="Optional one-based raster bands to use. Defaults to all bands.",
    )
    n_estimators: int = Field(default=100, ge=1, le=1000, description="Random forest tree count.")
    random_seed: int = Field(default=13, description="Deterministic random seed.")
    smoothing: int = Field(default=0, ge=0, le=5, description="Optional median-filter smoothing radius in pixels.")
    new_name: str = Field(..., description="Name for the generated classification raster.")


class UnsupervisedClassificationArgs(BaseModel):
    raster_id: int = Field(..., description="Source raster index_id to classify.")
    n_classes: int = Field(default=5, ge=2, le=255, description="Number of output spectral classes.")
    method: Literal["kmeans", "mini_batch_kmeans"] = Field(
        default="kmeans",
        description="Clustering method.",
    )
    band_indices: list[int] | None = Field(
        default=None,
        description="Optional one-based raster bands to use. Defaults to all bands.",
    )
    max_samples: int = Field(default=50000, ge=100, description="Maximum valid pixels used to fit clusters.")
    random_seed: int = Field(default=13, description="Deterministic random seed.")
    smoothing: int = Field(default=0, ge=0, le=5, description="Optional median-filter smoothing radius in pixels.")
    new_name: str = Field(..., description="Name for the generated classification raster.")


class DeepLearningSegmentationArgs(BaseModel):
    raster_id: int = Field(..., description="Source raster index_id to segment.")
    new_name: str = Field(..., description="Name for the generated segmentation raster.")
    model_path: str | None = Field(
        default=None,
        description="Optional local ONNX model path. When omitted, built-in spectral-spatial segmentation is used.",
    )
    backend: Literal["auto", "onnx", "spectral_spatial", "slic", "watershed"] = Field(
        default="auto",
        description="Segmentation backend. auto uses ONNX when model_path is present, otherwise spectral_spatial.",
    )
    n_classes: int = Field(default=2, ge=2, le=255, description="Class/segment count for built-in segmentation.")
    band_indices: list[int] | None = Field(
        default=None,
        description="Optional one-based raster bands to use. Defaults to all bands.",
    )
    threshold: float = Field(default=0.5, ge=0, le=1, description="Binary threshold for one-channel ONNX outputs.")
    random_seed: int = Field(default=13, description="Deterministic random seed.")
    max_samples: int = Field(default=50000, ge=100, description="Maximum valid pixels used by built-in segmentation.")
    compactness: float = Field(default=0.15, ge=0, le=10, description="Spatial compactness for built-in segmentation.")
    smoothing: int = Field(default=1, ge=0, le=5, description="Optional median-filter smoothing radius in pixels.")


class ScriptSandboxArgs(BaseModel):
    raster_ids: list[int] = Field(
        ...,
        min_length=1,
        description=(
            "Raster index_id inputs exposed inside the sandbox in this exact order. The gateway "
            "also injects stable aliases raster_<index_id>, raster_files[<index_id>], and "
            "raster_filenames[<index_id>] for these ids. Use the Sandbox Input Map context to "
            "match each id to its actual sandbox filename/open_expr."
        ),
    )
    output_name: str = Field(
        ...,
        description="Name for the generated raster output. The script must write OUTPUT_FILE.",
    )
    script: str = Field(
        ...,
        min_length=20,
        max_length=60000,
        description=(
            "Safe Python script for the isolated executor sandbox. Use "
            "rasterio/numpy/scipy/skimage/shapely/pyproj/cv2/sklearn; "
            "read rasters through exact Sandbox Input Map expressions such as raster_<index_id>, "
            "raster_files[<index_id>], inputs[\"actual_filename.tif\"], or ordered input_0/input_1; "
            "helpers include input_path(), read_raster(), read_array(), write_raster(), "
            "sandbox_open(), output_path(), and list_inputs(); write the final GeoTIFF to OUTPUT_FILE."
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


class BandDiffRequest(BaseModel):
    index_id_t1: int = Field(..., description="Earlier raster index_id.")
    index_id_t2: int = Field(..., description="Later raster index_id.")
    band_idx: int = Field(default=1, ge=1, description="One-based band index.")
    threshold: float = Field(default=0.1, description="Change threshold.")
    threshold_mode: Literal["abs", "positive", "negative"] = Field(
        default="abs",
        description="Threshold mode.",
    )
    output_mask: bool = Field(default=True, description="Whether to also create a binary mask.")


class BandRatioRequest(BaseModel):
    index_id_t1: int = Field(..., description="Earlier raster index_id.")
    index_id_t2: int = Field(..., description="Later raster index_id.")
    band_idx: int = Field(default=1, ge=1, description="One-based band index.")
    threshold: float = Field(default=0.2, description="Ratio change threshold.")
    output_mask: bool = Field(default=True, description="Whether to also create a binary mask.")


class IndexDiffRequest(BaseModel):
    index_id_t1_b1: int = Field(..., description="Earlier raster first band index_id.")
    index_id_t1_b2: int = Field(..., description="Earlier raster second band index_id.")
    index_id_t2_b1: int = Field(..., description="Later raster first band index_id.")
    index_id_t2_b2: int = Field(..., description="Later raster second band index_id.")
    index_type: Literal["ndvi", "ndwi", "ndbi", "mndwi"] = Field(
        default="ndvi",
        description="Spectral index to compare.",
    )
    threshold: float = Field(default=0.15, description="Index change threshold.")
    threshold_mode: Literal["abs", "positive", "negative"] = Field(
        default="abs",
        description="Threshold mode.",
    )
    output_mask: bool = Field(default=True, description="Whether to also create a binary mask.")


class ClipVectorByGeometryArgs(BaseModel):
    clip_geometry: dict[str, Any] = Field(..., description="GeoJSON Geometry used as the clipping geometry.")
    features: list[dict[str, Any]] = Field(..., description="GeoJSON Features to clip or filter.")
    src_vector_crs: str = Field(default="EPSG:4326", description="Input feature CRS.")
    mode: Literal["intersects", "within", "clip"] = Field(
        default="intersects",
        description="Spatial relation mode.",
    )


class AIFunctionInvokeRequest(BaseModel):
    name: str = Field(..., description="Registered tool name.")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments passed to the registered tool.",
    )


class VectorProjectCreateArgs(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name for the new vector project.")


class VectorProjectListArgs(BaseModel):
    pass


class VectorLayerCreateArgs(BaseModel):
    project_id: UUID = Field(..., description="Vector project UUID that will own the new layer.")
    name: str = Field(..., min_length=1, max_length=255, description="Name for the new vector layer.")
    source_raster_index_id: int | None = Field(
        default=None,
        description="Optional raster index_id this vector layer was derived from.",
    )


class VectorLayerListArgs(BaseModel):
    project_id: UUID = Field(..., description="Vector project UUID whose layers should be listed.")


class VectorLayerUpdateArgs(BaseModel):
    layer_id: UUID = Field(..., description="Vector layer UUID to update.")
    name: str | None = Field(default=None, min_length=1, max_length=255, description="New layer name.")
    source_raster_index_id: int | None = Field(
        default=None,
        description="Optional replacement source raster index_id. Pass null to clear it.",
    )


class VectorLayerDeleteArgs(BaseModel):
    layer_id: UUID = Field(..., description="Vector layer UUID to delete.")


class VectorFieldCreateArgs(BaseModel):
    layer_id: UUID = Field(..., description="Vector layer UUID that will receive the field.")
    field_name: str = Field(..., min_length=1, description="JSON property key. Spaces are not allowed.")
    field_alias: str | None = Field(default=None, description="Human-readable field label.")
    field_type: Literal["string", "number", "boolean", "date"] = Field(
        default="string",
        description="Field value type.",
    )
    field_order: int = Field(default=0, ge=0, description="Display order in the attribute table.")
    is_required: bool = Field(default=False, description="Whether this field is required by convention.")
    default_val: str | None = Field(default=None, description="Optional default value stored as text.")


class VectorFieldListArgs(BaseModel):
    layer_id: UUID = Field(..., description="Vector layer UUID whose fields should be listed.")


class VectorFieldUpdateArgs(BaseModel):
    layer_id: UUID = Field(..., description="Vector layer UUID, used to scope the update.")
    field_id: UUID = Field(..., description="Vector field UUID to update.")
    field_alias: str | None = Field(default=None, description="Human-readable field label.")
    field_type: Literal["string", "number", "boolean", "date"] | None = Field(
        default=None,
        description="Updated field value type.",
    )
    field_order: int | None = Field(default=None, ge=0, description="Updated display order.")
    is_required: bool | None = Field(default=None, description="Updated required flag.")
    default_val: str | None = Field(default=None, description="Updated default value stored as text.")


class VectorFieldDeleteArgs(BaseModel):
    layer_id: UUID = Field(..., description="Vector layer UUID, used to scope the delete.")
    field_id: UUID = Field(..., description="Vector field UUID to delete.")


class VectorFeatureInputArgs(BaseModel):
    geometry: dict[str, Any] = Field(..., description="GeoJSON Geometry object in EPSG:4326.")
    properties: dict[str, Any] = Field(default_factory=dict, description="Feature attribute values.")
    category: str | None = Field(default=None, description="Optional feature category.")
    srid: int = Field(default=4326, description="Input geometry SRID. EPSG:4326 is expected.")


class VectorFeatureCreateArgs(VectorFeatureInputArgs):
    layer_id: UUID = Field(..., description="Vector layer UUID that will receive the feature.")


class VectorFeatureBulkCreateArgs(BaseModel):
    layer_id: UUID = Field(..., description="Vector layer UUID that will receive the features.")
    features: list[VectorFeatureInputArgs] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Features to insert. Each geometry must be a GeoJSON Geometry in EPSG:4326.",
    )


class VectorFeatureGetArgs(BaseModel):
    feature_id: UUID = Field(..., description="Vector feature UUID to retrieve.")


class VectorFeatureQueryBboxArgs(BaseModel):
    layer_id: UUID = Field(..., description="Vector layer UUID to query.")
    minx: float = Field(..., description="Minimum longitude/x coordinate.")
    miny: float = Field(..., description="Minimum latitude/y coordinate.")
    maxx: float = Field(..., description="Maximum longitude/x coordinate.")
    maxy: float = Field(..., description="Maximum latitude/y coordinate.")
    max_features: int = Field(default=500, ge=1, le=5000, description="Maximum features to return.")


class VectorFeatureUpdateArgs(BaseModel):
    feature_id: UUID = Field(..., description="Vector feature UUID to update.")
    geometry: dict[str, Any] | None = Field(default=None, description="Optional replacement GeoJSON Geometry.")
    properties: dict[str, Any] | None = Field(default=None, description="Optional properties to merge into the feature.")
    category: str | None = Field(default=None, description="Optional replacement feature category.")


class VectorFeatureDeleteArgs(BaseModel):
    feature_id: UUID = Field(..., description="Vector feature UUID to delete.")


class VectorLayerExportArgs(BaseModel):
    layer_id: UUID = Field(..., description="Vector layer UUID to export.")
    max_features: int = Field(default=1000, ge=1, le=10000, description="Maximum features to return.")


class RasterToVectorArgs(BaseModel):
    raster_index_id: int = Field(..., description="Raster index_id to polygonize.")
    project_id: UUID = Field(..., description="Vector project UUID that will receive the generated layer.")
    new_name: str = Field(..., min_length=1, max_length=255, description="Name for the generated vector layer.")
    band_index: int = Field(default=1, ge=1, description="One-based raster band index to polygonize.")
    skip_nodata: bool = Field(default=True, description="Skip nodata pixels.")
    skip_zero: bool = Field(default=True, description="Skip zero-valued pixels.")
    max_features: int = Field(default=10000, ge=1, le=100000, description="Maximum polygons to generate.")
    simplify_tolerance: float = Field(default=0.0, ge=0.0, description="Optional simplification tolerance.")


class VectorLayerToRasterArgs(BaseModel):
    layer_id: UUID = Field(..., description="Vector layer UUID to rasterize.")
    ref_index_id: int = Field(..., description="Reference raster index_id for extent, transform, and resolution.")
    new_name: str = Field(..., min_length=1, max_length=255, description="Name for the generated raster.")


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


def _json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _serialize_project(project: Any) -> dict[str, Any]:
    return _json_safe({
        "id": getattr(project, "id", None),
        "name": getattr(project, "name", None),
        "created_at": getattr(project, "created_at", None),
    })


def _serialize_layer(layer: Any) -> dict[str, Any]:
    return _json_safe({
        "id": getattr(layer, "id", None),
        "project_id": getattr(layer, "project_id", None),
        "name": getattr(layer, "name", None),
        "source_raster_index_id": getattr(layer, "source_raster_index_id", None),
    })


def _serialize_field(field: Any) -> dict[str, Any]:
    return _json_safe({
        "id": getattr(field, "id", None),
        "layer_id": getattr(field, "layer_id", None),
        "field_name": getattr(field, "field_name", None),
        "field_alias": getattr(field, "field_alias", None),
        "field_type": getattr(field, "field_type", None),
        "field_order": getattr(field, "field_order", None),
        "is_required": getattr(field, "is_required", None),
        "is_system": getattr(field, "is_system", None),
        "default_val": getattr(field, "default_val", None),
    })


def _feature_create_from_input(feature: VectorFeatureInputArgs) -> FeatureCreate:
    return FeatureCreate(**feature.model_dump())


def _feature_collection_result(features: list[dict[str, Any]], max_features: int) -> dict[str, Any]:
    total = len(features)
    capped = features[:max_features]
    return {
        "type": "FeatureCollection",
        "features": _json_safe(capped),
        "feature_count": total,
        "returned": len(capped),
        "truncated": total > len(capped),
    }


def _get_data_service_ops():
    import services.data_service.db_ops as db_ops

    return db_ops


def _get_raster_processor():
    from services.data_service.processor import RasterProcessor

    return RasterProcessor


def _get_layer_crud_class():
    from services.annotation_service.crud.layer_crud import LayerCRUD

    return LayerCRUD


def _get_feature_crud_class():
    from services.annotation_service.crud.feature_crud import FeatureCRUD

    return FeatureCRUD


def _get_layer_field_crud_class():
    from services.annotation_service.crud.layer_field_crud import LayerFieldCRUD

    return LayerFieldCRUD


async def _execute_index_task(
    name: str,
    band_ids: list[int],
    new_name: str,
    db: AsyncSession,
    processor_func: Callable[..., None],
) -> dict[str, Any]:
    db_ops = _get_data_service_ops()
    return await db_ops.process_index_task(db, band_ids, new_name, name, processor_func)


async def _run_ndvi(
    args: NdviArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    processor = _get_raster_processor()
    return await _execute_index_task(
        "ndvi",
        [args.red_id, args.nir_id],
        args.new_name,
        db,
        processor.calculate_ndvi,
    )


async def _run_ndwi(
    args: NdwiArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    processor = _get_raster_processor()
    return await _execute_index_task(
        "ndwi",
        [args.green_id, args.nir_id],
        args.new_name,
        db,
        processor.calculate_ndwi,
    )


async def _run_ndbi(
    args: NdbiArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    processor = _get_raster_processor()
    return await _execute_index_task(
        "ndbi",
        [args.swir_id, args.nir_id],
        args.new_name,
        db,
        processor.calculate_ndbi,
    )


async def _run_mndwi(
    args: MndwiArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    processor = _get_raster_processor()
    return await _execute_index_task(
        "mndwi",
        [args.green_id, args.swir_id],
        args.new_name,
        db,
        processor.calculate_mndwi,
    )


async def _run_raster_calculator(
    args: RasterCalculatorArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
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
    from services.data_service.routers.upload_router import merge_raster_bands_task

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
    from services.data_service.routers.upload_router import extract_raster_bands_task

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
    db_ops = _get_data_service_ops()
    return await db_ops.process_resampling_task(
        db=db,
        raster_id=args.raster_id,
        target_resolution_x=args.target_resolution_x,
        target_resolution_y=args.target_resolution_y,
        resolution_unit=args.resolution_unit,
        resampling_method=args.resampling_method,
        new_name=args.new_name,
    )


async def _run_atmospheric_correction(
    args: AtmosphericCorrectionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    import services.data_service.db_ops as db_ops

    return await db_ops.process_atmospheric_correction_task(
        db=db,
        raster_id=args.raster_id,
        method=args.method,
        sensor=args.sensor,
        new_name=args.new_name,
        scale_factor=args.scale_factor,
        offset=args.offset,
        dark_percentile=args.dark_percentile,
        bright_percentile=args.bright_percentile,
        clamp=args.clamp,
    )


async def _run_radiometric_calibration(
    args: RadiometricCalibrationArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    return await db_ops.process_radiometric_calibration_task(
        db=db,
        raster_id=args.raster_id,
        new_name=args.new_name,
        calibration_type=args.calibration_type,
        scale_factor=args.scale_factor,
        offset=args.offset,
        radiance_mult=args.radiance_mult,
        radiance_add=args.radiance_add,
        reflectance_mult=args.reflectance_mult,
        reflectance_add=args.reflectance_add,
        sun_elevation=args.sun_elevation,
        earth_sun_distance=args.earth_sun_distance,
        solar_irradiance=args.solar_irradiance,
        sun_elevation_correction=args.sun_elevation_correction,
        clamp=args.clamp,
    )


async def _run_geometric_correction(
    args: GeometricCorrectionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    return await db_ops.process_geometric_correction_task(
        db=db,
        raster_id=args.raster_id,
        new_name=args.new_name,
        dst_crs=args.dst_crs,
        resampling_method=args.resampling_method,
        target_resolution_x=args.target_resolution_x,
        target_resolution_y=args.target_resolution_y,
        shift_x=args.shift_x,
        shift_y=args.shift_y,
        scale_x=args.scale_x,
        scale_y=args.scale_y,
        rotation_degrees=args.rotation_degrees,
        gcps=args.gcps,
    )


async def _run_supervised_classification(
    args: SupervisedClassificationArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    return await db_ops.process_supervised_classification_task(
        db=db,
        raster_id=args.raster_id,
        samples=args.samples,
        classifier=args.classifier,
        new_name=args.new_name,
        band_indices=args.band_indices,
        n_estimators=args.n_estimators,
        random_seed=args.random_seed,
        smoothing=args.smoothing,
    )


async def _run_unsupervised_classification(
    args: UnsupervisedClassificationArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    return await db_ops.process_unsupervised_classification_task(
        db=db,
        raster_id=args.raster_id,
        n_classes=args.n_classes,
        method=args.method,
        new_name=args.new_name,
        band_indices=args.band_indices,
        max_samples=args.max_samples,
        random_seed=args.random_seed,
        smoothing=args.smoothing,
    )


async def _run_deep_learning_segmentation(
    args: DeepLearningSegmentationArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    return await db_ops.process_deep_learning_segmentation_task(
        db=db,
        raster_id=args.raster_id,
        new_name=args.new_name,
        model_path=args.model_path,
        backend=args.backend,
        n_classes=args.n_classes,
        band_indices=args.band_indices,
        threshold=args.threshold,
        random_seed=args.random_seed,
        max_samples=args.max_samples,
        compactness=args.compactness,
        smoothing=args.smoothing,
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

    from services.data_service.bridges.executor_bridge import dispatch_user_script

    return await dispatch_user_script(
        db=db,
        script=args.script,
        raster_ids=args.raster_ids,
        output_name=args.output_name,
    )


async def _create_vector_project(
    args: VectorProjectCreateArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    project = await _get_layer_crud_class()(vector_db).create_project(args.name)
    return {"status": "success", "project": _serialize_project(project)}


async def _list_vector_projects(
    args: VectorProjectListArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del args, db
    projects = await _get_layer_crud_class()(vector_db).get_projects()
    return {
        "status": "success",
        "projects": [_serialize_project(project) for project in projects],
        "count": len(projects),
    }


async def _create_vector_layer(
    args: VectorLayerCreateArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    layer = await _get_layer_crud_class()(vector_db).create_layer(
        args.project_id,
        args.name,
        args.source_raster_index_id,
    )
    return {"status": "success", "layer": _serialize_layer(layer)}


async def _list_vector_layers(
    args: VectorLayerListArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    layers = await _get_layer_crud_class()(vector_db).get_layers_by_project(args.project_id)
    return {
        "status": "success",
        "project_id": str(args.project_id),
        "layers": [_serialize_layer(layer) for layer in layers],
        "count": len(layers),
    }


async def _update_vector_layer(
    args: VectorLayerUpdateArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    updates = args.model_dump(exclude={"layer_id"}, exclude_unset=True)
    if not updates:
        raise ValueError("At least one layer field must be provided for update.")

    layer = await _get_layer_crud_class()(vector_db).update_layer(args.layer_id, updates)
    if not layer:
        raise ValueError(f"Vector layer not found: {args.layer_id}")
    return {"status": "success", "layer": _serialize_layer(layer)}


async def _delete_vector_layer(
    args: VectorLayerDeleteArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    deleted = await _get_layer_crud_class()(vector_db).delete_layer(args.layer_id)
    if not deleted:
        raise ValueError(f"Vector layer not found: {args.layer_id}")
    return {"status": "success", "deleted": True, "layer_id": str(args.layer_id)}


async def _create_vector_field(
    args: VectorFieldCreateArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    field_payload = LayerFieldCreate(**args.model_dump(exclude={"layer_id"}))
    field = await _get_layer_field_crud_class()(vector_db).create(args.layer_id, field_payload)
    return {"status": "success", "field": _serialize_field(field)}


async def _list_vector_fields(
    args: VectorFieldListArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    fields = await _get_layer_field_crud_class()(vector_db).get_by_layer(args.layer_id)
    return {
        "status": "success",
        "layer_id": str(args.layer_id),
        "fields": [_serialize_field(field) for field in fields],
        "count": len(fields),
    }


async def _update_vector_field(
    args: VectorFieldUpdateArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    crud = _get_layer_field_crud_class()(vector_db)
    current = await crud.get_by_id(args.field_id)
    if not current or current.layer_id != args.layer_id:
        raise ValueError(f"Vector field not found in layer {args.layer_id}: {args.field_id}")

    updates = args.model_dump(exclude={"layer_id", "field_id"}, exclude_unset=True)
    if not updates:
        raise ValueError("At least one field definition value must be provided for update.")

    field = await crud.update(args.field_id, LayerFieldUpdate(**updates))
    return {"status": "success", "field": _serialize_field(field)}


async def _delete_vector_field(
    args: VectorFieldDeleteArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    crud = _get_layer_field_crud_class()(vector_db)
    current = await crud.get_by_id(args.field_id)
    if not current or current.layer_id != args.layer_id:
        raise ValueError(f"Vector field not found in layer {args.layer_id}: {args.field_id}")

    deleted = await crud.delete(args.field_id)
    if not deleted:
        raise ValueError(f"Vector field not found: {args.field_id}")
    return {"status": "success", "deleted": True, "field_id": str(args.field_id)}


async def _create_vector_feature(
    args: VectorFeatureCreateArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    crud = _get_feature_crud_class()(vector_db)
    feature = await crud.create(
        args.layer_id,
        FeatureCreate(
            geometry=args.geometry,
            properties=args.properties,
            category=args.category,
            srid=args.srid,
        ),
    )
    return {"status": "success", "feature": _json_safe(await crud.get_by_id(feature.id))}


async def _bulk_create_vector_features(
    args: VectorFeatureBulkCreateArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    created = await _get_feature_crud_class()(vector_db).bulk_create(
        args.layer_id,
        [_feature_create_from_input(feature) for feature in args.features],
    )
    return {
        "status": "success",
        "layer_id": str(args.layer_id),
        "created": created,
        "requested": len(args.features),
    }


async def _get_vector_feature(
    args: VectorFeatureGetArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    feature = await _get_feature_crud_class()(vector_db).get_by_id(args.feature_id)
    if not feature:
        raise ValueError(f"Vector feature not found: {args.feature_id}")
    return {"status": "success", "feature": _json_safe(feature)}


async def _query_vector_features_by_bbox(
    args: VectorFeatureQueryBboxArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    if args.maxx <= args.minx or args.maxy <= args.miny:
        raise ValueError("Bounding box max values must be greater than min values.")

    features = await _get_feature_crud_class()(vector_db).find_by_bbox(
        args.layer_id,
        args.minx,
        args.miny,
        args.maxx,
        args.maxy,
    )
    result = _feature_collection_result(features, args.max_features)
    result.update({"status": "success", "layer_id": str(args.layer_id)})
    return result


async def _update_vector_feature(
    args: VectorFeatureUpdateArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    update_data = args.model_dump(exclude={"feature_id"}, exclude_unset=True)
    if not update_data:
        raise ValueError("At least one feature field must be provided for update.")

    crud = _get_feature_crud_class()(vector_db)
    updated = await crud.update(args.feature_id, FeatureUpdate(**update_data))
    if not updated:
        raise ValueError(f"Vector feature not found: {args.feature_id}")
    return {"status": "success", "feature": _json_safe(await crud.get_by_id(updated.id))}


async def _delete_vector_feature(
    args: VectorFeatureDeleteArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    deleted = await _get_feature_crud_class()(vector_db).delete(args.feature_id)
    if not deleted:
        raise ValueError(f"Vector feature not found: {args.feature_id}")
    return {"status": "success", "deleted": True, "feature_id": str(args.feature_id)}


async def _export_vector_layer_features(
    args: VectorLayerExportArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db
    features = await _get_feature_crud_class()(vector_db).export_by_layer(args.layer_id)
    result = _feature_collection_result(features, args.max_features)
    result.update({"status": "success", "layer_id": str(args.layer_id)})
    return result


async def _raster_to_vector_layer(
    args: RasterToVectorArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    result = await db_ops.process_raster_to_vector_task(
        db=db,
        raster_index_id=args.raster_index_id,
        project_id=args.project_id,
        new_name=args.new_name,
        band_index=args.band_index,
        skip_nodata=args.skip_nodata,
        skip_zero=args.skip_zero,
        max_features=args.max_features,
        simplify_tolerance=args.simplify_tolerance,
    )
    return _json_safe(result)


async def _vector_layer_to_raster(
    args: VectorLayerToRasterArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    processor = _get_raster_processor()
    from services.data_service.bridges.vector_bridge import internal_fetch_features

    result = await db_ops.process_rasterize_task(
        db=db,
        layer_id=args.layer_id,
        ref_index_id=args.ref_index_id,
        new_name=args.new_name,
        prefix="rasterized",
        processor_func=processor.run_rasterization,
        fetch_func=internal_fetch_features,
    )
    return _json_safe(result)


async def _run_extraction(
    args: ExtractionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
    *,
    prefix: str,
    processor_func: Callable[..., None],
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
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
    processor = _get_raster_processor()
    return await _run_extraction(
        args,
        db,
        vector_db,
        prefix="veg",
        processor_func=processor.run_vegetation_extraction,
    )


async def _run_extract_water(
    args: ExtractionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    processor = _get_raster_processor()
    return await _run_extraction(
        args,
        db,
        vector_db,
        prefix="water",
        processor_func=processor.run_water_extraction,
    )


async def _run_extract_buildings(
    args: ExtractionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    processor = _get_raster_processor()
    return await _run_extraction(
        args,
        db,
        vector_db,
        prefix="building",
        processor_func=processor.run_building_extraction,
    )


async def _run_extract_clouds(
    args: ExtractionArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    processor = _get_raster_processor()
    return await _run_extraction(
        args,
        db,
        vector_db,
        prefix="cloud",
        processor_func=processor.run_cloud_extraction,
    )


async def _run_clip_raster_by_geometry(
    args: ClipRasterByGeometryArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    from services.data_service.routers.clip_router import (
        clip_raster_by_vector as clip_raster_by_vector_api,
    )

    return await clip_raster_by_vector_api(args, db)


async def _run_clip_vector_by_geometry(
    args: ClipVectorByGeometryArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db, vector_db
    from functions.implement.clip_ops import clip_vector_by_raster

    return clip_vector_by_raster(
        clip_geometry=args.clip_geometry,
        geojson_features=args.features,
        src_vector_crs=args.src_vector_crs,
        mode=args.mode,
    )


async def _run_band_diff(
    args: BandDiffRequest,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    from services.data_service.routers.change_router import detect_band_diff

    return _normalize_result(await detect_band_diff(args, db))


async def _run_band_ratio(
    args: BandRatioRequest,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    from services.data_service.routers.change_router import detect_band_ratio

    return _normalize_result(await detect_band_ratio(args, db))


async def _run_index_diff(
    args: IndexDiffRequest,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    from services.data_service.routers.change_router import detect_index_diff

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
            name="atmospheric_correction",
            description=(
                "Generate a surface-reflectance raster with compatibility for Landsat LaSRC/LEDAPS, "
                "Sentinel-2 Sen2Cor, MODIS official surface-reflectance products, and Gaofen "
                "FLAASH/QUAC/6S-style products. Supports metadata scaling, DOS1, and QUAC modes."
            ),
            category="atmospheric_correction",
            arguments_model=AtmosphericCorrectionArgs,
            handler=_run_atmospheric_correction,
        ),
        RegisteredFunction(
            name="radiometric_calibration",
            description=(
                "Calibrate raster DN values into radiance, reflectance, or generic scale/offset corrected values. "
                "Use this for sensor/product radiometric calibration before analysis or classification."
            ),
            category="radiometric_calibration",
            arguments_model=RadiometricCalibrationArgs,
            handler=_run_radiometric_calibration,
        ),
        RegisteredFunction(
            name="geometric_correction",
            description=(
                "Apply geometric correction using affine shift/scale/rotation, optional GCP-derived transform, "
                "and optional reprojection/resampling to a target CRS or resolution."
            ),
            category="geometric_correction",
            arguments_model=GeometricCorrectionArgs,
            handler=_run_geometric_correction,
        ),
        RegisteredFunction(
            name="supervised_classification",
            description=(
                "Run supervised raster classification from labeled training samples and save a uint16 class raster. "
                "Use when the user provides or selects representative class samples."
            ),
            category="classification",
            arguments_model=SupervisedClassificationArgs,
            handler=_run_supervised_classification,
        ),
        RegisteredFunction(
            name="unsupervised_classification",
            description=(
                "Run unsupervised spectral clustering, such as KMeans, and save a uint16 class raster. "
                "Use when no training labels are available."
            ),
            category="classification",
            arguments_model=UnsupervisedClassificationArgs,
            handler=_run_unsupervised_classification,
        ),
        RegisteredFunction(
            name="deep_learning_segmentation",
            description=(
                "Run deep-learning segmentation when a local ONNX model path is supplied, or use the built-in "
                "spectral-spatial segmentation backend with the same output contract."
            ),
            category="segmentation",
            arguments_model=DeepLearningSegmentationArgs,
            handler=_run_deep_learning_segmentation,
        ),
        RegisteredFunction(
            name="run_script_sandbox",
            description=(
                "Generate and run a safe Python raster-processing script in the isolated sandbox when "
                "no dedicated gateway function can satisfy the request. Scripts should read raster "
                "inputs from the Sandbox Input Map aliases/filenames and write OUTPUT_FILE."
            ),
            category="script_sandbox",
            arguments_model=ScriptSandboxArgs,
            handler=_run_script_sandbox,
        ),
        RegisteredFunction(
            name="create_vector_project",
            description="Create a new vector annotation project.",
            category="vector_management",
            arguments_model=VectorProjectCreateArgs,
            handler=_create_vector_project,
        ),
        RegisteredFunction(
            name="list_vector_projects",
            description="List vector annotation projects available in the workspace.",
            category="vector_management",
            arguments_model=VectorProjectListArgs,
            handler=_list_vector_projects,
        ),
        RegisteredFunction(
            name="create_vector_layer",
            description="Create a vector layer inside an existing project.",
            category="vector_management",
            arguments_model=VectorLayerCreateArgs,
            handler=_create_vector_layer,
        ),
        RegisteredFunction(
            name="list_vector_layers",
            description="List vector layers within a project.",
            category="vector_management",
            arguments_model=VectorLayerListArgs,
            handler=_list_vector_layers,
        ),
        RegisteredFunction(
            name="update_vector_layer",
            description="Rename or relink a vector layer.",
            category="vector_management",
            arguments_model=VectorLayerUpdateArgs,
            handler=_update_vector_layer,
        ),
        RegisteredFunction(
            name="delete_vector_layer",
            description="Delete a vector layer and its features only when the user explicitly requests deletion.",
            category="vector_management",
            arguments_model=VectorLayerDeleteArgs,
            handler=_delete_vector_layer,
        ),
        RegisteredFunction(
            name="create_vector_field",
            description="Create an attribute-field definition on a vector layer.",
            category="vector_attributes",
            arguments_model=VectorFieldCreateArgs,
            handler=_create_vector_field,
        ),
        RegisteredFunction(
            name="list_vector_fields",
            description="List attribute-field definitions for a vector layer.",
            category="vector_attributes",
            arguments_model=VectorFieldListArgs,
            handler=_list_vector_fields,
        ),
        RegisteredFunction(
            name="update_vector_field",
            description="Update a vector layer attribute-field definition.",
            category="vector_attributes",
            arguments_model=VectorFieldUpdateArgs,
            handler=_update_vector_field,
        ),
        RegisteredFunction(
            name="delete_vector_field",
            description="Delete a user-defined vector field only when the user explicitly requests deletion.",
            category="vector_attributes",
            arguments_model=VectorFieldDeleteArgs,
            handler=_delete_vector_field,
        ),
        RegisteredFunction(
            name="create_vector_feature",
            description="Create one GeoJSON feature in a vector layer.",
            category="vector_features",
            arguments_model=VectorFeatureCreateArgs,
            handler=_create_vector_feature,
        ),
        RegisteredFunction(
            name="bulk_create_vector_features",
            description="Create multiple GeoJSON features in one vector layer.",
            category="vector_features",
            arguments_model=VectorFeatureBulkCreateArgs,
            handler=_bulk_create_vector_features,
        ),
        RegisteredFunction(
            name="get_vector_feature",
            description="Retrieve one vector feature by UUID.",
            category="vector_features",
            arguments_model=VectorFeatureGetArgs,
            handler=_get_vector_feature,
        ),
        RegisteredFunction(
            name="query_vector_features_by_bbox",
            description="Query vector features in a layer by an EPSG:4326 bounding box.",
            category="vector_features",
            arguments_model=VectorFeatureQueryBboxArgs,
            handler=_query_vector_features_by_bbox,
        ),
        RegisteredFunction(
            name="update_vector_feature",
            description="Update a vector feature geometry, properties, or category.",
            category="vector_features",
            arguments_model=VectorFeatureUpdateArgs,
            handler=_update_vector_feature,
        ),
        RegisteredFunction(
            name="delete_vector_feature",
            description="Delete a vector feature only when the user explicitly requests deletion.",
            category="vector_features",
            arguments_model=VectorFeatureDeleteArgs,
            handler=_delete_vector_feature,
        ),
        RegisteredFunction(
            name="export_vector_layer_features",
            description="Export vector layer features as a bounded GeoJSON FeatureCollection.",
            category="vector_features",
            arguments_model=VectorLayerExportArgs,
            handler=_export_vector_layer_features,
        ),
        RegisteredFunction(
            name="raster_to_vector_layer",
            description="Polygonize a raster band and store the generated polygons in a vector layer.",
            category="vector_conversion",
            arguments_model=RasterToVectorArgs,
            handler=_raster_to_vector_layer,
        ),
        RegisteredFunction(
            name="vector_layer_to_raster",
            description="Rasterize a vector layer using a reference raster extent and resolution.",
            category="vector_conversion",
            arguments_model=VectorLayerToRasterArgs,
            handler=_vector_layer_to_raster,
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
