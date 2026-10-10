"""Evidence-aware, buyer-costed package negotiation for live Arena threads."""

from __future__ import annotations

import math
import re
from copy import deepcopy

from negotiator.evaluator import EvaluationInputError, evaluate_deal
from negotiator.package_policy import CLAIM_ADJUSTMENT_CAP_PCT, plan_packages
from negotiator.packages import PackageInputError, generate_packages
from negotiator.supplier_evidence import build_thread_supplier_context, context_for_part

from ..docs import standard_terms
from ..play import latest, live_threads, moves_left, standing


class UnifiedAgent:
    """Connect supplier evidence to buyer-efficient package negotiation.

    The agent uses each supplier's live PDF, CSV, email, and offer history as
    sourced context. It selects only packages that pass the buyer's must-haves
    and beat the stated alternative (or the buyer's fallback reservation when
    no alternative quote exists), and it compares package total cost across
    suppliers. Supplier-profile fields remain evidence-driven: unknown fields
    deliberately produce price-only packages rather than invented give-gets.
    """

    def __init__(self, *, max_discount_pct=5.0):
        self.max_discount_pct = max_discount_pct
        self.decision_history = []

    def decide(self, case, threads):
        standing_offers = self._standing_offers(case, threads)
        acceptable = [offer for offer in standing_offers if offer["acceptable"]]
        final_or_last = [
            offer for offer in acceptable
            if latest(threads[offer["supplier_id"]]).get("status") in {"agreed", "final_offer"}
            or moves_left(case, threads[offer["supplier_id"]]) <= 1
        ]
        if final_or_last:
            return self._accept(min(final_or_last, key=lambda offer: offer["standing_cost"]))

        candidates = []
        holds = []
        for offer in standing_offers:
            events = threads[offer["supplier_id"]]
            status = latest(events).get("status")
            if status in {"agreed", "final_offer"} or offer["remaining_moves"] <= 0:
                continue
            previous_buyer = _last_buyer_message(events)
            progress = _supplier_progress(case, events, offer)
            if previous_buyer is not None and progress is False:
                if previous_buyer.get("term_sheets"):
                    holds.append(offer)
                # After the information-seeking hold, do not spend another
                # round repeating the same ask. The existing standing offer
                # remains available for the accept-or-walk decision below.
                continue
            candidate = self._package_candidate(case, threads, offer)
            if candidate is not None:
                candidates.append(candidate)
        if candidates:
            return self._counter(min(candidates, key=lambda candidate: candidate["best_cost"]))
        if holds:
            return self._hold(min(holds, key=lambda offer: offer["standing_cost"]))
        if acceptable:
            # Do not walk away from a valid offer that already beats the buyer's
            # alternative merely because no new package could be generated.
            return self._accept(min(acceptable, key=lambda offer: offer["standing_cost"]))
        return self._walk(threads, standing_offers)

    def close(self, case, threads):
        offers = self._standing_offers(case, threads)
        acceptable = [offer for offer in offers if offer["acceptable"]]
        if acceptable:
            return self._accept(min(acceptable, key=lambda offer: offer["standing_cost"]))
        return self._walk(threads, offers)

    def _standing_offers(self, case, threads):
        offers = []
        for supplier_id in live_threads(threads):
            events = threads[supplier_id]
            offer_id, terms = standing(events)
            if not offer_id or not terms.get("unit_price"):
                continue
            standard = standard_terms(events)
            try:
                # Supplier standing sheets may omit fields listed in
                # `missing_fields`; those close on the supplier PDF's standard
                # terms. Apply those before evaluator defaults so reservation
                # checks match the deal the Arena would actually close.
                effective_terms = _effective_standing_terms(case, terms, standard)
                evaluation = evaluate_deal(case, effective_terms, standard)
            except EvaluationInputError:
                continue
            cost = evaluation["buyer"]["total_cost"]
            if cost is None:
                continue
            offers.append({
                "supplier_id": supplier_id,
                "offer_id": offer_id,
                "terms": deepcopy(terms),
                "standard": standard,
                "evaluation": evaluation,
                "standing_cost": cost,
                "reservation_cost": _reservation_cost(case, evaluation),
                "status": latest(events).get("status"),
                "remaining_moves": moves_left(case, events),
                "claim_results": deepcopy(latest(events).get("claim_results") or []),
                "acceptable": (
                    evaluation["valid_for_negotiation"]
                    and evaluation["buyer"]["total_cost"] <= _reservation_cost(case, evaluation)
                ),
            })
        return offers

    def _package_candidate(self, case, threads, offer):
        events = threads[offer["supplier_id"]]
        context = self._context(events, offer["supplier_id"], offer["terms"].get("part_id"))
        profile = context.get("supplier_profile", {}) if context else {}
        buyer_rounds = sum(event.get("from") == "buyer" for event in events)
        claimed_impact, supplier_claims = (
            _supplier_claim_cost_impact(context) if buyer_rounds == 0 else (0.0, [])
        )
        try:
            plan = plan_packages(
                case,
                offer["terms"],
                profile,
                supplier_standard_terms=offer["standard"],
                claimed_cost_impact_pct=claimed_impact,
                max_discount_pct=self.max_discount_pct,
            )
            generated = generate_packages(
                case,
                offer["terms"],
                plan["candidate_unit_prices"],
                offer["standard"],
                term_constraints_by_price=plan["term_constraints_by_price"],
            )
        except (PackageInputError, EvaluationInputError, ValueError):
            return None
        reservation = _reservation_cost(case, offer["evaluation"])
        packages = [
            package for package in generated["packages"]
            if package["evaluation"]["buyer"]["total_cost"] <= reservation
        ]
        if not packages:
            return None
        citable_ids = set(case.get("refs") or []) | set((case.get("facts") or {}).keys())
        cited_dimensions = {item["profile_dimension"] for item in plan["trade_hypotheses"]}
        if plan["profile_used"]["price_rigid"]:
            cited_dimensions.add("price_rigid")
        profile_refs = sorted({
            evidence["id"]
            for dimension in cited_dimensions
            for evidence in plan["profile_evidence"].get(dimension, [])
            if evidence["id"] in citable_ids
        })[:20]
        plan["supplier_claims_used"] = supplier_claims if plan["claim_adjustment_pct"] else []
        plan["profile_refs"] = profile_refs
        return {
            "offer": offer,
            "context": context,
            "plan": plan,
            "generated": generated,
            "packages": packages,
            "best_cost": packages[0]["evaluation"]["buyer"]["total_cost"],
        }

    def _counter(self, candidate):
        offer = candidate["offer"]
        packages = candidate["packages"]
        message = {
            "subject": latest_context_subject(offer["supplier_id"], candidate["context"]),
            "body": self._body(candidate["context"], candidate["plan"], packages),
            "term_sheets": [{"terms": package["terms"]} for package in packages],
        }
        if candidate["plan"]["profile_refs"]:
            message["refs"] = candidate["plan"]["profile_refs"]
        self.decision_history.append({
            "supplier_id": offer["supplier_id"],
            "offer_id": offer["offer_id"],
            "action": "counter_packages",
            "input_policy": "supplier_evidence_buyer_cost_packages",
            "standing_total_cost": offer["standing_cost"],
            "reservation_cost": offer["reservation_cost"],
            "remaining_moves": offer["remaining_moves"],
            "supplier_status": offer["status"],
            "supplier_claim_results": offer["claim_results"],
            "best_package_total_cost": candidate["best_cost"],
            "context_part_id": candidate["context"].get("part_id") if candidate["context"] else None,
            "profile_used": candidate["plan"]["profile_used"],
            "evidence_source": _lead_source(candidate["context"]),
            "supplier_claimed_cost_impact_pct": candidate["plan"]["claim_adjustment_pct"],
            "supplier_claims_cited": candidate["plan"]["supplier_claims_used"],
            "trade_hypotheses": candidate["plan"]["trade_hypotheses"],
            "generated": candidate["generated"],
            "message": message,
        })
        return {"supplier_id": offer["supplier_id"], "message": message}

    def _accept(self, offer):
        message = {"action": {"type": "accept", "term_sheet_id": offer["offer_id"]}}
        self.decision_history.append({
            "supplier_id": offer["supplier_id"],
            "offer_id": offer["offer_id"],
            "action": "accept",
            "input_policy": "supplier_evidence_buyer_cost_packages",
            "standing_total_cost": offer["standing_cost"],
            "reservation_cost": offer.get("reservation_cost"),
            "remaining_moves": offer.get("remaining_moves"),
            "supplier_status": offer.get("status"),
            "supplier_claim_results": offer.get("claim_results", []),
            "message": message,
        })
        return {"supplier_id": offer["supplier_id"], "message": message}

    def _hold(self, offer):
        message = {
            "subject": latest_context_subject(offer["supplier_id"], None),
            "body": (
                "Before we send another counter, could you identify the term preventing approval "
                "and share the supporting cost breakdown? That will help us assess a workable package."
            ),
        }
        self.decision_history.append({
            "supplier_id": offer["supplier_id"],
            "offer_id": offer["offer_id"],
            "action": "hold",
            "input_policy": "supplier_evidence_buyer_cost_packages",
            "standing_total_cost": offer["standing_cost"],
            "reservation_cost": offer["reservation_cost"],
            "remaining_moves": offer["remaining_moves"],
            "supplier_status": offer["status"],
            "supplier_claim_results": offer["claim_results"],
            "reason": "supplier standing terms did not improve after the buyer's package counter",
            "message": message,
        })
        return {"supplier_id": offer["supplier_id"], "message": message}

    def _walk(self, threads, offers=None):
        suppliers = live_threads(threads)
        if not suppliers:
            raise ValueError("No live supplier thread")
        offer = min(offers or [], key=lambda item: item["standing_cost"], default=None)
        supplier_id = offer["supplier_id"] if offer else suppliers[0]
        message = {"action": {"type": "walk_away"}}
        self.decision_history.append({
            "supplier_id": supplier_id,
            "action": "walk_away",
            "reason": "no available package beats the reservation cost" if offer else "no complete standing offer",
            "standing_total_cost": offer["standing_cost"] if offer else None,
            "reservation_cost": offer["reservation_cost"] if offer else None,
            "remaining_moves": offer["remaining_moves"] if offer else None,
            "supplier_status": offer["status"] if offer else None,
            "supplier_claim_results": offer["claim_results"] if offer else [],
            "message": message,
        })
        return {"supplier_id": supplier_id, "message": message}

    @staticmethod
    def _context(events, supplier_id, part_id):
        bundle = build_thread_supplier_context(events, supplier_id, part_id)
        return context_for_part(bundle, part_id)

    @staticmethod
    def _body(context, plan, packages):
        evidence = _lead_text(context)
        trade_notes = []
        used_trades = []
        for package in packages:
            price = package["terms"]["unit_price"]
            trade_notes.extend(plan["rationales_by_price"].get(price, []))
            for hypothesis in plan["trade_hypotheses"]:
                if all(package["terms"].get(field) == value
                       for field, value in hypothesis["buyer_gives"].items()):
                    used_trades.append(hypothesis)
        terms = "; ".join(dict.fromkeys(trade_notes))
        claim_sentences = [
            _claim_citation(claim) for claim in plan.get("supplier_claims_used", [])[:3]
        ]
        evidence_sentence = f" We reviewed your supplier-provided evidence: {evidence}." if evidence else ""
        if any(claim.get("claim_text") and claim["claim_text"] in str(evidence)
               for claim in plan.get("supplier_claims_used", [])):
            evidence_sentence = ""
        trade_sentences = []
        for hypothesis in used_trades:
            sources = list(dict.fromkeys(
                item["source"] for item in hypothesis["evidence"]
                if item.get("source") and not _looks_like_arena_id(item["source"])
            ))
            source_note = f"; linked to {', '.join(sources[:2])}" if sources else ""
            trade_sentences.append(
                f"The {hypothesis['profile_dimension'].replace('_', ' ')} package trade is supported"
                f" by the linked supplier profile evidence{source_note}."
            )
        if plan["profile_used"]["price_rigid"]:
            sources = [
                item["source"] for item in plan["profile_evidence"].get("price_rigid", [])
                if item.get("source") and not _looks_like_arena_id(item["source"])
            ]
            source_note = f" from {', '.join(dict.fromkeys(sources[:2]))}" if sources else ""
            trade_sentences.append(
                f"The softer price ladder reflects supported price-rigidity evidence{source_note}."
            )
        claim_note = (
            " These are supplier-stated claims; their effect on this opening ask is capped at "
            f"{CLAIM_ADJUSTMENT_CAP_PCT:g} percentage points."
            if claim_sentences else ""
        )
        return (
            "Thank you for the quotation. We can proceed with one of the attached valid packages; "
            "please confirm which is workable." + evidence_sentence
            + (" " + " ".join(claim_sentences) + claim_note if claim_sentences else "")
            + (" " + " ".join(dict.fromkeys(trade_sentences)) if trade_sentences else "")
            + (f" The packages reflect: {terms}." if terms else "")
            + " Please share the supporting cost breakdown."
        )[:8000]


