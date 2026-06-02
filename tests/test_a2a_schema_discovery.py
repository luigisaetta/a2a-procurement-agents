"""
Author: L. Saetta
Date Last Modified: 2026-06-02
License: MIT
Description:    Tests pragmatic JSON Schema discovery endpoints exposed by
                A2A agent servers.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bid_collection_agent.config import (
    REQUEST_SCHEMA_FILE as COLLECT_BIDS_REQUEST_SCHEMA_FILE,
)
from bid_collection_agent.config import (
    RESPONSE_SCHEMA_FILE as COLLECT_BIDS_RESPONSE_SCHEMA_FILE,
)
from bid_collection_agent.config import Settings as BidCollectionSettings
from bid_collection_agent.server import build_server as build_bid_collection_server
from offer_evaluation_agent.config import (
    DEFAULT_POLICY_FILE as OFFER_EVALUATION_POLICY_FILE,
)
from offer_evaluation_agent.config import (
    REQUEST_SCHEMA_FILE as EVALUATE_OFFERS_REQUEST_SCHEMA_FILE,
)
from offer_evaluation_agent.config import (
    RESPONSE_SCHEMA_FILE as EVALUATE_OFFERS_RESPONSE_SCHEMA_FILE,
)
from offer_evaluation_agent.config import Settings as OfferEvaluationSettings
from offer_evaluation_agent.server import build_server as build_offer_evaluation_server
from procurement_orchestrator.config import (
    EVENT_SCHEMA_FILE as ORCHESTRATION_EVENT_SCHEMA_FILE,
)
from procurement_orchestrator.config import (
    REQUEST_SCHEMA_FILE as ORCHESTRATION_REQUEST_SCHEMA_FILE,
)
from procurement_orchestrator.config import (
    RESPONSE_SCHEMA_FILE as ORCHESTRATION_RESPONSE_SCHEMA_FILE,
)
from procurement_orchestrator.config import Settings as OrchestratorSettings
from procurement_orchestrator.server import build_server as build_orchestrator_server
from purchase_order_agent.config import (
    REQUEST_SCHEMA_FILE as CREATE_PURCHASE_ORDER_REQUEST_SCHEMA_FILE,
)
from purchase_order_agent.config import (
    RESPONSE_SCHEMA_FILE as CREATE_PURCHASE_ORDER_RESPONSE_SCHEMA_FILE,
)
from purchase_order_agent.config import Settings as PurchaseOrderSettings
from purchase_order_agent.server import build_server as build_purchase_order_server


@pytest.mark.parametrize(
    ("build_client", "agent_name", "skill_id", "schema_paths"),
    [
        (
            lambda: TestClient(build_bid_collection_server(_bid_settings()).app),
            "bid-collection-agent",
            "collect_bids",
            {
                "input_schema": "/schemas/collect-bids-request.schema.json",
                "output_schema": "/schemas/collect-bids-response.schema.json",
            },
        ),
        (
            lambda: TestClient(build_offer_evaluation_server(_offer_settings()).app),
            "offer-evaluation-agent",
            "evaluate_offers",
            {
                "input_schema": "/schemas/evaluate-offers-request.schema.json",
                "output_schema": "/schemas/evaluate-offers-response.schema.json",
            },
        ),
        (
            lambda: TestClient(build_orchestrator_server(_orchestrator_settings()).app),
            "procurement-orchestrator",
            "run_procurement_workflow",
            {
                "input_schema": (
                    "/schemas/procurement-orchestration-request.schema.json"
                ),
                "event_schema": (
                    "/schemas/procurement-orchestration-event.schema.json"
                ),
                "output_schema": (
                    "/schemas/procurement-orchestration-response.schema.json"
                ),
            },
        ),
        (
            lambda: TestClient(build_purchase_order_server(_purchase_settings()).app),
            "purchase-order-agent",
            "create_purchase_order",
            {
                "input_schema": "/schemas/create-purchase-order-request.schema.json",
                "output_schema": "/schemas/create-purchase-order-response.schema.json",
            },
        ),
    ],
)
def test_a2a_agents_publish_schema_discovery(
    build_client: Callable[[], TestClient],
    agent_name: str,
    skill_id: str,
    schema_paths: dict[str, str],
) -> None:
    """Expose skill-to-schema mappings and serve each referenced schema."""

    client = build_client()

    discovery_response = client.get("/.well-known/a2a-schemas")

    assert discovery_response.status_code == 200
    discovery = discovery_response.json()
    assert discovery["agent"] == agent_name
    assert discovery["protocol_version"] == "1.0"
    assert discovery["skills"][skill_id] == schema_paths

    for schema_path in schema_paths.values():
        schema_response = client.get(schema_path)
        assert schema_response.status_code == 200
        schema = schema_response.json()
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].endswith(Path(schema_path).name)

    missing_response = client.get("/schemas/missing.schema.json")
    assert missing_response.status_code == 404


def _bid_settings() -> BidCollectionSettings:
    """Return minimal Bid Collection Agent settings for server tests."""

    return BidCollectionSettings(
        agent_port=8000,
        agent_api_key="test-key",
        procurement_data_mcp_url="http://mcp.example/mcp",
        mcp_timeout_seconds=10,
        request_schema_file=COLLECT_BIDS_REQUEST_SCHEMA_FILE,
        response_schema_file=COLLECT_BIDS_RESPONSE_SCHEMA_FILE,
    )


def _offer_settings() -> OfferEvaluationSettings:
    """Return minimal Offer Evaluation Agent settings for server tests."""

    return OfferEvaluationSettings(
        oci_region="eu-frankfurt-1",
        oci_auth="API_KEY",
        oci_model_id="test-model",
        oci_compartment_id="ocid1.compartment.oc1..example",
        agent_port=8001,
        agent_api_key="test-key",
        oci_profile="DEFAULT",
        oci_endpoint="https://example.com/openai/v1",
        policy_file=OFFER_EVALUATION_POLICY_FILE,
        request_schema_file=EVALUATE_OFFERS_REQUEST_SCHEMA_FILE,
        response_schema_file=EVALUATE_OFFERS_RESPONSE_SCHEMA_FILE,
    )


def _orchestrator_settings() -> OrchestratorSettings:
    """Return minimal Procurement Orchestrator settings for server tests."""

    return OrchestratorSettings(
        agent_port=8003,
        agent_api_key="test-key",
        bid_collection_agent_url="http://bid.example",
        offer_evaluation_agent_url="http://offer.example",
        purchase_order_agent_url="http://po.example",
        request_schema_file=ORCHESTRATION_REQUEST_SCHEMA_FILE,
        event_schema_file=ORCHESTRATION_EVENT_SCHEMA_FILE,
        response_schema_file=ORCHESTRATION_RESPONSE_SCHEMA_FILE,
    )


def _purchase_settings() -> PurchaseOrderSettings:
    """Return minimal Purchase Order Agent settings for server tests."""

    return PurchaseOrderSettings(
        oci_region="eu-frankfurt-1",
        oci_auth="API_KEY",
        oci_model_id="test-model",
        oci_compartment_id="ocid1.compartment.oc1..example",
        agent_port=8002,
        agent_api_key="test-key",
        oci_profile="DEFAULT",
        oci_endpoint="https://example.com/openai/v1",
        request_schema_file=CREATE_PURCHASE_ORDER_REQUEST_SCHEMA_FILE,
        response_schema_file=CREATE_PURCHASE_ORDER_RESPONSE_SCHEMA_FILE,
        purchase_order_storage_backend="fake",
        db_host="127.0.0.1",
        db_port=3306,
        db_name="procurement_demo",
        db_user="",
        db_password="",
    )
