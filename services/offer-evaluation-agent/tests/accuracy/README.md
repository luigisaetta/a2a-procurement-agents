# Offer Evaluation Accuracy Suite

This folder contains the accuracy regression suite for the Offer Evaluation
Agent.

The suite includes 20 procurement offer sets. Each case records the expected
decision in `offer-evaluation-accuracy-cases.json`, including either the winning
`offer_id` or a `no_valid_offers` outcome. When the policy accepts several
equivalent winners, the case lists them in `accepted_offer_ids`.

The decision is made only by the LLM, which applies the Markdown policy. The
agent code does not apply procurement rules, so decision accuracy can only be
measured with a live LLM.

## Run the offline suite

From the repository root:

```bash
conda run -n a2a-procurement-agents pytest services/offer-evaluation-agent/tests/accuracy/test_accuracy_suite.py
```

By default this runs only the offline test. For every case it answers with the
recorded expected decision in place of the LLM, and checks that the workflow
returns that decision unchanged and that it passes the technical consistency
checks. It needs no OCI access. The live LLM test is skipped unless explicitly
enabled.

## Measure LLM accuracy

To measure how often the configured LLM makes the expected decision, enable the
live LLM test:

```bash
OFFER_EVALUATION_RUN_LIVE_LLM=1 \
conda run -n a2a-procurement-agents pytest services/offer-evaluation-agent/tests/accuracy/test_accuracy_suite.py::test_live_llm_accuracy_report
```

This requires the same OCI environment variables used by the Offer Evaluation
Agent runtime. It sends all 20 cases to the LLM, so it has a model usage cost.
The test fails if any case is wrong.

The test writes a generated report to:

```text
services/offer-evaluation-agent/tests/accuracy/results/latest-llm-accuracy-report.json
```

The report records:

- error count
- accuracy
- per-case expected outcome, LLM outcome, and technical error, if the LLM
  answer was rejected by the consistency checks

The `results/` folder is intentionally gitignored because it contains generated
run output.

## Run the full repository test suite

```bash
./check.sh
```

## What the suite covers

The baseline cases cover:

- lowest eligible price selection
- currency mismatch exclusions
- late delivery exclusions
- price, reliability, and delivery-date tie-breakers
- offers still tied after all tie-breakers
- no-valid-offers outcomes
- policy-ignored fields such as `quality_score` and `valid_until`
