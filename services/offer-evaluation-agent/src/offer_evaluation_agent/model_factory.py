"""
OCI model factory for the Offer Evaluation Agent.

Author: L. Saetta
Date Last Modified: 2026-05-27
License: MIT
Description:    Builds the Locus OCI Chat Completions model used by the
                LLM-driven policy evaluation step.
"""

from __future__ import annotations

from locus.models.providers.oci import OCIChatCompletionsModel

from offer_evaluation_agent.config import Settings


def build_model(settings: Settings) -> OCIChatCompletionsModel:
    """Build the OCI Locus model used for offer evaluation.

    The initial implementation supports OCI API key authentication through
    an OCI config profile. It uses OCI's OpenAI-compatible chat completions
    endpoint through Locus and does not use the Responses API.

    Args:
        settings: Validated runtime settings.

    Returns:
        Configured OCI Chat Completions model.
    """

    return OCIChatCompletionsModel(
        model=settings.oci_model_id,
        profile=settings.oci_profile,
        compartment_id=settings.oci_compartment_id,
        region=settings.oci_region,
        base_url=settings.oci_endpoint,
        temperature=0.0,
        max_tokens=2048,
    )
