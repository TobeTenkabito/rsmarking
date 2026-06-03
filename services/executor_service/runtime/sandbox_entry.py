import json
import os
import sys
import traceback
import warnings

import numpy as np
import rasterio
import scipy
from scipy import ndimage

warnings.filterwarnings("ignore")

_REAL_IMPORT = __import__
_REAL_OPEN = open
_REAL_BUILD_CLASS = __build_class__
INPUT_DIR = "/data/inputs"
OUTPUT_DIR = "/data/outputs"
SCRIPT_PATH = "/data/scripts/user_code.py"
_RASTER_INPUT_SUFFIXES = (
    ".tif",
    ".tiff",
    ".img",
    ".hdf",
    ".h5",
    ".vrt",
    ".jp2",
)
_ALLOWED_MODULE_ROOTS = {
    "__future__",
    "affine",
    "array",
    "bisect",
    "collections",
    "contextlib",
    "copy",
    "cv2",
    "dataclasses",
    "datetime",
    "decimal",
    "functools",
    "fractions",
    "heapq",
    "imageio",
    "itertools",
    "json",
    "math",
    "matplotlib",
    "numexpr",
    "numpy",
    "operator",
    "os",
    "pathlib",
    "PIL",
    "pyproj",
    "random",
    "re",
    "rasterio",
    "scipy",
    "shapely",
    "skimage",
    "sklearn",
    "statistics",
    "string",
    "sys",
    "tifffile",
    "typing",
    "warnings",
}


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level != 0:
        raise ImportError("Relative imports are not allowed in the sandbox")

    root_name = name.split(".", 1)[0]
    if root_name not in _ALLOWED_MODULE_ROOTS:
        raise ImportError(f"Import of '{name}' is not allowed in the sandbox")

    return _REAL_IMPORT(name, globals, locals, fromlist, level)


def optional_import(name):
    try:
        return _REAL_IMPORT(name)
    except Exception:
        return None


SAFE_BUILTINS = {
    "__import__": safe_import,
    "__build_class__": _REAL_BUILD_CLASS,
    "BaseException": BaseException,
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
    "frozenset": frozenset,
    "int": int,
    "float": float,
    "complex": complex,
    "str": str,
    "bool": bool,
    "bytes": bytes,
    "bytearray": bytearray,
    "memoryview": memoryview,
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
    "ascii": ascii,
    "format": format,
    "chr": chr,
    "ord": ord,
    "bin": bin,
    "hex": hex,
    "oct": oct,
    "vars": vars,
    "dir": dir,
    "id": id,
    "hash": hash,
    "slice": slice,
    "Exception": Exception,
    "AssertionError": AssertionError,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "RuntimeError": RuntimeError,
    "NameError": NameError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
    "ImportError": ImportError,
    "OSError": OSError,
    "IOError": IOError,
    "LookupError": LookupError,
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
    "super": super,
}


