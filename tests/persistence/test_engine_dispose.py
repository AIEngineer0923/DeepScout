"""Graceful shutdown disposes pooled engines."""

from unittest.mock import MagicMock

from deepscout_persistence import session as session_mod
from deepscout_persistence.session import dispose_all_engines


def test_dispose_all_engines_clears_pool() -> None:
    fake_engine = MagicMock()
    session_mod._ENGINES["test://dispose"] = fake_engine
    session_mod._FACTORIES["test://dispose"] = MagicMock()
    dispose_all_engines()
    assert session_mod._ENGINES == {}
    assert session_mod._FACTORIES == {}
    fake_engine.dispose.assert_called_once()
