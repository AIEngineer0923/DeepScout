"""Extensible, capability-aware source discovery and acquisition fabric."""

from deepscout_research.source_fabric.registry import (
    ConnectorRegistry,
    SourceCapability,
    baseline_connector_registry,
)
from deepscout_research.source_fabric.router import DiscoveryRouter, build_discovery_router
from deepscout_research.source_fabric.strategy import (
    DiscoveryRequest,
    QueryStrategy,
    SourceStrategy,
    infer_source_kind,
    plan_source_strategy,
)

__all__ = [
    "ConnectorRegistry",
    "DiscoveryRequest",
    "DiscoveryRouter",
    "QueryStrategy",
    "SourceCapability",
    "SourceStrategy",
    "baseline_connector_registry",
    "build_discovery_router",
    "infer_source_kind",
    "plan_source_strategy",
]
