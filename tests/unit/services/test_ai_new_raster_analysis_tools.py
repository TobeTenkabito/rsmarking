from services.ai_gateway.function_registry import list_registered_functions


def test_new_raster_analysis_tools_are_ai_callable():
    result = list_registered_functions("catalog")
    functions = {item["name"]: item for item in result["functions"]}

    expected = {
        "dem_analysis": "dem_analysis",
        "raster_transform_analysis": "raster_transform_analysis",
        "texture_feature_analysis": "texture_feature_analysis",
        "time_series_analysis": "time_series_analysis",
    }

    for name, category in expected.items():
        assert name in functions
        assert functions[name]["category"] == category

    dem_schema = functions["dem_analysis"]["parameters"]["properties"]
    assert "operation" in dem_schema
    assert "raster_id" in dem_schema

    texture_schema = functions["texture_feature_analysis"]["parameters"]["properties"]
    assert "texture_type" in texture_schema
    assert "glcm_property" in texture_schema

    time_series_schema = functions["time_series_analysis"]["parameters"]["properties"]
    assert "raster_ids" in time_series_schema
    assert "operation" in time_series_schema
