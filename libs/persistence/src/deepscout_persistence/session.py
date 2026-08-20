from deepscout_core.settings import Settings, get_settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def get_engine(database_url: str | None = None):
    settings = Settings() if database_url is None else None
    url = database_url or settings.database_url  # type: ignore[union-attr]
    return create_engine(url, pool_pre_ping=True)


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    engine = get_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_settings_session() -> Session:
    return get_session_factory(get_settings().database_url)()
