from services.ai_gateway.function_registry import list_registered_functions


def test_atmospheric_correction_is_ai_callable():
    result = list_registered_functions("catalog")
    tool_names = {item["name"] for item in result["functions"]}

    assert "atmospheric_correction" in tool_names
