"""Alembic migration entrypoint."""

from alembic import command

from deepscout_persistence.migrations import alembic_config


def main() -> None:
    command.upgrade(alembic_config(), "head")


if __name__ == "__main__":
    main()
