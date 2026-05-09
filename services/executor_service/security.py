import re
from typing import Final


_DANGEROUS_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    (re.compile(r"__import__"), "__import__"),
    (re.compile(r"\bsubprocess\b"), "subprocess"),
    (re.compile(r"\bsocket\b"), "socket"),
    (re.compile(r"\bos\.system\s*\("), "os.system()"),
    (re.compile(r"\bos\.popen\s*\("), "os.popen()"),
    (re.compile(r"\bos\.execv(?:e)?\s*\("), "os.execv/execve()"),
    (re.compile(r"(?<![\w.])eval\s*\("), "eval()"),
    (re.compile(r"(?<![\w.])exec\s*\("), "exec()"),
    (re.compile(r"(?<![\w.])compile\s*\("), "compile()"),
    (re.compile(r"(?<![\w.])open\s*\("), "open()"),
    (re.compile(r"(?<![\w.])file\s*\("), "file()"),
    (re.compile(r"(?<![\w.])input\s*\("), "input()"),
    (re.compile(r"(?<![\w.])raw_input\s*\("), "raw_input()"),
    (re.compile(r"(?<![\w.])globals\s*\("), "globals()"),
    (re.compile(r"(?<![\w.])locals\s*\("), "locals()"),
    (re.compile(r"__builtins__"), "__builtins__"),
]


def validate_script_content(script: str) -> tuple[bool, str | None]:
    """
    Validate user-submitted Python code while avoiding false positives on
    safe calls like rasterio.open() or names like execute_script.
    """
    for pattern, label in _DANGEROUS_PATTERNS:
        if pattern.search(script):
            return False, label
    return True, None
