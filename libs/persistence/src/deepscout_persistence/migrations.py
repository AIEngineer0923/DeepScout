"""Alembic configuration helpers."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config


def persistence_root() -> Path:
    return Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    root = persistence_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    return config
