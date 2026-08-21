"""Versioned model pricing — missing entries yield UNKNOWN cost."""

from __future__ import annotations

from deepscout_core.domain.usage import ModelPricingRate, PricingCatalog
from deepscout_core.types import ProviderKind
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS, DEFAULT_EMBEDDING_MODELS

DEFAULT_PRICING_CATALOG = PricingCatalog(
    version="2026-08-21",
    rates=[
        ModelPricingRate(
            provider=ProviderKind.GOOGLE.value,
            model=DEFAULT_CHAT_MODELS[ProviderKind.GOOGLE],
            version="2026-08-21",
            input_per_million_usd=0.30,
            output_per_million_usd=2.50,
            effective_from="2026-08-21",
        ),
        ModelPricingRate(
            provider=ProviderKind.OPENAI.value,
            model=DEFAULT_CHAT_MODELS[ProviderKind.OPENAI],
            version="2026-08-21",
            input_per_million_usd=2.50,
            output_per_million_usd=10.00,
            effective_from="2026-08-21",
        ),
        ModelPricingRate(
            provider=ProviderKind.ANTHROPIC.value,
            model=DEFAULT_CHAT_MODELS[ProviderKind.ANTHROPIC],
            version="2026-08-21",
            input_per_million_usd=3.00,
            output_per_million_usd=15.00,
            effective_from="2026-08-21",
        ),
        ModelPricingRate(
            provider=ProviderKind.GOOGLE.value,
            model=DEFAULT_EMBEDDING_MODELS[ProviderKind.GOOGLE],
            version="2026-08-21",
            input_per_million_usd=0.15,
            output_per_million_usd=0.0,
            effective_from="2026-08-21",
        ),
        ModelPricingRate(
            provider=ProviderKind.OPENAI.value,
            model=DEFAULT_EMBEDDING_MODELS[ProviderKind.OPENAI],
            version="2026-08-21",
            input_per_million_usd=0.02,
            output_per_million_usd=0.0,
            effective_from="2026-08-21",
        ),
    ],
)
