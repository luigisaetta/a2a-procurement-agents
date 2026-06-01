# Offer Evaluation Accuracy Suite

This folder contains a deterministic accuracy regression suite for the Offer
Evaluation Agent.

The suite includes 20 procurement offer sets. Each case records the expected
decision in `offer-evaluation-accuracy-cases.json`, including either the winning
`offer_id` or a `no_valid_offers` outcome.

## Run the accuracy suite

From the repository root:

```bash
conda run -n a2a-procurement-agents pytest services/offer-evaluation-agent/tests/accuracy/test_accuracy_suite.py
```

## Run all Offer Evaluation Agent tests

The full service test suite also needs the service `src` folder and examples
folder on `PYTHONPATH` because this repository uses independent service source
layouts.

```bash
PYTHONPATH=services/offer-evaluation-agent/src:services/offer-evaluation-agent/examples \
conda run -n a2a-procurement-agents pytest services/offer-evaluation-agent/tests
```

## Run the full repository test suite

```bash
PYTHONPATH=services/offer-evaluation-agent/src:services/offer-evaluation-agent/examples:services/bid-collection-agent/src:services/purchase-order-agent/src:services/procurement-orchestrator/src:services/procurement-data-mcp/src:services/conversational-procurement-intake/src \
conda run -n a2a-procurement-agents pytest
```

## What the suite verifies

The baseline cases cover:

- lowest eligible price selection
- currency mismatch exclusions
- late delivery exclusions
- price, reliability, and delivery-date tie-breakers
- no-valid-offers outcomes
- policy-ignored fields such as `quality_score` and `valid_until`

The pytest runner sends every case through the Offer Evaluation Agent workflow
and compares the actual workflow result with the expected outcome recorded in
the fixture.
