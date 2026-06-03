import json
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
    input_metadata_by_name = {}

    try:
        try:
            raw_input_map = os.environ.get("SANDBOX_INPUT_MAP", "[]")
            input_metadata = json.loads(raw_input_map)
        except Exception as metadata_error:
            print(f"WARNING: failed to parse sandbox input map: {metadata_error}")
            input_metadata = []
        if isinstance(input_metadata, list):
            input_metadata_by_name = {
                str(item.get("name")): item
                for item in input_metadata
                if isinstance(item, dict) and item.get("name")
            }

        discovered_inputs = {}
        if os.path.exists(input_dir):
            for file_name in sorted(os.listdir(input_dir)):
                if file_name.lower().endswith((".tif", ".tiff", ".img", ".hdf")):
                    discovered_inputs[file_name] = os.path.join(input_dir, file_name)

        input_files = []
        if isinstance(input_metadata, list) and input_metadata:
            for item in input_metadata:
                if not isinstance(item, dict):
                    continue
                file_name = str(item.get("name") or "")
                file_path = discovered_inputs.pop(file_name, None)
                if file_path:
                    input_files.append(file_path)
        input_files.extend(discovered_inputs[name] for name in sorted(discovered_inputs))

        print(f"Found {len(input_files)} input file(s)")
        for idx, file_path in enumerate(input_files):
            basename = os.path.basename(file_path)
            metadata = input_metadata_by_name.get(basename, {})
            alias = metadata.get("alias")
            raster_id = metadata.get("raster_id")
            alias_note = f", alias={alias}, raster_id={raster_id}" if alias or raster_id is not None else ""
            print(f"  input_{idx} -> {basename}{alias_note}")
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
    raster_files = {}
    raster_filenames = {}

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
        "raster_files": raster_files,
        "raster_filenames": raster_filenames,
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
        basename = os.path.basename(file_path)
        metadata = input_metadata_by_name.get(basename, {})
        alias = str(metadata.get("alias") or "")
        if alias.isidentifier():
            exec_globals[alias] = file_path

        raster_id = metadata.get("raster_id")
        if raster_id is not None:
            try:
                raster_key = int(raster_id)
            except (TypeError, ValueError):
                raster_key = str(raster_id)
            raster_files[raster_key] = file_path
            raster_filenames[raster_key] = basename

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
