"""CSV formula-injection guards for untrusted export fields."""

from __future__ import annotations

import csv
import io
import re

_FORMULA_PREFIX = re.compile(r"^[=+\-@].")


def sanitize_csv_field(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def render_csv(headers: list[str], rows: list[list[object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([sanitize_csv_field(item) for item in row])
    return buffer.getvalue()
