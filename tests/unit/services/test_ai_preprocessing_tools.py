from services.ai_gateway.function_registry import list_registered_functions


def test_radiometric_and_geometric_tools_are_ai_callable():
    result = list_registered_functions("catalog")
    functions = {item["name"]: item for item in result["functions"]}

    assert "radiometric_calibration" in functions
    assert "geometric_correction" in functions
    assert functions["radiometric_calibration"]["category"] == "radiometric_calibration"
    assert functions["geometric_correction"]["category"] == "geometric_correction"
