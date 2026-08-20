from deepscout_evaluation.deterministic import (
    eval_budget_compliance,
    eval_claim_has_evidence,
    eval_forbidden_tool_called,
    eval_provenance_complete,
    eval_quote_resolves,
)


def test_deterministic_evaluators() -> None:
    assert eval_claim_has_evidence(evidence_count=1) is True
    assert eval_claim_has_evidence(evidence_count=0) is False
    assert eval_quote_resolves(quote="NMC cathode", snapshot_text="NMC cathode chemistry") is True
    assert eval_budget_compliance(consumed=3.0, limit=5.0) is True
    assert eval_forbidden_tool_called(tool_name="web_search", allowlist={"web_search"}) is True
    assert eval_forbidden_tool_called(tool_name="shell", allowlist={"web_search"}) is False
    assert eval_provenance_complete(claim_has_source=True, evidence_has_snapshot=True) is True
