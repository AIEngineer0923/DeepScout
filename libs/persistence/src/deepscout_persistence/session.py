from threading import RLock

from deepscout_core.settings import get_settings
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

_ENGINES: dict[str, Engine] = {}
_FACTORIES: dict[str, sessionmaker[Session]] = {}
_LOCK = RLock()


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    with _LOCK:
        engine = _ENGINES.get(url)
        if engine is None:
            settings = get_settings()
            engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_recycle=1800,
            )
            _ENGINES[url] = engine
        return engine


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    url = database_url or get_settings().database_url
    with _LOCK:
        factory = _FACTORIES.get(url)
        if factory is None:
            factory = sessionmaker(
                bind=get_engine(url),
                autoflush=False,
                autocommit=False,
                expire_on_commit=False,
            )
            _FACTORIES[url] = factory
        return factory


def get_settings_session() -> Session:
    return get_session_factory(get_settings().database_url)()


def dispose_all_engines() -> None:
    """Dispose pooled engines on graceful shutdown (SIGTERM / lifespan end)."""
    with _LOCK:
        engines = list(_ENGINES.values())
        _ENGINES.clear()
        _FACTORIES.clear()
    for engine in engines:
        engine.dispose()
