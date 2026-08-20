import pytest
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind

pytestmark = pytest.mark.postgres


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE)
