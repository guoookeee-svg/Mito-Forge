import os
import re
from pathlib import Path
from typing import Optional

_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9._-]+$')


def validate_file_path(file_path: str, *, must_exist: bool = False, allowed_extensions: Optional[list] = None) -> Path:
    p = Path(file_path).resolve()
    if must_exist and not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if allowed_extensions and p.suffix.lower() not in allowed_extensions:
        raise ValueError(f"Invalid file extension '{p.suffix}'. Allowed: {allowed_extensions}")
    return p


def validate_within_dir(file_path: str, base_dir: str) -> Path:
    p = Path(file_path).resolve()
    base = Path(base_dir).resolve()
    try:
        p.relative_to(base)
    except ValueError:
        raise ValueError(f"Path '{file_path}' is outside allowed directory '{base_dir}'")
    return p


def validate_safe_name(name: str) -> str:
    if not _SAFE_NAME_RE.match(name):
        raise ValueError(f"Invalid name: {name!r} (only alphanumeric, dot, dash, underscore allowed)")
    return name


def sanitize_for_log(text: str, max_length: int = 200) -> str:
    sensitive_patterns = [
        r'(api[_-]?key\s*[:=]\s*)\S+',
        r'(authorization\s*[:=]\s*)\S+',
        r'(token\s*[:=]\s*)\S+',
        r'(bearer\s+)\S+',
        r'(sk-)[a-zA-Z0-9]{20,}',
        r'(x-api-key\s*[:=]\s*)\S+',
    ]
    result = text
    for pattern in sensitive_patterns:
        result = re.sub(pattern, r'\1[REDACTED]', result, flags=re.IGNORECASE)
    if len(result) > max_length:
        result = result[:max_length] + "..."
    return result
