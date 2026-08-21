from deepscout_core.deployment import DeploymentMode
from deepscout_core.settings import Settings


def test_local_is_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.deployment_mode == DeploymentMode.LOCAL
    assert settings.hosted_auth_ready() is True


def test_hosted_fails_closed_without_secrets() -> None:
    settings = Settings(_env_file=None, DEEPSCOUT_DEPLOYMENT_MODE=DeploymentMode.HOSTED)
    assert settings.is_hosted()
    assert settings.hosted_auth_ready() is False


def test_listen_url_falls_back_to_database_url() -> None:
    settings = Settings(_env_file=None)
    assert settings.listen_database_url() == settings.database_url
    dedicated = Settings(
        _env_file=None,
        DATABASE_LISTEN_URL="postgresql+psycopg://listen@localhost:5432/deepscout",
    )
    assert dedicated.listen_database_url().startswith("postgresql+psycopg://listen@")