def latest_context_subject(supplier_id, context):
    """Use a stable supplier-focused subject without exposing buyer-side details."""
    part_id = context.get("part_id") if context else None
    return f"Re: quotation {part_id or supplier_id}"


def _lead_source(context):
    if not context:
        return None
    evidence = [item for item in context.get("evidence", []) if isinstance(item, dict) and item.get("source")]
    evidence.sort(key=lambda item: item.get("priority") if type(item.get("priority")) is int else 99)
    return evidence[0].get("source") if evidence else None


def _lead_text(context):
    if not context:
        return None
    evidence = [item for item in context.get("evidence", []) if isinstance(item, dict)]
    evidence.sort(key=lambda item: (
        item.get("priority") if type(item.get("priority")) is int else 99,
        0 if item.get("kind") == "claim" else 1,
    ))
    if not evidence:
        return None
    data = evidence[0].get("data") or {}
    text = data.get("claim_text")
    if text:
        return str(text)[:240]
    source = evidence[0].get("source")
    return f"quote source {source}" if source else None


def _supplier_claim_cost_impact(context):
    """Calculate a bounded-policy input from explicit supplier index/share claims."""
    if not context:
        return 0.0, []
    by_series = {}
    for item in context.get("supplier_claims", []):
        if not isinstance(item, dict):
            continue
        data = item.get("data") or {}
        series = data.get("series")
        change = data.get("index_change_pct")
        share = data.get("cost_share_pct")
        if not isinstance(series, str) or not series.strip():
            continue
        if isinstance(change, bool) or isinstance(share, bool):
            continue
        try:
            change = float(str(change).replace(",", "."))
            share = float(str(share).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(change) and -100 <= change <= 1000):
            continue
        if not (math.isfinite(share) and 0 <= share <= 100):
            continue
        by_series[series.strip().upper()] = {
            "series": series.strip().upper(),
            "index_change_pct": change,
            "cost_share_pct": share,
            "impact_pct": change * share / 100,
            "claim_text": _safe_text(data.get("claim_text"), 240),
            "source": _safe_text(item.get("source"), 180),
        }
    claims = list(by_series.values())
    return sum(item["impact_pct"] for item in claims), claims


