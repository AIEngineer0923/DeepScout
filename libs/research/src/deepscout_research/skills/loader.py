"""Provider-neutral Agent Skills (SKILL.md). Procedure only — never permissions."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Skill:
    skill_id: str
    version: str
    description: str
    body: str
    triggers: tuple[str, ...]


def _builtin_root() -> Path:
    return Path(__file__).resolve().parent / "builtin"


def _parse_frontmatter(block: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def _parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"skill {path} missing YAML frontmatter")
    _, rest = text.split("---", 1)
    fm_raw, body = rest.split("---", 1)
    meta = _parse_frontmatter(fm_raw)
    name = meta.get("name") or path.parent.name
    description = meta.get("description") or ""
    version = "1"
    triggers = tuple(
        part.strip().casefold() for part in meta.get("compatibility", "").split(",") if part.strip()
    )
    return Skill(
        skill_id=name,
        version=version,
        description=description,
        body=body.strip(),
        triggers=triggers or tuple(name.replace("-", " ").split()),
    )


@lru_cache(maxsize=1)
def load_builtin_skills() -> tuple[Skill, ...]:
    skills: list[Skill] = []
    root = _builtin_root()
    if not root.exists():
        return ()
    for skill_md in sorted(root.glob("*/SKILL.md")):
        skills.append(_parse_skill(skill_md))
    return tuple(skills)


def skill_catalog_for_prompt() -> str:
    lines = [
        f"{skill.skill_id} v{skill.version}: {skill.description}" for skill in load_builtin_skills()
    ]
    return "\n".join(lines)
