import ast
from typing import Final


_ALLOWED_IMPORT_ROOTS: Final[set[str]] = {
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
    "rasterio",
    "re",
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

_BLOCKED_IMPORT_ROOTS: Final[set[str]] = {
    "asyncio",
    "builtins",
    "ctypes",
    "ftplib",
    "http",
    "importlib",
    "io",
    "multiprocessing",
    "pickle",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "telnetlib",
    "threading",
    "urllib",
    "webbrowser",
}

_BLOCKED_DIRECT_CALLS: Final[dict[str, str]] = {
    "__import__": "__import__",
    "compile": "compile()",
    "eval": "eval()",
    "exec": "exec()",
    "file": "file()",
    "globals": "globals()",
    "input": "input()",
    "locals": "locals()",
    "open": "open()",
    "raw_input": "raw_input()",
}

_BLOCKED_OS_CALL_PREFIXES: Final[tuple[str, ...]] = (
    "exec",
    "fdopen",
    "fork",
    "kill",
    "open",
    "popen",
    "spawn",
    "system",
)

_BLOCKED_DUNDER_NAMES: Final[set[str]] = {
    "__builtins__",
    "__class__",
    "__closure__",
    "__code__",
    "__dict__",
    "__globals__",
    "__mro__",
    "__subclasses__",
}


def _root_name(module_name: str | None) -> str:
    return (module_name or "").split(".", 1)[0]


def _os_call_label(attr: str) -> str | None:
    if not attr.startswith(_BLOCKED_OS_CALL_PREFIXES):
        return None
    if attr in {"execv", "execve"}:
        return "os.execv/execve()"
    return f"os.{attr}()"


def _call_label(node: ast.Call, os_aliases: set[str]) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return _BLOCKED_DIRECT_CALLS.get(func.id)

    if isinstance(func, ast.Attribute):
        attr = func.attr
        if isinstance(func.value, ast.Name) and func.value.id in os_aliases:
            return _os_call_label(attr)

    return None


def _import_label(root_name: str) -> str | None:
    if root_name in _BLOCKED_IMPORT_ROOTS:
        return root_name
    if root_name not in _ALLOWED_IMPORT_ROOTS:
        return f"import {root_name}"
    return None


def validate_script_content(script: str) -> tuple[bool, str | None]:
    """
    Validate user-submitted Python code using syntax-aware checks.

    The executor still runs inside Docker with a restricted import hook and no
    network. This preflight validator exists to reject high-risk operations
    early without blocking harmless comments, string literals, helper names, or
    legitimate calls like rasterio.open().
    """
    try:
        tree = ast.parse(script, mode="exec")
    except SyntaxError as exc:
        return False, f"syntax error: {exc.msg}"

    os_aliases = {"os"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = _root_name(alias.name)
                label = _import_label(root_name)
                if label:
                    return False, label
                if root_name == "os":
                    os_aliases.add(alias.asname or root_name)

        if isinstance(node, ast.ImportFrom):
            if node.level:
                return False, "relative import"
            root_name = _root_name(node.module)
            label = _import_label(root_name)
            if label:
                return False, label
            if root_name == "os":
                for alias in node.names:
                    label = _os_call_label(alias.name)
                    if label:
                        return False, label

        if isinstance(node, ast.Call):
            label = _call_label(node, os_aliases)
            if label:
                return False, label

        if isinstance(node, ast.Name) and node.id in _BLOCKED_DUNDER_NAMES:
            return False, node.id

        if isinstance(node, ast.Attribute) and node.attr in _BLOCKED_DUNDER_NAMES:
            return False, node.attr

    return True, None
