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


class DEMAnalysisArgs(BaseModel):
    raster_id: int = Field(..., description="Source DEM raster index_id.")
    operation: Literal[
        "elevation",
        "slope",
        "aspect",
        "hillshade",
        "curvature",
        "relief",
        "twi",
        "flow_direction",
        "flow_accumulation",
        "watershed",
    ] = Field(..., description="DEM-derived product to generate.")
    new_name: str = Field(..., description="Name for the generated DEM analysis raster.")
    band_index: int = Field(default=1, ge=1, description="One-based elevation band index.")
    z_factor: float = Field(default=1.0, gt=0, description="Vertical scale factor applied before terrain derivatives.")
    slope_unit: Literal["degrees", "percent", "radians"] = Field(
        default="degrees",
        description="Output unit for slope products.",
    )
    hillshade_azimuth: float = Field(default=315.0, ge=0, le=360, description="Hillshade light azimuth in degrees.")
    hillshade_altitude: float = Field(default=45.0, gt=0, le=90, description="Hillshade light altitude in degrees.")
    relief_window_size: int = Field(default=3, ge=3, description="Neighborhood size for topographic relief.")
    min_slope_degrees: float = Field(default=0.1, gt=0, description="Minimum slope used to stabilize TWI.")


class RasterTransformAnalysisArgs(BaseModel):
    raster_id: int = Field(..., description="Source raster index_id.")
    transform_type: Literal["fourier", "wavelet", "pca"] = Field(..., description="Transform analysis to run.")
    new_name: str = Field(..., description="Name for the generated transform raster.")
    band_index: int = Field(default=1, ge=1, description="One-based band index for Fourier or wavelet analysis.")
    fourier_output: Literal["magnitude", "power", "phase"] = Field(
        default="magnitude",
        description="Fourier output product.",
    )
    wavelet_output: Literal["detail_energy", "approximation", "horizontal", "vertical", "diagonal"] = Field(
        default="detail_energy",
        description="Haar wavelet output product.",
    )
    wavelet_level: int = Field(default=1, ge=1, description="Wavelet decomposition level.")
    pca_components: int = Field(default=3, ge=1, description="Number of PCA components to write.")
    pca_standardize: bool = Field(default=False, description="Standardize bands before PCA.")


class TextureFeatureAnalysisArgs(BaseModel):
    raster_id: int = Field(..., description="Source raster index_id.")
    texture_type: Literal["glcm", "local_statistics", "gabor", "lbp"] = Field(
        ...,
        description="Texture feature extraction method.",
    )
    new_name: str = Field(..., description="Name for the generated texture raster.")
    band_index: int = Field(default=1, ge=1, description="One-based source band index.")
    gray_levels: int = Field(default=32, ge=2, le=256, description="Quantization levels for GLCM/local entropy.")
    window_size: int = Field(default=7, ge=3, description="Neighborhood size for GLCM and local statistics.")
    glcm_distance: int = Field(default=1, ge=1, description="Pixel offset distance for GLCM.")
    glcm_angle: float = Field(default=0.0, description="GLCM offset angle in degrees.")
    glcm_property: Literal[
        "contrast",
        "dissimilarity",
        "homogeneity",
        "asm",
        "energy",
        "entropy",
        "correlation",
    ] = Field(default="contrast", description="GLCM texture property.")
    local_stat: Literal["mean", "std", "variance", "range", "entropy"] = Field(
        default="mean",
        description="Local statistics window output.",
    )
    gabor_frequency: float = Field(default=0.2, gt=0, description="Gabor sinusoid frequency.")
    gabor_theta: float = Field(default=0.0, description="Gabor orientation in degrees.")
    gabor_sigma: float = Field(default=2.0, gt=0, description="Gabor Gaussian envelope sigma.")
    lbp_radius: float = Field(default=1.0, gt=0, description="LBP sampling radius.")
    lbp_points: int = Field(default=8, ge=1, le=24, description="LBP neighbor count.")


