"""A deterministic, cost-aware negotiation policy.

The language model example is useful for prose, but it should not be trusted to
invent the economics of a deal.  This agent keeps the decision loop small and
auditable: price every standing offer with the supplier's standard terms, keep
an alternative as a reservation value, make measured concessions, and only
close when the remaining rounds make further value unlikely.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..cost import complete_offer, must_haves_ok, total_cost
from ..docs import standard_terms
from ..play import latest, live_threads, moves_left, standing


@dataclass
class _Offer:
    cost: float
    supplier_id: str
    sheet_id: str
    terms: dict
    standard: dict


class AdvancedAgent:
    """Negotiate from total cost and a reservation value, not list price alone.

    The policy deliberately leaves wording simple.  In a real arena run it is
    safe, fast, and predictable; a presentation layer can later turn its
    selected packages and evidence into more tailored prose.
    """

    def __init__(self, opening_discount=0.10, concession_share=0.35):
        self.opening_discount = opening_discount
        self.concession_share = concession_share

    def decide(self, case, threads):
        offers = self._offers(case, threads)
        if not offers:
            return self._walk(threads)
        best = min(offers, key=lambda o: o.cost)
        events = threads[best.supplier_id]
        status = latest(events).get("status")
        reserve = self._reservation(case)

        # An agreed package is already our proposal.  A final offer is accepted
        # when it beats the outside option: bluffing after that loses deals.
        if status == "agreed" or (status == "final_offer" and best.cost <= reserve):
            return self._accept(best)
        if moves_left(case, events) <= 1:
            return self._accept(best) if best.cost <= reserve else self._walk(threads)

        proposal = self._proposal(case, events, best.terms)
        return {
            "supplier_id": best.supplier_id,
            "message": {
                "subject": f"Re: {case['title']}",
                "body": self._body(case, events),
                "term_sheets": [{"terms": proposal}],
            },
        }

    def _offers(self, case, threads):
        out = []
        for sid in live_threads(threads):
            sheet_id, terms = standing(threads[sid])
            standard = standard_terms(threads[sid])
            if sheet_id and must_haves_ok(case, terms, standard):
                out.append(_Offer(total_cost(case, terms, standard), sid, sheet_id, terms, standard))
        return out

    def _reservation(self, case):
        alternative = case["buyer"].get("alternative") or {}
        terms = alternative.get("terms") or {}
        if terms.get("unit_price") is not None:
            return total_cost(case, terms)
        # Without a quoted alternative, buying the whole horizon at fallback is
        # the conservative walk-away price.
        buyer = case["buyer"]
        return buyer["need_per_year"] * buyer["horizon_years"] * buyer["fallback_unit_price"]

    def _proposal(self, case, events, standing_terms):
        history = [
            message["term_sheets"][0]["terms"].get("unit_price")
            for message in events
            if message.get("from") == "buyer" and message.get("term_sheets")
        ]
        current = standing_terms["unit_price"]
        if not history:
            price = current * (1 - self.opening_discount)
        else:
            # Concede only part of the gap.  This preserves bargaining room and
            # makes every supplier move earn a reciprocal move from us.
            price = history[-1] + (current - history[-1]) * self.concession_share
        proposal = {**standing_terms, "unit_price": round(price, 2)}
        return complete_offer(case, proposal)

    def _body(self, case, events):
        if not any(message.get("from") == "buyer" for message in events):
            return (
                "Thank you for the quotation. Please share the cost breakdown and confirm "
                "whether the proposed package can be approved."
            )
        return "Thank you for the movement. If you can approve this package, we can close promptly."

    @staticmethod
    def _accept(offer):
        return {
            "supplier_id": offer.supplier_id,
            "message": {"action": {"type": "accept", "term_sheet_id": offer.sheet_id}},
        }

    @staticmethod
    def _walk(threads):
        suppliers = live_threads(threads)
        return {"supplier_id": suppliers[0], "message": {"action": {"type": "walk_away"}}}
