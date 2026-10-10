"""Evidence-aware, buyer-costed package negotiation for live Arena threads."""

from __future__ import annotations

from copy import deepcopy

from negotiator.evaluator import EvaluationInputError, evaluate_deal
from negotiator.package_policy import plan_packages
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
        for offer in standing_offers:
            events = threads[offer["supplier_id"]]
            if latest(events).get("status") in {"agreed", "final_offer"} or moves_left(case, events) <= 1:
                continue
            candidate = self._package_candidate(case, threads, offer)
            if candidate is not None:
                candidates.append(candidate)
        if candidates:
            return self._counter(min(candidates, key=lambda candidate: candidate["best_cost"]))
        if acceptable:
            # Do not walk away from a valid offer that already beats the buyer's
            # alternative merely because no new package could be generated.
            return self._accept(min(acceptable, key=lambda offer: offer["standing_cost"]))
        return self._walk(threads)

    def close(self, case, threads):
        acceptable = [offer for offer in self._standing_offers(case, threads) if offer["acceptable"]]
        if acceptable:
            return self._accept(min(acceptable, key=lambda offer: offer["standing_cost"]))
        return self._walk(threads)

    def _standing_offers(self, case, threads):
        offers = []
        for supplier_id in live_threads(threads):
            events = threads[supplier_id]
            offer_id, terms = standing(events)
            if not offer_id or not terms.get("unit_price"):
                continue
            standard = standard_terms(events)
            try:
                evaluation = evaluate_deal(case, terms, standard)
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
        try:
            plan = plan_packages(case, offer["terms"], profile, max_discount_pct=self.max_discount_pct)
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
            "body": self._body(candidate["context"], candidate["plan"]),
            "term_sheets": [{"terms": package["terms"]} for package in packages],
        }
        self.decision_history.append({
            "supplier_id": offer["supplier_id"],
            "offer_id": offer["offer_id"],
            "action": "counter_packages",
            "input_policy": "supplier_evidence_buyer_cost_packages",
            "standing_total_cost": offer["standing_cost"],
            "best_package_total_cost": candidate["best_cost"],
            "context_part_id": candidate["context"].get("part_id") if candidate["context"] else None,
            "profile_used": candidate["plan"]["profile_used"],
            "evidence_source": _lead_source(candidate["context"]),
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
            "message": message,
        })
        return {"supplier_id": offer["supplier_id"], "message": message}

    def _walk(self, threads):
        suppliers = live_threads(threads)
        if not suppliers:
            raise ValueError("No live supplier thread")
        message = {"action": {"type": "walk_away"}}
        self.decision_history.append({"supplier_id": suppliers[0], "action": "walk_away", "message": message})
        return {"supplier_id": suppliers[0], "message": message}

    @staticmethod
    def _context(events, supplier_id, part_id):
        bundle = build_thread_supplier_context(events, supplier_id, part_id)
        return context_for_part(bundle, part_id)

    @staticmethod
    def _body(context, plan):
        evidence = _lead_text(context)
        trade_notes = []
        for notes in plan["rationales_by_price"].values():
            trade_notes.extend(notes)
        terms = "; ".join(dict.fromkeys(trade_notes))
        evidence_sentence = f" We reviewed your supplier-provided evidence: {evidence}." if evidence else ""
        return (
            "Thank you for the quotation. We can proceed with one of the attached valid packages; "
            "please confirm which is workable." + evidence_sentence
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
