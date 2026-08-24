"""Generic extraction and deterministic validation of numeric user constraints."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from deepscout_core.domain.contracts import NumericConstraint

_CONSTRAINT_PATTERN = re.compile(
    r"(?P<metric>budget(?:\s+(?:totale|total))?|total\s+budget|"
    r"(?:totale|total|sum|somma)(?:\s+(?:budget|cost|costo|allocation|allocazione))?)"
    r"[^\d]{0,72}(?P<value>\d{1,9}(?:[.,]\d{1,4})?)"
    r"\s*(?P<unit>crediti|credits?|usd|eur|euro|€|\$)?",
    re.I,
)


def _decimal(value: str) -> Decimal:
    normalized = value.replace(" ", "")
    if "," in normalized and "." not in normalized:
        normalized = normalized.replace(",", ".")
    else:
        normalized = normalized.replace(",", "")
    return Decimal(normalized)


def extract_numeric_constraints(goal: str) -> tuple[list[NumericConstraint], list[str]]:
    """Extract explicit budget/total conditions and flag incompatible equalities."""
    constraints: list[NumericConstraint] = []
    seen: set[tuple[str, str, str]] = set()
    for index, match in enumerate(_CONSTRAINT_PATTERN.finditer(goal), start=1):
        raw_metric = match.group("metric").casefold()
        unit = (match.group("unit") or "").casefold()
        bridge = goal[match.end("metric") : match.start("value")]
        # A later audience or league size is not a budget merely because the
        # word "budget" occurred earlier in the same clause. Explicit currency
        # units remain authoritative, while unitless matches must not cross a
        # participant/team-size phrase.
        if not unit and re.search(
            r"\b(?:league|leagues|lega|leghe|participants?|partecipanti|teams?|squadre)\b",
            bridge,
            re.I,
        ):
            continue
        metric = (
            "budget_total"
            if "budget" in raw_metric
            or unit in {"credit", "credits", "crediti", "usd", "eur", "euro", "€", "$"}
            else "total"
        )
        value = str(_decimal(match.group("value")))
        key = (metric, value, unit)
        if key in seen:
            continue
        seen.add(key)
        start = max(0, match.start() - 60)
        end = min(len(goal), match.end() + 60)
        constraints.append(
            NumericConstraint(
                constraint_id=f"N{index}",
                metric=metric,
                value=value,
                unit=unit,
                source_text=re.sub(r"\s+", " ", goal[start:end]).strip(),
            )
        )
    conflicts: list[str] = []
    by_metric: dict[tuple[str, str], set[str]] = {}
    for item in constraints:
        by_metric.setdefault((item.metric, item.unit), set()).add(item.value)
    for (metric, unit), values in by_metric.items():
        if len(values) > 1:
            suffix = f" {unit}" if unit else ""
            conflicts.append(f"{metric}: {', '.join(sorted(values))}{suffix}")
    return constraints, conflicts


def markdown_allocation_errors(body: str) -> list[str]:
    """Check arithmetic in allocation tables that contain an explicit total row."""
    errors: list[str] = []
    lines = body.splitlines()
    index = 0
    while index < len(lines):
        if "|" not in lines[index] or not re.search(
            r"budget|credit|cost|costo|allocation|allocazione", lines[index], re.I
        ):
            index += 1
            continue
        table: list[str] = []
        while index < len(lines) and "|" in lines[index]:
            table.append(lines[index])
            index += 1
        if len(table) < 4:
            continue
        values: list[Decimal] = []
        stated_total: Decimal | None = None
        for row in table[2:]:
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            match = re.search(r"-?\d+(?:[.,]\d+)?", cells[-1])
            if not match:
                continue
            try:
                value = _decimal(match.group(0))
            except InvalidOperation:
                continue
            if re.search(r"\b(?:total|totale|sum|somma)\b", " ".join(cells[:-1]), re.I):
                stated_total = value
            else:
                values.append(value)
        if stated_total is not None and values and sum(values, Decimal(0)) != stated_total:
            errors.append(f"allocation_sum_mismatch:{sum(values, Decimal(0))}!={stated_total}")
    return errors