class TimeSeriesAnalysisArgs(BaseModel):
    raster_ids: list[int] = Field(
        ...,
        min_length=1,
        description="Ordered raster index_id list representing the time series.",
    )
    operation: Literal[
        "monthly_composite",
        "annual_composite",
        "maximum_composite",
        "median_composite",
        "moving_window_smoothing",
        "savitzky_golay",
        "trend",
        "seasonality",
        "phenology",
    ] = Field(..., description="Time-series analysis operation.")
    new_name: str = Field(..., description="Name for the generated time-series analysis raster.")
    band_index: int = Field(default=1, ge=1, description="One-based source band index used from each raster.")
    dates: list[str] | str | None = Field(
        default=None,
        description=(
            "Optional acquisition dates in raster_ids order. Use YYYY-MM-DD, YYYY-MM, or YYYY. "
            "When omitted, raster created_at dates are used."
        ),
    )
    moving_window_size: int = Field(default=3, ge=1, description="Temporal window for moving-window smoothing.")
    savgol_window_length: int = Field(default=5, ge=3, description="Odd temporal window for Savitzky-Golay filtering.")
    savgol_polyorder: int = Field(default=2, ge=0, description="Polynomial order for Savitzky-Golay filtering.")
    phenology_threshold_ratio: float = Field(
        default=0.2,
        ge=0,
        le=1,
        description="Fraction of seasonal amplitude used to define start/end of season.",
    )


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


class RasterListArgs(BaseModel):
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of newest raster records to return.",
    )


class RasterGetArgs(BaseModel):
    raster_id: int = Field(..., description="Raster index_id to retrieve.")


class RasterStatisticsArgs(RasterGetArgs):
    bins: int = Field(default=32, ge=4, le=128, description="Histogram bin count.")
    max_size: int = Field(
        default=768,
        ge=128,
        le=2048,
        description="Maximum sampled width or height used to compute statistics.",
    )
    band_indices: list[int] | None = Field(
        default=None,
        description="Optional one-based bands to inspect. Defaults to every band.",
    )


class RasterSpectrumArgs(RasterGetArgs):
    lng: float = Field(..., ge=-180, le=180, description="WGS84 longitude.")
    lat: float = Field(..., ge=-90, le=90, description="WGS84 latitude.")


class RasterDeleteArgs(RasterGetArgs):
    pass


class RasterFieldListArgs(RasterGetArgs):
    pass


class RasterFieldCreateArgs(RasterGetArgs):
    field_name: str = Field(..., min_length=1, max_length=255, description="Field key.")
    field_alias: str | None = Field(default=None, max_length=255, description="Display label.")
    field_type: Literal["string", "number", "boolean", "date"] = Field(
        default="string",
        description="Stored field value type.",
    )
    field_order: int = Field(default=0, ge=0, description="Display order.")
    is_required: bool = Field(default=False, description="Whether the field is required by convention.")
    default_val: str | None = Field(default=None, description="Optional default value stored as text.")


class RasterFieldUpdateArgs(BaseModel):
    raster_id: int = Field(..., description="Raster index_id that owns the field.")
    field_id: int = Field(..., description="Raster field database id.")
    field_alias: str | None = Field(default=None, max_length=255, description="Updated display label.")
    field_type: Literal["string", "number", "boolean", "date"] | None = Field(
        default=None,
        description="Updated field value type.",
    )
    field_order: int | None = Field(default=None, ge=0, description="Updated display order.")
    is_required: bool | None = Field(default=None, description="Updated required flag.")
    default_val: str | None = Field(default=None, description="Updated default value stored as text.")


class RasterFieldDeleteArgs(BaseModel):
    raster_id: int = Field(..., description="Raster index_id that owns the field.")
    field_id: int = Field(..., description="Raster field database id to delete.")


class ProcessingTaskStatusArgs(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=255, description="Celery task id.")


class ProcessingJobStatusArgs(BaseModel):
    job_id: str = Field(..., min_length=1, max_length=255, description="Persistent processing job id.")


class ScriptTemplateListArgs(BaseModel):
    include_code: bool = Field(
        default=False,
        description="Include full template source code instead of names and descriptions only.",
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


class GeneratedDocumentArgs(BaseModel):
    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Export filename. Its extension is normalized to match format.",
    )
    format: Literal["txt", "md", "html", "json", "svg"] = Field(
        default="md",
        description=(
            "Generated file format. Use svg for AI-authored diagrams or simple vector images; "
            "active scripts and external SVG resources are rejected."
        ),
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=1_000_000,
        description="Complete UTF-8 file content to persist and make downloadable.",
    )


class GeneratedTableArgs(BaseModel):
    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Export filename. Its extension is normalized to match format.",
    )
    columns: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Ordered table column headings.",
    )
    rows: list[list[Any]] = Field(
        default_factory=list,
        max_length=10_000,
        description="Table rows in the same order and width as columns.",
    )
    format: Literal["csv", "xlsx", "json"] = Field(
        default="xlsx",
        description="Download format for the generated table.",
    )
    sheet_name: str = Field(
        default="AI Table",
        min_length=1,
        max_length=31,
        description="Worksheet name used for XLSX exports.",
    )


