from services.executor_service.security import validate_script_content


def test_validator_allows_rasterio_open_calls():
    script = """
import rasterio

with rasterio.open(input_0) as src:
    data = src.read(1)

with rasterio.open(OUTPUT_FILE, "w", **src.profile) as dst:
    dst.write(data, 1)
"""

    assert validate_script_content(script) == (True, None)


def test_validator_blocks_bare_open_calls():
    script = 'with open("/tmp/unsafe.txt", "w") as f:\n    f.write("x")\n'

    assert validate_script_content(script) == (False, "open()")


def test_validator_ignores_blocked_words_in_comments_strings_and_names():
    script = """
import numpy as np

# The old validator rejected harmless comments that mentioned subprocess/open.
subprocess_count = 0
message = "eval and open are just text here"
data = np.asarray([1, 2, 3])
print(message, subprocess_count, data.mean())
"""

    assert validate_script_content(script) == (True, None)


def test_validator_allows_structured_scientific_code():
    script = """
from dataclasses import dataclass
from skimage.filters import threshold_otsu
import numpy as np

@dataclass
class ThresholdResult:
    value: float

arr = np.asarray([0.0, 0.5, 1.0], dtype=np.float32)
result = ThresholdResult(float(threshold_otsu(arr)))
print(result.value)
"""

    assert validate_script_content(script) == (True, None)


def test_validator_allows_sandbox_file_helper():
    script = """
with sandbox_open(output_path("summary.json"), "w", encoding="utf-8") as handle:
    handle.write("{}")
"""

    assert validate_script_content(script) == (True, None)


def test_validator_blocks_dangerous_imports_and_calls():
    assert validate_script_content("import subprocess\n")[0] is False
    assert validate_script_content("import os\nos.system('echo unsafe')\n") == (False, "os.system()")
    assert validate_script_content("import os as operating\noperating.system('echo unsafe')\n") == (False, "os.system()")
    assert validate_script_content("from os import system\n") == (False, "os.system()")
    assert validate_script_content("eval('1 + 1')\n") == (False, "eval()")
