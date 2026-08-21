"""Unit tests for HITL policy without Postgres."""

from deepscout_core.domain.enums import ReviewReasonCode
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_research.hitl import PolicyVerdict, evaluate_policy, payload_hash


def test_payload_hash_stable() -> None:
    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert payload_hash(a) == payload_hash(b)


def test_normal_ops_autonomous() -> None:
    settings = Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE, HITL_ENABLED=True)
    # Security-sensitive still requires review when HITL on
    assert (
        evaluate_policy(ReviewReasonCode.SECURITY_SENSITIVE_ACTION, settings)
        == PolicyVerdict.REQUIRE_REVIEW
    )
