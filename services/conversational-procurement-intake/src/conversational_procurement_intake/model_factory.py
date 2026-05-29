"""
Author: L. Saetta
Date Last Modified: 2026-05-29
License: MIT
Description:    OCI model factory for conversational intake LLM extraction.
"""

from __future__ import annotations

from locus.models.providers.oci import OCIChatCompletionsModel

from conversational_procurement_intake.config import Settings


def build_model(settings: Settings) -> OCIChatCompletionsModel:
    """Build the OCI Locus model used for intake extraction.

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
