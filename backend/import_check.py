"""
Fail-fast check for optional dependencies required by the backend.
Raises ImportError at import time if any required optional package is missing.
"""

_REQUIRED_OPTIONAL = (
    ("ollama", "ollama"),
    ("kreuzberg", "kreuzberg"),
)


def check_optional_imports() -> None:
    """
    Import each required optional dependency. If any fail, raise ImportError
    immediately with a clear message and install hint.
    """
    missing: list[str] = []
    for _module_name, _pip_name in _REQUIRED_OPTIONAL:
        try:
            __import__(_module_name)
        except ImportError:
            missing.append(_pip_name)
    if missing:
        pip_install = " ".join(missing)
        raise ImportError(
            f"Missing required optional dependencies: {', '.join(missing)}. "
            f"Install with: pip install {pip_install}"
        )
