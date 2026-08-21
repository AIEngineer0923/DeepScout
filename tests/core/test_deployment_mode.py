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
