from __future__ import annotations

import re
from pathlib import PurePath

DEFAULT_OUTPUT_FILENAME = "merged_packet.pdf"
INVALID_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_pdf_filename(
    raw_name: str | None,
    default_name: str = DEFAULT_OUTPUT_FILENAME,
) -> str:
    candidate = (raw_name or "").strip()
    if not candidate:
        return default_name

    base_name = PurePath(candidate).name
    suffix = PurePath(base_name).suffix.lower()
    stem = PurePath(base_name).stem if suffix else base_name
    safe_stem = INVALID_FILENAME_CHARS.sub("_", stem).strip("._-")

    if not safe_stem:
        safe_stem = PurePath(default_name).stem

    return f"{safe_stem}.pdf"


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 0:
        raise ValueError("File size cannot be negative.")

    units = ("B", "KB", "MB", "GB")
    size = float(size_bytes)

    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024

    raise RuntimeError("Unreachable code reached while formatting file size.")
