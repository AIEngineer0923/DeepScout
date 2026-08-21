"""Select a minimal skill set. Retrieved text cannot activate or promote skills."""

from __future__ import annotations

from deepscout_research.skills.loader import Skill, load_builtin_skills


def select_skills(text: str, *, limit: int = 2) -> list[Skill]:
    haystack = text.casefold()
    scored: list[tuple[int, Skill]] = []
    for skill in load_builtin_skills():
        score = 0
        slug = skill.skill_id.replace("-", " ")
        if slug in haystack:
            score += 3
        score += sum(2 for trigger in skill.triggers if trigger and trigger in haystack)
        if score:
            scored.append((score, skill))
    scored.sort(key=lambda item: (-item[0], item[1].skill_id))
    return [skill for _, skill in scored[:limit]]


def refuse_document_skill_promotion(_document: str) -> bool:
    """Persistent skills are application-owned. Documents never promote."""
    return True
