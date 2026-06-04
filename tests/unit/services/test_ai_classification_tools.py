from services.ai_gateway.function_registry import list_registered_functions


def test_classification_and_segmentation_are_ai_callable():
    result = list_registered_functions("catalog")
    functions = {item["name"]: item for item in result["functions"]}

    assert "supervised_classification" in functions
    assert "unsupervised_classification" in functions
    assert "deep_learning_segmentation" in functions
    assert functions["supervised_classification"]["category"] == "classification"
    assert functions["unsupervised_classification"]["category"] == "classification"
    assert functions["deep_learning_segmentation"]["category"] == "segmentation"
