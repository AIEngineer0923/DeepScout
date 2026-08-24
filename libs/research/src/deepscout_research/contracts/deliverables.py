"""Generic deliverable inference, constrained selection, and report validation."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from deepscout_core.domain.contracts import (
    AnswerRequirement,
    CategoryQuota,
    DeliverableKind,
    DeliverableSpec,
    DeliverableValidationResult,
    EntityAttributeGoal,
    EntityResearchEntity,
    EntityResearchMatrix,
    MatrixFieldStatus,
    NumericConstraint,
    RequirementKind,
)

_SELECTION_HINTS = re.compile(
    r"\b(?:choose|select|shortlist|rank|allocate|portfolio|basket|roster|list|"
    r"costruisci|scegli|seleziona|proponi|classifica|alloca|rosa|elenco|lista|itinerar\w*)\b",
    re.I,
)
_IMPERATIVE_BUILD_HINT = re.compile(
    r"(?:^|[.!?]\s+)build\s+(?:a|an|the|me\s+an?)\b",
    re.I,
)
_ALLOCATION_HINTS = re.compile(
    r"\b(?:budget|allocation|allocazione|allocate|alloca|credits?|crediti|portfolio)\b",
    re.I,
)
_RANKING_HINTS = re.compile(r"\b(?:rank|ranking|classifica|miglior\w*|top)\b", re.I)
_QUOTA = re.compile(
    r"(?<![\d.,])(?P<count>\d{1,3})\s+"
    r"(?P<label>[^\d\n,;:.!?/]{2,45}?)(?=\s*(?:,|/|;|\be\b|\band\b|"
    r"\b(?:con|with)\s+budget\b|\n|$))",
    re.I,
)
_EXACT_COUNT = re.compile(
    r"\b(?:build|choose|select|shortlist|rank|propose|return|costruisci|scegli|"
    r"seleziona|proponi|restituisci)\s+(?:a\s+|an\s+|una?\s+)?"
    r"(?:of\s+|di\s+)?(?:exactly\s+|esattamente\s+)?"
    r"(?P<count>\d{1,3})\s+"
    r"(?P<label>[\wÀ-ÿ-]{2,30}(?:\s+[\wÀ-ÿ-]{2,30}){0,4}?)"
    r"(?=\s+(?:available|with|under|within|for|that|which|and|"
    r"disponibil\w*|con|entro|per|che|e)\b|[,.;:\n]|$)",
    re.I,
)
_NON_CATEGORY_LABELS = {
    "sources",
    "source",
    "fonti",
    "fonte",
    "credits",
    "crediti",
    "eur",
    "usd",
    "euro",
    "days",
    "giorni",
    "years",
    "anni",
    "participants",
    "partecipanti",
}


def _ascii(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _key(value: str) -> str:
    words = re.findall(r"[a-z0-9]+", _ascii(value).casefold())
    return "_".join(words[:8])[:120] or "item"


def _clean_label(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" -–—:.,;")
    value = re.sub(r"^(?:and|e|di|of)\s+", "", value, flags=re.I)
    return value


def category_keys_match(left: str, right: str) -> bool:
    """Tolerate simple singular/plural inflection without domain dictionaries."""
    a, b = _key(left), _key(right)
    if a == b or a in b or b in a:
        return True
    common = 0
    for char_a, char_b in zip(a, b, strict=False):
        if char_a != char_b:
            break
        common += 1
    return common >= max(4, min(len(a), len(b)) - 2)


def _quota_candidates(goal: str) -> list[CategoryQuota]:
    quotas: list[CategoryQuota] = []
    seen: set[str] = set()
    for match in _QUOTA.finditer(goal):
        count = int(match.group("count"))
        label = _clean_label(match.group("label"))
        label_key = _key(label)
        if not label or count > 100 or label_key in _NON_CATEGORY_LABELS:
            continue
        # Years, money and dates are not category quotas. A quota label should
        # be a short noun phrase rather than a full instruction clause.
        if len(label.split()) > 5 or re.search(
            r"\b(?:agosto|august|budget|totale|total)\b", label, re.I
        ):
            continue
        if label_key in seen:
            continue
        seen.add(label_key)
        quotas.append(
            CategoryQuota(
                category_key=label_key,
                label=label,
                exact_count=count,
                source_text=re.sub(r"\s+", " ", match.group(0)).strip(),
            )
        )
    return quotas if len(quotas) >= 2 else []


def _attribute_goals(requirements: list[AnswerRequirement]) -> list[EntityAttributeGoal]:
    goals: list[EntityAttributeGoal] = []
    seen: set[str] = set()
    ignored = {
        RequirementKind.OUTPUT_FORMAT,
        RequirementKind.SOURCE_POLICY,
        RequirementKind.SYNTHESIS,
    }
    for requirement in requirements:
        if requirement.kind in ignored or requirement.requirement_id == "R0":
            continue
        key = _key(requirement.text)
        if key in seen:
            continue
        seen.add(key)
        goals.append(
            EntityAttributeGoal(
                attribute_key=key,
                label=requirement.text[:500],
                requirement_ids=[requirement.requirement_id],
                critical=requirement.critical,
                materiality=requirement.materiality,
            )
        )
    return goals[:40]


def _list_after(pattern: str, goal: str) -> list[str]:
    match = re.search(pattern, goal, re.I)
    if not match:
        return []
    fragment = re.split(r"[.\n]", match.group(1), maxsplit=1)[0]
    return [
        item.strip(" \t-–—\"'")[:200]
        for item in re.split(r",|;|/|\band\b|\be\b", fragment, flags=re.I)
        if item.strip(" \t-–—\"'")
    ][:50]


def infer_deliverable_spec(
    *,
    goal: str,
    requirements: list[AnswerRequirement],
    numeric_constraints: list[NumericConstraint],
) -> DeliverableSpec:
    """Infer answer shape from syntax, without relying on domain vocabularies."""
    quotas = _quota_candidates(goal)
    exact_count: int | None = sum(item.exact_count or 0 for item in quotas) or None
    entity_type = "item"
    exact_match = _EXACT_COUNT.search(goal)
    if exact_match and int(exact_match.group("count")) <= 1000:
        exact_count = exact_count or int(exact_match.group("count"))
        entity_type = _clean_label(exact_match.group("label")).split(" ")[-1][:120] or "item"

    lowered = goal.casefold()
    selection_requested = bool(
        _SELECTION_HINTS.search(goal) or _IMPERATIVE_BUILD_HINT.search(goal)
    )
    kind = DeliverableKind.NARRATIVE
    if "itinerar" in lowered:
        kind = DeliverableKind.ITINERARY
    elif quotas and _ALLOCATION_HINTS.search(goal):
        kind = DeliverableKind.ALLOCATION
    elif selection_requested and _ALLOCATION_HINTS.search(goal):
        kind = DeliverableKind.PORTFOLIO
    elif selection_requested and _RANKING_HINTS.search(goal):
        kind = DeliverableKind.RANKING
    elif selection_requested:
        kind = DeliverableKind.ENTITY_SET
    elif any(req.kind == RequirementKind.COMPARISON for req in requirements):
        kind = DeliverableKind.COMPARISON

    budget_constraints = [item for item in numeric_constraints if item.metric == "budget_total"]
    budget = budget_constraints[-1] if budget_constraints else None
    alternatives = None
    alternative_match = re.search(
        r"(?:(\d+)\s+)?(?:alternativ\w*|backup\w*)\s+(?:per|for)\s+(?:ogni|each)",
        goal,
        re.I,
    )
    if alternative_match:
        alternatives = int(alternative_match.group(1) or 1)

    comparisons: list[str] = []
    for req in requirements:
        for subject in req.comparison_subjects:
            if subject and subject not in comparisons:
                comparisons.append(subject)

    return DeliverableSpec(
        kind=kind,
        entity_type=entity_type,
        exact_item_count=exact_count,
        category_quotas=quotas,
        budget_total=budget.value if budget else "",
        budget_unit=budget.unit if budget else "",
        must_include=_list_after(
            r"(?:must\s+include|includi\s+obbligatoriamente)\s*[:]?\s*([^\n]+)", goal
        ),
        must_exclude=_list_after(
            r"\b(?:must\s+exclude|exclude|escludi)\b\s*[:]?\s*([^\n]+)", goal
        ),
        alternatives_per_entity=alternatives,
        comparison_subjects=comparisons[:30],
        attribute_goals=_attribute_goals(requirements),
    )


def _field_decimal(entity: EntityResearchEntity, keys: tuple[str, ...]) -> Decimal | None:
    for field in entity.fields:
        if field.status not in {MatrixFieldStatus.KNOWN, MatrixFieldStatus.ESTIMATED}:
            continue
        if not any(token in field.attribute_key for token in keys):
            continue
        match = re.search(r"-?\d+(?:[.,]\d+)?", field.value)
        if match:
            try:
                return Decimal(match.group(0).replace(",", "."))
            except InvalidOperation:
                return None
    return None


def solve_constrained_selection(
    matrix: EntityResearchMatrix,
    spec: DeliverableSpec,
    *,
    scores: dict[str, float] | None = None,
) -> list[EntityResearchEntity]:
    """Deterministically select the highest-scored feasible entities.

    This deliberately small solver covers exact counts, category quotas,
    must-include/exclude and a total cost ceiling. It never invents entities or
    values; infeasible requests return the largest valid partial selection and
    are rejected by :func:`validate_selected_entities`.
    """
    scores = scores or {}
    excluded = {_ascii(item).casefold() for item in spec.must_exclude}
    include = {_ascii(item).casefold() for item in spec.must_include}
    candidates = [
        entity
        for entity in matrix.entities
        if _ascii(entity.entity_name).casefold() not in excluded
    ]
    candidates.sort(
        key=lambda entity: (
            _ascii(entity.entity_name).casefold() not in include,
            -scores.get(entity.entity_id, 0.0),
            -sum(field.confidence for field in entity.fields),
            entity.entity_name.casefold(),
        )
    )
    selected: list[EntityResearchEntity] = []
    by_category: dict[str, list[EntityResearchEntity]] = defaultdict(list)
    for entity in candidates:
        by_category[_key(entity.category)].append(entity)
    for quota in spec.category_quotas:
        target = quota.exact_count if quota.exact_count is not None else quota.minimum_count or 0
        selected.extend(by_category.get(quota.category_key, [])[:target])
    wanted = spec.exact_item_count or spec.minimum_item_count or 0
    for entity in candidates:
        if len(selected) >= wanted:
            break
        if entity not in selected:
            selected.append(entity)

    if spec.budget_total:
        try:
            ceiling = Decimal(spec.budget_total)
        except InvalidOperation:
            ceiling = None
        if ceiling is not None:
            total = sum(
                (_field_decimal(item, ("budget", "cost", "price", "prezzo", "costo")) or 0)
                for item in selected
            )
            while total > ceiling and selected:
                removable = [
                    item
                    for item in reversed(selected)
                    if _ascii(item.entity_name).casefold() not in include
                ]
                if not removable:
                    break
                removed = removable[0]
                selected.remove(removed)
                total -= (
                    _field_decimal(removed, ("budget", "cost", "price", "prezzo", "costo")) or 0
                )
    return selected


def validate_selected_entities(
    selected: list[EntityResearchEntity], spec: DeliverableSpec
) -> DeliverableValidationResult:
    counts: dict[str, int] = defaultdict(int)
    for entity in selected:
        counts[_key(entity.category)] += 1
    checks: dict[str, bool] = {}
    issues: list[str] = []
    if spec.exact_item_count is not None:
        checks["exact_item_count"] = len(selected) == spec.exact_item_count
        if not checks["exact_item_count"]:
            issues.append(f"item_count:{len(selected)}!={spec.exact_item_count}")
    for quota in spec.category_quotas:
        if quota.exact_count is None:
            continue
        valid = counts.get(quota.category_key, 0) == quota.exact_count
        checks[f"category:{quota.category_key}"] = valid
        if not valid:
            issues.append(
                f"category_count:{quota.category_key}:{counts.get(quota.category_key, 0)}"
                f"!={quota.exact_count}"
            )
    names = {_ascii(item.entity_name).casefold() for item in selected}
    if spec.must_include:
        checks["must_include"] = all(_ascii(item).casefold() in names for item in spec.must_include)
    if spec.must_exclude:
        checks["must_exclude"] = all(
            _ascii(item).casefold() not in names for item in spec.must_exclude
        )
    return DeliverableValidationResult(
        valid=all(checks.values()) if checks else True,
        checks=checks,
        observed={"item_count": len(selected), "category_counts": dict(counts)},
        issues=issues,
    )


def _markdown_tables(body: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = body.splitlines()
    tables: list[tuple[list[str], list[list[str]]]] = []
    index = 0
    while index + 1 < len(lines):
        if "|" not in lines[index] or not re.match(r"^\s*\|?\s*:?-+", lines[index + 1]):
            index += 1
            continue
        header = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        index += 2
        rows: list[list[str]] = []
        while index < len(lines) and "|" in lines[index]:
            rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
            index += 1
        tables.append((header, rows))
    return tables


def validate_report_deliverable(body: str, spec: DeliverableSpec) -> DeliverableValidationResult:
    """Validate the rendered answer rather than trusting prose about completeness."""
    if spec.kind == DeliverableKind.NARRATIVE:
        return DeliverableValidationResult(valid=True, checks={"narrative": True})
    tables = _markdown_tables(body)
    best: tuple[list[str], list[list[str]]] | None = None
    for header, rows in tables:
        normalized = [_key(cell) for cell in header]
        if any(
            token in normalized
            for token in (
                "entity",
                "item",
                "name",
                "nome",
                "player",
                "giocatore",
                "option",
                "opzione",
            )
        ):
            if best is None or len(rows) > len(best[1]):
                best = (header, rows)
    checks: dict[str, bool] = {}
    issues: list[str] = []
    observed: dict[str, str | int | float | list[str] | dict[str, int]] = {}
    if best is None:
        if spec.kind == DeliverableKind.COMPARISON:
            present = all(
                subject.casefold() in body.casefold() for subject in spec.comparison_subjects
            )
            return DeliverableValidationResult(
                valid=present,
                checks={"comparison_subjects": present},
                issues=[] if present else ["comparison_subject_missing"],
            )
        return DeliverableValidationResult(
            valid=False,
            checks={"deliverable_table": False},
            issues=["deliverable_table_missing"],
        )

    header, rows = best
    normalized = [_key(cell) for cell in header]
    entity_index = next(
        (
            index
            for index, token in enumerate(normalized)
            if token
            in {"entity", "item", "name", "nome", "player", "giocatore", "option", "opzione"}
        ),
        0,
    )
    category_index = next(
        (
            index
            for index, token in enumerate(normalized)
            if token in {"category", "categoria", "type", "tipo", "role", "ruolo"}
        ),
        None,
    )
    budget_index = next(
        (
            index
            for index, token in enumerate(normalized)
            if re.search(r"budget|cost|price|prezzo|costo|credit", token)
        ),
        None,
    )
    data_rows = [
        row for row in rows if not re.search(r"\b(?:total|totale|sum|somma)\b", " ".join(row), re.I)
    ]
    names = [
        row[entity_index] for row in data_rows if len(row) > entity_index and row[entity_index]
    ]
    observed["item_count"] = len(names)
    observed["entities"] = names[:100]
    if spec.exact_item_count is not None:
        checks["exact_item_count"] = len(names) == spec.exact_item_count
        if not checks["exact_item_count"]:
            issues.append(f"item_count:{len(names)}!={spec.exact_item_count}")

    category_counts: dict[str, int] = defaultdict(int)
    if category_index is not None:
        for row in data_rows:
            if len(row) > category_index:
                cell = _key(row[category_index])
                for quota in spec.category_quotas:
                    if category_keys_match(quota.category_key, cell):
                        category_counts[quota.category_key] += 1
    observed["category_counts"] = dict(category_counts)
    for quota in spec.category_quotas:
        if quota.exact_count is None:
            continue
        valid = category_counts.get(quota.category_key, 0) == quota.exact_count
        checks[f"category:{quota.category_key}"] = valid
        if not valid:
            issues.append(
                f"category_count:{quota.category_key}:{category_counts.get(quota.category_key, 0)}"
                f"!={quota.exact_count}"
            )

    if budget_index is not None and spec.budget_total:
        values: list[Decimal] = []
        for row in data_rows:
            if len(row) <= budget_index:
                continue
            match = re.search(r"-?\d+(?:[.,]\d+)?", row[budget_index])
            if match:
                try:
                    values.append(Decimal(match.group(0).replace(",", ".")))
                except InvalidOperation:
                    pass
        if values:
            total = sum(values, Decimal(0))
            expected = Decimal(spec.budget_total)
            checks["budget_total"] = total == expected
            observed["budget_total"] = float(total)
            if total != expected:
                issues.append(f"budget_total:{total}!={expected}")

    lowered_names = {_ascii(re.sub(r"[*_`]", "", name)).casefold() for name in names}
    if spec.must_include:
        checks["must_include"] = all(
            _ascii(item).casefold() in lowered_names for item in spec.must_include
        )
    if spec.must_exclude:
        checks["must_exclude"] = all(
            _ascii(item).casefold() not in lowered_names for item in spec.must_exclude
        )
    if spec.comparison_subjects:
        checks["comparison_subjects"] = all(
            subject.casefold() in body.casefold() for subject in spec.comparison_subjects
        )
    valid = all(checks.values()) if checks else bool(names)
    return DeliverableValidationResult(
        valid=valid,
        checks=checks or {"deliverable_table": bool(names)},
        observed=observed,
        issues=issues,
    )
