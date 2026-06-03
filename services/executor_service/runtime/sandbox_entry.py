import os
import sys
import traceback
import warnings

import numpy as np
import rasterio
from scipy import ndimage

warnings.filterwarnings("ignore")

_REAL_IMPORT = __import__
_ALLOWED_MODULE_ROOTS = {
    "collections",
    "datetime",
    "functools",
    "itertools",
    "json",
    "math",
    "numpy",
    "os",
    "pathlib",
    "rasterio",
    "scipy",
    "skimage",
    "statistics",
    "sys",
    "warnings",
}


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level != 0:
        raise ImportError("Relative imports are not allowed in the sandbox")

    root_name = name.split(".", 1)[0]
    if root_name not in _ALLOWED_MODULE_ROOTS:
        raise ImportError(f"Import of '{name}' is not allowed in the sandbox")

    return _REAL_IMPORT(name, globals, locals, fromlist, level)


SAFE_BUILTINS = {
    "__import__": safe_import,
    "print": print,
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "reversed": reversed,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "bytes": bytes,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "pow": pow,
    "divmod": divmod,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "type": type,
    "hasattr": hasattr,
    "getattr": getattr,
    "setattr": setattr,
    "callable": callable,
    "iter": iter,
    "next": next,
    "any": any,
    "all": all,
    "repr": repr,
    "format": format,
    "vars": vars,
    "dir": dir,
    "id": id,
    "hash": hash,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "RuntimeError": RuntimeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
    "ImportError": ImportError,
    "OSError": OSError,
    "IOError": IOError,
    "StopIteration": StopIteration,
    "NotImplementedError": NotImplementedError,
    "ArithmeticError": ArithmeticError,
    "ZeroDivisionError": ZeroDivisionError,
    "OverflowError": OverflowError,
    "MemoryError": MemoryError,
    "Warning": Warning,
    "UserWarning": UserWarning,
    "True": True,
    "False": False,
    "None": None,
    "object": object,
    "property": property,
    "staticmethod": staticmethod,
    "classmethod": classmethod,
}


def save_raster_helper(data, path, profile):
    with rasterio.open(path, "w", **profile) as dst:
        if data.ndim == 2:
            dst.write(data, 1)
            return

        for i in range(data.shape[0]):
            dst.write(data[i], i + 1)


def main():
    input_dir = "/data/inputs"
    output_dir = "/data/outputs"
    script_path = "/data/scripts/user_code.py"
    output_filename = os.environ.get("OUTPUT_FILENAME", "result.tif")

    try:
        input_files = []
        if os.path.exists(input_dir):
            for file_name in sorted(os.listdir(input_dir)):
                if file_name.lower().endswith((".tif", ".tiff", ".img", ".hdf")):
                    input_files.append(os.path.join(input_dir, file_name))

        print(f"Found {len(input_files)} input file(s)")
        for idx, file_path in enumerate(input_files):
            print(f"  input_{idx} -> {os.path.basename(file_path)}")
    except Exception as e:
        print(f"ERROR: failed to read input directory: {e}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(script_path):
        print(f"ERROR: user script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        user_code = f.read()

    input_mapping = {}
    for idx, file_path in enumerate(input_files):
        basename = os.path.basename(file_path)
        input_mapping[basename] = file_path
        input_mapping[f"input{idx}"] = file_path
        input_mapping[idx] = file_path

    output_file = os.path.join(output_dir, output_filename)

    exec_globals = {
        "__builtins__": SAFE_BUILTINS,
        "np": np,
        "numpy": np,
        "rasterio": rasterio,
        "ndimage": ndimage,
        "INPUT_DIR": input_dir,
        "OUTPUT_DIR": output_dir,
        "INPUT_FILES": input_files,
        "OUTPUT_FILE": output_file,
        "inputs": input_mapping,
        "os": os,
        "sys": sys,
        "math": _REAL_IMPORT("math"),
        "warnings": warnings,
        "print": print,
        "read_raster": rasterio.open,
        "save_raster": save_raster_helper,
    }

    for idx, file_path in enumerate(input_files):
        exec_globals[f"input_{idx}"] = file_path

    if len(input_files) == 1:
        exec_globals["input_file"] = input_files[0]

    print("=" * 50)
    print("Starting sandboxed user script")
    print("=" * 50)

    try:
        exec(user_code, exec_globals)
        print("=" * 50)
        print("SUCCESS: script finished")

        if os.path.exists(output_file):
            print(f"Output file generated: {output_filename}")
            return

        generated_files = [
            file_name for file_name in os.listdir(output_dir)
            if file_name.lower().endswith((".tif", ".tiff"))
        ]
        if generated_files:
            print(f"Generated output file(s): {', '.join(generated_files)}")
        else:
            print(
                "WARNING: no output raster detected. "
                "Make sure the script writes a raster into OUTPUT_DIR or OUTPUT_FILE."
            )
    except Exception:
        exc_info = traceback.format_exc()
        print("=" * 50)
        print("ERROR: script execution failed", file=sys.stderr)
        print(exc_info, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
