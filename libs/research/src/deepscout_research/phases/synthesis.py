"""Evidence-backed synthesis / decision phase."""

from __future__ import annotations

import uuid

from deepscout_core.domain.enums import AgentRole, ClaimVerificationStatus, ResearchPhase
from deepscout_core.domain.schemas import DecisionWrite, SynthesisOutput
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from deepscout_research.context import ContextAssembly
from deepscout_research.prompts import SYNTHESIS_V1, compose_system_message
from deepscout_research.routing.model_router import ModelRouter
from deepscout_research.usage.recorder import langsmith_metadata, record_model_usage


def _admissible_claims(store: ResearchStore, run_id: uuid.UUID):
    return [
        claim
        for claim in store.list_claims(run_id)
        if claim.verification_status
        in {
            ClaimVerificationStatus.VERIFIED,
            ClaimVerificationStatus.PARTIALLY_VERIFIED,
        }
    ]


@traceable(name="phase:synthesis", run_type="chain", metadata=SYNTHESIS_V1.trace_metadata())
def synthesize_decision(
    store: ResearchStore,
    settings: Settings,
    run_id: uuid.UUID,
) -> uuid.UUID | None:
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"ResearchRun {run_id} not found")

    claims = _admissible_claims(store, run_id)
    if not claims:
        return None

    contradictions_count = len(store.list_contradictions(run_id))
    claim_lines = [
        f"- [{claim.id}] ({claim.verification_status.value}) {claim.statement[:500]}"
        for claim in claims
    ]
    context = ContextAssembly(
        run_id=run_id,
        phase=ResearchPhase.SYNTHESIS,
        goal=run.goal,
        system_policy=compose_system_message(SYNTHESIS_V1),
        phase_instructions="Produce structured synthesis from admissible claims only.",
        domain_state={
            "claims": "\n".join(claim_lines),
            "contradictions": str(contradictions_count),
        },
    )

    router = ModelRouter(settings)
    model, selection = router.build_chat_model(AgentRole.SYNTHESIS)
    structured = model.with_structured_output(SynthesisOutput, include_raw=True)
    trace_meta = langsmith_metadata(prompt=SYNTHESIS_V1, selection=selection, run_id=run_id)
    raw_result = structured.invoke(
        [
            SystemMessage(content=compose_system_message(SYNTHESIS_V1)),
            HumanMessage(content=context.render_user_content()),
        ],
        config={"metadata": trace_meta},
    )
    if isinstance(raw_result, dict):
        synthesis = raw_result.get("parsed")
        raw_message = raw_result.get("raw")
    else:
        synthesis = raw_result
        raw_message = None
    if raw_message is not None:
        record_model_usage(
            store,
            settings,
            message=raw_message,
            run_id=run_id,
            phase=ResearchPhase.SYNTHESIS,
            role=AgentRole.SYNTHESIS,
            selection=selection,
            prompt=SYNTHESIS_V1,
        )
    if not isinstance(synthesis, SynthesisOutput):
        synthesis = SynthesisOutput.model_validate(synthesis)

    if synthesis.uncertainty_state == "insufficient_evidence" or not synthesis.supporting_claim_ids:
        return None

    confidence = 0.8 if synthesis.uncertainty_state == "verified" else 0.6
    decision = store.save_decision(
        run_id,
        DecisionWrite(
            recommendation=synthesis.recommendation,
            rationale=synthesis.rationale,
            confidence=confidence,
            supporting_claim_ids=synthesis.supporting_claim_ids,
        ),
    )
    return decision.id
