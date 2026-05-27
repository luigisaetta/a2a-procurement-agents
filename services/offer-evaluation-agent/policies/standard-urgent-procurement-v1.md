# Standard Urgent Procurement Policy

Policy ID: `standard-urgent-procurement-v1`

Version: `0.1.0`

Status: Draft

Applies to: Offer Evaluation Agent

---

## Purpose

This policy defines how the Offer Evaluation Agent selects the best supplier offer for an urgent procurement request.

The policy is intentionally simple and deterministic. It prioritizes offers that can meet the required delivery date, use the expected currency, and minimize procurement cost.

---

## Required Input Fields

The policy uses the following request fields:

- `request_id`
- `currency`
- `required_delivery_date`
- `offers`

The policy uses the following offer fields:

- `offer_id`
- `supplier_id`
- `supplier_name`
- `price`
- `currency`
- `delivery_date`
- `reliability_score`

The `quality_score` and `valid_until` fields are part of the request schema but are not used by this policy version.

---

## Exclusion Rules

The agent must exclude an offer when any of these conditions is true:

1. The offer `currency` is different from the request `currency`.
2. The offer `delivery_date` is later than the request `required_delivery_date`.

Excluded offers must not be selected.

---

## Selection Rules

After applying the exclusion rules, the agent must evaluate only the remaining offers.

### Primary Criterion: Cost

Cost is the primary criterion and represents the dominant 80% policy priority.

Reliability and delivery date are used only as tie-breakers.

The agent must select the offer with the lowest `price` among eligible offers.

### Tie-Breakers

If two or more eligible offers have the same `price`, the agent must apply tie-breakers in this order:

1. Select the offer with the highest `reliability_score`.
2. If reliability is also equal, select the offer with the earliest `delivery_date`.

If offers are still tied after all tie-breakers, the agent may select any one of the tied offers, but the explanation must state that the final choice was made among equivalent offers.

---

## No Valid Offers

If no offers remain after applying the exclusion rules, the agent must return a `no_valid_offers` decision.

The response must include:

- `decision.status` set to `no_valid_offers`
- one or more reasons explaining why no offer was eligible
- a concise human-readable `explanation`

---

## Explanation Requirements

The response explanation must be concise and must mention:

- whether an offer was selected or no valid offer was available
- the main reason for the decision
- the relevant policy criteria used, such as currency, delivery date, cost, reliability, or delivery tie-break

The explanation must not include internal implementation details.

---

## Example Selected Offer Explanation

Supplier B was selected because it provides the lowest eligible cost, uses the requested currency, and meets the required delivery date.

---

## Example No Valid Offers Explanation

No supplier offer was selected because every offer was excluded by the policy due to currency mismatch or delivery dates later than the requested delivery date.
