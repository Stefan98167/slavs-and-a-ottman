"""Buyer agent that sends deterministic, costed package alternatives."""

from __future__ import annotations

from copy import deepcopy

from negotiator.package_policy import plan_packages
from negotiator.packages import generate_packages

from ..cost import total_cost
from ..docs import standard_terms
from ..play import closing_move, latest, live_threads, standing


class PackageAgent:
    """Offer up to three costed packages from a bounded price ladder.

    Profiles are optional, externally supplied context keyed by supplier ID.
    This agent never infers a supplier trait itself; an unknown profile yields
    price alternatives only.
    """

    def __init__(self, supplier_profiles=None, *, max_discount_pct=5.0):
        self.supplier_profiles = deepcopy(supplier_profiles or {})
        self.max_discount_pct = max_discount_pct
        self.decision_history = []

    def decide(self, case, threads):
        suppliers = [sid for sid in live_threads(threads) if standing(threads[sid])[1].get("unit_price") is not None]
        if not suppliers:
            return closing_move(case, threads)
        sid = min(
            suppliers,
            key=lambda item: total_cost(case, standing(threads[item])[1], standard_terms(threads[item])),
        )
        events = threads[sid]
        if latest(events).get("status") in {"agreed", "final_offer"}:
            return closing_move(case, threads)
        offer_id, offered_terms = standing(events)
        plan = plan_packages(
            case,
            offered_terms,
            self.supplier_profiles.get(sid),
            supplier_standard_terms=standard_terms(events),
            max_discount_pct=self.max_discount_pct,
        )
        generated = generate_packages(
            case,
            offered_terms,
            plan["candidate_unit_prices"],
            standard_terms(events),
            term_constraints_by_price=plan["term_constraints_by_price"],
        )
        packages = generated["packages"]
        if not packages:
            return closing_move(case, threads)
        message = {
            "subject": latest(events).get("subject", case["title"]),
            "body": self._body(packages, plan),
            "term_sheets": [{"terms": package["terms"]} for package in packages],
        }
        self.decision_history.append(
            {
                "supplier_id": sid,
                "offer_id": offer_id,
                "plan": plan,
                "generated": generated,
                "message": message,
            }
        )
        return {"supplier_id": sid, "message": message}

    def close(self, case, threads):
        return closing_move(case, threads)

    @staticmethod
    def _body(packages, plan):
        trade_notes = []
        for package in packages:
            price = package["terms"]["unit_price"]
            trade_notes.extend(plan["rationales_by_price"].get(price, []))
        unique_notes = list(dict.fromkeys(trade_notes))
        note = f" We can trade on {', '.join(unique_notes)}." if unique_notes else ""
        return (
            "Thank you for the offer. We can proceed with one of the attached packages; "
            "please confirm which is workable for you." + note
        )[:8000]