def _claim_citation(claim):
    if claim.get("claim_text"):
        assertion = claim["claim_text"]
    else:
        assertion = (
            f"{claim['series']} moved {claim['index_change_pct']:+g}% and is "
            f"{claim['cost_share_pct']:g}% of your cost"
        )
    return f"Your email states: {assertion}."


def _safe_text(value, limit):
    if not isinstance(value, str):
        return None
    return re.sub(r"[\r\n\x00-\x1f]+", " ", value).strip()[:limit] or None


def _looks_like_arena_id(value):
    return isinstance(value, str) and bool(
        re.match(r"^(?:idx|quote|sc|qn|po|cost|fc|news|doc|ctr|offer):", value)
    )


def _reservation_cost(case, evaluation):
    """Use a quoted alternative when available, otherwise the buyer fallback."""
    alternative = evaluation["buyer"].get("alternative_cost")
    if alternative is not None:
        return alternative
    buyer = case.get("buyer", {})
    try:
        return float(buyer["need_per_year"]) * float(buyer["horizon_years"]) * float(buyer["fallback_unit_price"])
    except (KeyError, TypeError, ValueError):
        return float("inf")


def _last_buyer_message(events):
    return next((event for event in reversed(events) if event.get("from") == "buyer"), None)


def _effective_standing_terms(case, terms, standard):
    """Complete missing negotiable supplier terms from its quote PDF."""
    negotiable = case.get("negotiable", [])
    supplier_defaults = {field: standard[field] for field in negotiable if field in standard}
    return {**supplier_defaults, **terms}


def _supplier_progress(case, events, current_offer):
    """Return None for an opening quote; otherwise whether the supplier improved."""
    supplier_offers = [
        event for event in events
        if event.get("from") != "buyer" and event.get("term_sheets")
    ]
    if len(supplier_offers) < 2:
        return None
    previous_terms = supplier_offers[-2]["term_sheets"][0].get("terms") or {}
    if previous_terms == current_offer["terms"]:
        return False
    try:
        effective_previous_terms = _effective_standing_terms(
            case, previous_terms, current_offer["standard"]
        )
        previous_evaluation = evaluate_deal(
            case, effective_previous_terms, current_offer["standard"]
        )
    except (EvaluationInputError, TypeError, ValueError):
        return False
    previous_cost = previous_evaluation["buyer"]["total_cost"]
    current_cost = current_offer["standing_cost"]
    if previous_cost is None or current_cost is None:
        return False
    # A changed term sheet at equal or lower buyer cost is movement. A worse
    # counter does not earn a fresh price ladder that would give ground back.
    return current_cost <= previous_cost + 0.01
