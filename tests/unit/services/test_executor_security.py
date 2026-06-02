from services.executor_service.security import validate_script_content


def test_validator_allows_rasterio_open_calls():
    script = """
import rasterio

with rasterio.open(input_file) as src:
    data = src.read(1)

with rasterio.open(OUTPUT_FILE, "w", **src.profile) as dst:
    dst.write(data, 1)
"""

    assert validate_script_content(script) == (True, None)


def test_validator_blocks_bare_open_calls():
    script = 'with open("/tmp/unsafe.txt", "w") as f:\n    f.write("x")\n'

    assert validate_script_content(script) == (False, "open()")