def _is_within(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _safe_container_path(path, *, for_write=False):
    raw_path = os.fspath(path)
    base_dir = OUTPUT_DIR if for_write else INPUT_DIR
    candidate = raw_path if os.path.isabs(raw_path) else os.path.join(base_dir, raw_path)
    resolved = os.path.realpath(os.path.abspath(candidate))

    allowed_roots = [OUTPUT_DIR] if for_write else [INPUT_DIR, OUTPUT_DIR]
    if any(_is_within(resolved, os.path.realpath(root)) for root in allowed_roots):
        return resolved

    allowed = " or ".join(allowed_roots)
    raise ValueError(f"Path is outside the sandbox data directories: {raw_path!r}; allowed: {allowed}")


def sandbox_open(path, mode="r", *args, **kwargs):
    if not isinstance(mode, str):
        raise TypeError("mode must be a string")

    for_write = any(flag in mode for flag in ("w", "a", "x", "+"))
    safe_path = _safe_container_path(path, for_write=for_write)
    if for_write:
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
    return _REAL_OPEN(safe_path, mode, *args, **kwargs)


def output_path(filename):
    return _safe_container_path(filename, for_write=True)


def save_raster_helper(data, path, profile):
    safe_path = _safe_container_path(path, for_write=True)
    with rasterio.open(safe_path, "w", **profile) as dst:
        if data.ndim == 2:
            dst.write(data, 1)
            return

        for i in range(data.shape[0]):
            dst.write(data[i], i + 1)


def main():
    input_dir = INPUT_DIR
    output_dir = OUTPUT_DIR
    script_path = SCRIPT_PATH
    output_filename = os.environ.get("OUTPUT_FILENAME", "result.tif")
    input_metadata_by_name = {}
    input_metadata_records = []

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
            input_metadata_records = [
                dict(item)
                for item in input_metadata
                if isinstance(item, dict)
            ]

        discovered_inputs = {}
        if os.path.exists(input_dir):
            for file_name in sorted(os.listdir(input_dir)):
                if file_name.lower().endswith(_RASTER_INPUT_SUFFIXES):
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

        input_metadata_records = []
        for idx, file_path in enumerate(input_files):
            basename = os.path.basename(file_path)
            metadata = dict(input_metadata_by_name.get(basename, {}))
            metadata.update({"index": idx, "name": basename, "path": file_path})
            input_metadata_records.append(metadata)

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
        input_mapping[f"input_{idx}"] = file_path
        input_mapping[idx] = file_path

    output_file = os.path.join(output_dir, output_filename)
    raster_files = {}
    raster_filenames = {}
    optional_modules = {
        "cv2": optional_import("cv2"),
        "numexpr": optional_import("numexpr"),
        "PIL": optional_import("PIL"),
        "pyproj": optional_import("pyproj"),
        "shapely": optional_import("shapely"),
        "skimage": optional_import("skimage"),
        "sklearn": optional_import("sklearn"),
    }

    def resolve_input_path(value=0):
        if value in input_mapping:
            return input_mapping[value]

        text_value = str(value)
        if text_value in input_mapping:
            return input_mapping[text_value]

        candidate = text_value if os.path.isabs(text_value) else os.path.join(input_dir, text_value)
        return _safe_container_path(candidate, for_write=False)

    def read_raster_helper(path_or_key=0, *args, **kwargs):
        return rasterio.open(resolve_input_path(path_or_key), *args, **kwargs)

    def read_array_helper(path_or_key=0, band=1, masked=False):
        with read_raster_helper(path_or_key) as src:
            return src.read(band, masked=masked)

    def write_raster_helper(data, profile, path=None, **profile_updates):
        output = path or output_file
        next_profile = dict(profile)
        next_profile.update(profile_updates)
        save_raster_helper(data, output, next_profile)
        return output

    exec_globals = {
        "__builtins__": SAFE_BUILTINS,
        "__name__": "__sandbox__",
        "np": np,
        "numpy": np,
        "scipy": scipy,
        "rasterio": rasterio,
        "ndimage": ndimage,
        "INPUT_DIR": input_dir,
        "OUTPUT_DIR": output_dir,
        "INPUT_FILES": input_files,
        "INPUT_METADATA": input_metadata_records,
        "OUTPUT_FILE": output_file,
        "inputs": input_mapping,
        "raster_files": raster_files,
        "raster_filenames": raster_filenames,
        "os": os,
        "sys": sys,
        "math": _REAL_IMPORT("math"),
        "warnings": warnings,
        "print": print,
        "sandbox_open": sandbox_open,
        "safe_open": sandbox_open,
        "output_path": output_path,
        "input_path": resolve_input_path,
        "list_inputs": lambda: list(input_metadata_records),
        "read_raster": read_raster_helper,
        "read_array": read_array_helper,
        "write_raster": write_raster_helper,
        "save_raster": save_raster_helper,
    }
    exec_globals.update({name: module for name, module in optional_modules.items() if module is not None})

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
            raster_files[str(raster_id)] = file_path
            raster_filenames[str(raster_id)] = basename

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