class GeneratedImageArgs(BaseModel):
    prompt: str = Field(
        ...,
        min_length=2,
        max_length=4000,
        description="Detailed prompt for the configured AI image-generation model.",
    )
    filename: str = Field(
        default="ai-generated-image.png",
        min_length=1,
        max_length=255,
        description="Filename offered when the user downloads the generated image.",
    )
    size: Literal["256x256", "512x512", "1024x1024", "1024x1536", "1536x1024"] = Field(
        default="1024x1024",
        description="Requested image dimensions; unsupported provider sizes may be rejected.",
    )
    quality: Literal["standard", "low", "medium", "high", "hd"] = Field(
        default="standard",
        description="Requested provider image quality.",
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


def _serialize_raster(raster: Any) -> dict[str, Any]:
    return _json_safe({
        "record_id": getattr(raster, "id", None),
        "index_id": getattr(raster, "index_id", None),
        "file_name": getattr(raster, "file_name", None),
        "bundle_id": getattr(raster, "bundle_id", None),
        "crs": getattr(raster, "crs", None),
        "bounds": getattr(raster, "bounds", None),
        "bounds_wgs84": getattr(raster, "bounds_wgs84", None),
        "center": getattr(raster, "center", None),
        "width": getattr(raster, "width", None),
        "height": getattr(raster, "height", None),
        "bands": getattr(raster, "bands", None),
        "data_type": getattr(raster, "data_type", None),
        "resolution_x": getattr(raster, "resolution_x", None),
        "resolution_y": getattr(raster, "resolution_y", None),
        "created_at": getattr(raster, "created_at", None),
    })


def _serialize_raster_field(field: Any) -> dict[str, Any]:
    return _json_safe({
        "id": getattr(field, "id", None),
        "raster_index_id": getattr(field, "raster_index_id", None),
        "field_name": getattr(field, "field_name", None),
        "field_alias": getattr(field, "field_alias", None),
        "field_type": getattr(field, "field_type", None),
        "field_order": getattr(field, "field_order", None),
        "is_required": getattr(field, "is_required", None),
        "is_system": getattr(field, "is_system", None),
        "default_val": getattr(field, "default_val", None),
        "created_at": getattr(field, "created_at", None),
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


def _get_raster_crud_class():
    from services.data_service.crud.raster_crud import RasterCRUD

    return RasterCRUD


def _get_raster_field_crud_class():
    from services.data_service.crud.raster_field_crud import RasterFieldCRUD

    return RasterFieldCRUD


def _get_compute_raster_statistics():
    from services.data_service.raster_statistics import compute_raster_statistics

    return compute_raster_statistics


def _get_cluster_task_status(task_id: str) -> dict[str, Any] | None:
    from services.data_service.bridges.worker_bridge import get_cluster_task_status

    return get_cluster_task_status(task_id)


def _get_script_templates_func():
    from services.data_service.routers.script_router import get_script_templates

    return get_script_templates


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


async def _run_dem_analysis(
    args: DEMAnalysisArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    return await db_ops.process_dem_analysis_task(
        db=db,
        raster_id=args.raster_id,
        operation=args.operation,
        new_name=args.new_name,
        band_index=args.band_index,
        z_factor=args.z_factor,
        slope_unit=args.slope_unit,
        hillshade_azimuth=args.hillshade_azimuth,
        hillshade_altitude=args.hillshade_altitude,
        relief_window_size=args.relief_window_size,
        min_slope_degrees=args.min_slope_degrees,
    )


async def _run_raster_transform_analysis(
    args: RasterTransformAnalysisArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    return await db_ops.process_raster_transform_task(
        db=db,
        raster_id=args.raster_id,
        transform_type=args.transform_type,
        new_name=args.new_name,
        band_index=args.band_index,
        fourier_output=args.fourier_output,
        wavelet_output=args.wavelet_output,
        wavelet_level=args.wavelet_level,
        pca_components=args.pca_components,
        pca_standardize=args.pca_standardize,
    )


async def _run_texture_feature_analysis(
    args: TextureFeatureAnalysisArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    return await db_ops.process_texture_feature_task(
        db=db,
        raster_id=args.raster_id,
        texture_type=args.texture_type,
        new_name=args.new_name,
        band_index=args.band_index,
        gray_levels=args.gray_levels,
        window_size=args.window_size,
        glcm_distance=args.glcm_distance,
        glcm_angle=args.glcm_angle,
        glcm_property=args.glcm_property,
        local_stat=args.local_stat,
        gabor_frequency=args.gabor_frequency,
        gabor_theta=args.gabor_theta,
        gabor_sigma=args.gabor_sigma,
        lbp_radius=args.lbp_radius,
        lbp_points=args.lbp_points,
    )


async def _run_time_series_analysis(
    args: TimeSeriesAnalysisArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    db_ops = _get_data_service_ops()
    if isinstance(args.dates, list):
        dates = ",".join(args.dates)
    else:
        dates = args.dates
    return await db_ops.process_time_series_task(
        db=db,
        raster_ids=args.raster_ids,
        operation=args.operation,
        new_name=args.new_name,
        band_index=args.band_index,
        dates=dates,
        moving_window_size=args.moving_window_size,
        savgol_window_length=args.savgol_window_length,
        savgol_polyorder=args.savgol_polyorder,
        phenology_threshold_ratio=args.phenology_threshold_ratio,
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


async def _require_raster(db: AsyncSession, raster_id: int) -> Any:
    raster = await _get_raster_crud_class().get_raster_by_index_id(db, raster_id)
    if not raster:
        raise ValueError(f"Raster not found: {raster_id}")
    return raster


def _raster_source_path(raster: Any) -> str:
    path = _get_data_service_ops().resolve_raster_record_path(raster)
    if not path:
        raise ValueError(f"Raster file not found for index_id={raster.index_id}")
    return path


async def _list_rasters(
    args: RasterListArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    rasters = await _get_raster_crud_class().get_all_rasters(db)
    selected = rasters[: args.limit]
    return {
        "status": "success",
        "rasters": [_serialize_raster(raster) for raster in selected],
        "count": len(selected),
        "total": len(rasters),
        "truncated": len(rasters) > len(selected),
    }


async def _get_raster_metadata(
    args: RasterGetArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    raster = await _require_raster(db, args.raster_id)
    return {"status": "success", "raster": _serialize_raster(raster)}


async def _get_raster_statistics(
    args: RasterStatisticsArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    raster = await _require_raster(db, args.raster_id)
    stats = _get_compute_raster_statistics()(
        _raster_source_path(raster),
        bins=args.bins,
        max_size=args.max_size,
        band_indices=args.band_indices,
    )
    return {
        "status": "success",
        "raster": _serialize_raster(raster),
        "statistics": _json_safe(stats),
    }


async def _query_raster_spectrum(
    args: RasterSpectrumArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    raster = await _require_raster(db, args.raster_id)
    spectrum = _get_raster_processor().query_spectrum(
        _raster_source_path(raster),
        args.lng,
        args.lat,
    )
    return {
        "status": "success",
        "raster": _serialize_raster(raster),
        "spectrum": _json_safe(spectrum),
    }


async def _delete_raster(
    args: RasterDeleteArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    raster = await _require_raster(db, args.raster_id)
    deleted = await _get_raster_crud_class().delete_raster(db, raster.id)
    if not deleted:
        raise ValueError(f"Raster not found: {args.raster_id}")
    return {"status": "success", "deleted": True, "raster_id": args.raster_id}


async def _list_raster_fields(
    args: RasterFieldListArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    await _require_raster(db, args.raster_id)
    fields = await _get_raster_field_crud_class()(db).get_by_raster(args.raster_id)
    return {
        "status": "success",
        "raster_id": args.raster_id,
        "fields": [_serialize_raster_field(field) for field in fields],
        "count": len(fields),
    }


async def _create_raster_field(
    args: RasterFieldCreateArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    await _require_raster(db, args.raster_id)
    from services.data_service.raster_field import RasterFieldCreate

    payload = RasterFieldCreate(**args.model_dump(exclude={"raster_id"}))
    field = await _get_raster_field_crud_class()(db).create(args.raster_id, payload)
    return {"status": "success", "field": _serialize_raster_field(field)}


async def _update_raster_field(
    args: RasterFieldUpdateArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    from services.data_service.raster_field import RasterFieldUpdate

    crud = _get_raster_field_crud_class()(db)
    current = await crud.get_by_id(args.field_id)
    if not current or current.raster_index_id != args.raster_id:
        raise ValueError(f"Raster field not found in raster {args.raster_id}: {args.field_id}")
    updates = args.model_dump(exclude={"raster_id", "field_id"}, exclude_unset=True)
    if not updates:
        raise ValueError("At least one raster field value must be provided for update.")
    field = await crud.update(args.field_id, RasterFieldUpdate(**updates))
    return {"status": "success", "field": _serialize_raster_field(field)}


async def _delete_raster_field(
    args: RasterFieldDeleteArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    crud = _get_raster_field_crud_class()(db)
    current = await crud.get_by_id(args.field_id)
    if not current or current.raster_index_id != args.raster_id:
        raise ValueError(f"Raster field not found in raster {args.raster_id}: {args.field_id}")
    deleted = await crud.delete(args.field_id)
    if not deleted:
        raise ValueError(f"Raster field not found: {args.field_id}")
    return {"status": "success", "deleted": True, "field_id": args.field_id}


async def _get_processing_task_status(
    args: ProcessingTaskStatusArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db, vector_db
    task = _get_cluster_task_status(args.task_id)
    if task is None:
        raise ValueError(f"Processing task not found: {args.task_id}")
    return {"status": "success", "task": _json_safe(task)}


async def _get_processing_job_status(
    args: ProcessingJobStatusArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del vector_db
    from sqlalchemy import text

    result = await db.execute(
        text(
            """
            SELECT job_id, celery_task_id, task_type, status, raster_index_id,
                   params, result, error, retry_count, created_at, started_at, finished_at
            FROM task_jobs
            WHERE job_id = :job_id
            """
        ),
        {"job_id": args.job_id},
    )
    row = result.mappings().first()
    if row is None:
        raise ValueError(f"Processing job not found: {args.job_id}")
    job = _json_safe(dict(row))
    if job.get("celery_task_id"):
        job["task_status"] = _json_safe(_get_cluster_task_status(job["celery_task_id"]))
    return {"status": "success", "job": job}


async def _list_script_templates(
    args: ScriptTemplateListArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db, vector_db
    templates = await _get_script_templates_func()()
    if not args.include_code:
        templates = [
            {"name": item.get("name"), "description": item.get("description")}
            for item in templates
        ]
    return {"status": "success", "templates": templates, "count": len(templates)}


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


async def _create_generated_document(
    args: GeneratedDocumentArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db, vector_db
    from services.ai_gateway.artifacts import create_document_artifact

    return create_document_artifact(args.filename, args.content, args.format)


async def _create_generated_table(
    args: GeneratedTableArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db, vector_db
    from services.ai_gateway.artifacts import create_table_artifact

    return create_table_artifact(
        args.filename,
        args.columns,
        args.rows,
        args.format,
        args.sheet_name,
    )


async def _generate_ai_image(
    args: GeneratedImageArgs,
    db: AsyncSession,
    vector_db: AsyncSession,
) -> dict[str, Any]:
    del db, vector_db
    from services.ai_gateway.image_generation import generate_ai_image

    return await generate_ai_image(
        prompt=args.prompt,
        filename=args.filename,
        size=args.size,
        quality=args.quality,
    )


REGISTERED_FUNCTIONS: dict[str, RegisteredFunction] = {
    spec.name: spec
    for spec in [
        RegisteredFunction(
            name="create_generated_document",
            description=(
                "Create a persistent downloadable AI-authored text, Markdown, HTML, JSON, or safe SVG file. "
                "Use safe SVG for diagrams or simple vector images that do not need a generative image model."
            ),
            category="artifact_generation",
            arguments_model=GeneratedDocumentArgs,
            handler=_create_generated_document,
        ),
        RegisteredFunction(
            name="create_generated_table",
            description=(
                "Create a persistent downloadable table as CSV, formatted XLSX, or JSON. "
                "Use whenever the user asks to generate, save, download, or export tabular results."
            ),
            category="artifact_generation",
            arguments_model=GeneratedTableArgs,
            handler=_create_generated_table,
        ),
        RegisteredFunction(
            name="generate_ai_image",
            description=(
                "Generate a raster image with the configured AI image model and return preview/download links. "
                "AI_IMAGE_MODEL must be configured; use create_generated_document with SVG for simple diagrams."
            ),
            category="artifact_generation",
            arguments_model=GeneratedImageArgs,
            handler=_generate_ai_image,
        ),
        RegisteredFunction(
            name="list_rasters",
            description="List the newest raster records and their public spatial metadata so the agent can discover index_id values.",
            category="raster_catalog",
            arguments_model=RasterListArgs,
            handler=_list_rasters,
        ),
        RegisteredFunction(
            name="get_raster_metadata",
            description="Retrieve public metadata for one raster by index_id without exposing internal filesystem paths.",
            category="raster_catalog",
            arguments_model=RasterGetArgs,
            handler=_get_raster_metadata,
        ),
        RegisteredFunction(
            name="get_raster_statistics",
            description="Compute sampled per-band statistics and histograms for a raster.",
            category="raster_catalog",
            arguments_model=RasterStatisticsArgs,
            handler=_get_raster_statistics,
        ),
        RegisteredFunction(
            name="query_raster_spectrum",
            description="Query all raster-band values at one WGS84 longitude/latitude coordinate.",
            category="raster_catalog",
            arguments_model=RasterSpectrumArgs,
            handler=_query_raster_spectrum,
        ),
        RegisteredFunction(
            name="delete_raster",
            description="Permanently delete one raster record and its files only when the user explicitly requests deletion.",
            category="raster_catalog",
            arguments_model=RasterDeleteArgs,
            handler=_delete_raster,
        ),
        RegisteredFunction(
            name="list_raster_fields",
            description="List system and custom attribute-field definitions for a raster.",
            category="raster_fields",
            arguments_model=RasterFieldListArgs,
            handler=_list_raster_fields,
        ),
        RegisteredFunction(
            name="create_raster_field",
            description="Create a custom attribute-field definition for a raster.",
            category="raster_fields",
            arguments_model=RasterFieldCreateArgs,
            handler=_create_raster_field,
        ),
        RegisteredFunction(
            name="update_raster_field",
            description="Update a raster field label, type, order, required flag, or default value.",
            category="raster_fields",
            arguments_model=RasterFieldUpdateArgs,
            handler=_update_raster_field,
        ),
        RegisteredFunction(
            name="delete_raster_field",
            description="Delete a non-system raster field only when the user explicitly requests deletion.",
            category="raster_fields",
            arguments_model=RasterFieldDeleteArgs,
            handler=_delete_raster_field,
        ),
        RegisteredFunction(
            name="get_processing_task_status",
            description="Get live status and progress for a Celery processing task id returned by an analysis tool.",
            category="task_monitoring",
            arguments_model=ProcessingTaskStatusArgs,
            handler=_get_processing_task_status,
        ),
        RegisteredFunction(
            name="get_processing_job_status",
            description="Get persistent processing-job status, result, errors, timestamps, and linked task status.",
            category="task_monitoring",
            arguments_model=ProcessingJobStatusArgs,
            handler=_get_processing_job_status,
        ),
        RegisteredFunction(
            name="list_script_templates",
            description="List supported raster-processing sandbox templates, optionally including their complete source code.",
            category="script_sandbox",
            arguments_model=ScriptTemplateListArgs,
            handler=_list_script_templates,
        ),
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
            name="dem_analysis",
            description=(
                "Generate DEM-derived rasters such as elevation, slope, aspect, hillshade, curvature, "
                "topographic relief, TWI, D8 flow direction, flow accumulation, or watershed labels."
            ),
            category="dem_analysis",
            arguments_model=DEMAnalysisArgs,
            handler=_run_dem_analysis,
        ),
        RegisteredFunction(
            name="raster_transform_analysis",
            description=(
                "Generate raster transform products using Fourier analysis, Haar wavelet analysis, or PCA. "
                "Use this for frequency-domain, multi-scale, or principal-component raster products."
            ),
            category="raster_transform_analysis",
            arguments_model=RasterTransformAnalysisArgs,
            handler=_run_raster_transform_analysis,
        ),
        RegisteredFunction(
            name="texture_feature_analysis",
            description=(
                "Generate texture feature rasters using GLCM, local statistics windows, Gabor filtering, "
                "or local binary patterns."
            ),
            category="texture_feature_analysis",
            arguments_model=TextureFeatureAnalysisArgs,
            handler=_run_texture_feature_analysis,
        ),
        RegisteredFunction(
            name="time_series_analysis",
            description=(
                "Generate time-series raster products: monthly or annual composites, maximum/median composites, "
                "moving-window smoothing, Savitzky-Golay filtering, trend, seasonality, or phenology parameters."
            ),
            category="time_series_analysis",
            arguments_model=TimeSeriesAnalysisArgs,
            handler=_run_time_series_analysis,
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
