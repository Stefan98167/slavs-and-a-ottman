"""Evidence-aware, buyer-costed package negotiation for live Arena threads."""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Mapping
from copy import deepcopy

from negotiator.buyer_arguments import price_evidence_reply, source_document_reply
from negotiator.case_evidence import CaseSupplierEvidence
from negotiator.dialogue_recovery import (
    can_clarify,
    capacity_refused,
    indicative_alternative,
    recovery_message,
    unasked_trade_terms,
)
from negotiator.evaluator import EvaluationInputError, evaluate_deal
from negotiator.offer_restoration import RESTORE_OFFER_MARKER, restore_prior_offer
from negotiator.package_policy import plan_packages, recheck_buyer_terms
from negotiator.packages import PackageInputError, generate_packages
from negotiator.proposal_safety import finite_number, reservation_cost, select_proposal
from negotiator.response_signal import supplier_sentences
from negotiator.response_trades import RESPONSE_TRADE_MARKER, response_trade_packages
from negotiator.supplier_alternatives import ALTERNATIVE_MARKER, supplier_alternative_package
from negotiator.supplier_economics import estimate_supplier_economics
from negotiator.supplier_evidence import build_thread_supplier_context, context_for_part
from negotiator.term_repair import REPAIR_MARKER, restoration_packages

from ..cost import closing_terms
from ..docs import quote_terms, standard_terms
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

    def __init__(self, *, max_discount_pct=5.0, package=None, min_improvement_pct=0.1,
                 claim_adjustment_cap_pct=0.0, minimum_rounds=2):
        for name, value, ceiling in (("max_discount_pct", max_discount_pct, 100),
                                     ("min_improvement_pct", min_improvement_pct, 100),
                                     ("claim_adjustment_cap_pct", claim_adjustment_cap_pct, 2.000001)):
            if not finite_number(value) or not 0 <= value < ceiling:
                raise ValueError(f"{name} must be finite, non-negative and within its documented cap")
        if type(minimum_rounds) is not int or minimum_rounds < 0:
            raise ValueError("minimum_rounds must be a non-negative integer")
        self.max_discount_pct = max_discount_pct
        self.min_improvement_pct = min_improvement_pct
        self.claim_adjustment_cap_pct = claim_adjustment_cap_pct
        self.minimum_rounds = minimum_rounds
        self.opening_goals = {}
        self.decision_history = []
        self.package = package
        self.archive = CaseSupplierEvidence(package) if package else None
        self.supplier_archive_enabled = os.environ.get("SUPPLIER_ARCHIVE_EVIDENCE") == "1"
        self.prepared_case = None
        self.archive_records = {}
        self.evidence_warnings = []
        self.supplier_economics_enabled = os.environ.get("SUPPLIER_ECONOMICS") == "1"
        self.supplier_facts = self._load_supplier_facts() if self.supplier_economics_enabled else {}

    @staticmethod
    def _load_supplier_facts():
        from ..data import DataPackage

        root = os.environ.get("ARENA_DATA", "data")
        try:
            return DataPackage(root).facts
        except (OSError, ValueError, TypeError):
            return {}

    def _supplier_economics(self, case, supplier_id):
        if not self.supplier_economics_enabled:
            return None
        inline_facts = case.get("facts")
        facts = {**self.supplier_facts, **(inline_facts if isinstance(inline_facts, Mapping) else {})}
        return estimate_supplier_economics(case, supplier_id, facts)

    def _load_archive(self):
        from ..data import DataPackage

        root = os.environ.get("ARENA_DATA", "data")
        try:
            return CaseSupplierEvidence(DataPackage(root))
        except (OSError, ValueError, TypeError):
            return CaseSupplierEvidence()

    def prepare(self, case):
        if self.prepared_case != case.get("case_id"):
            if self.archive is None and self.supplier_archive_enabled:
                self.archive = self._load_archive()
            self.archive_records, self.evidence_warnings = (
                self.archive.prepare(case) if self.archive else ({}, [])
            )
            self.prepared_case = case.get("case_id")

    def decide(self, case, threads):
        self.prepare(case)
        standing_offers = self._standing_offers(case, threads)
        for offer in standing_offers:
            offer["opening_goal"] = self._opening_goal(case, offer["supplier_id"], threads[offer["supplier_id"]])
            offer["buyer_rounds"] = sum(event.get("from") == "buyer" for event in threads[offer["supplier_id"]])
        acceptable = [offer for offer in standing_offers if offer["acceptable"]]

        candidates = []
        holds = []
        clarifications = []
        trade_clarifications = []
        recoveries = []
        represented = {offer["supplier_id"] for offer in standing_offers}
        for sid in live_threads(threads):
            events = threads[sid]
            if (sid not in represented and latest(events).get("status") == "open"
                    and moves_left(case, events) > 0 and can_clarify(events, "incomplete_offer")):
                recoveries.append((sid, "incomplete_offer", None))
        ceiling = min((offer["standing_cost"] for offer in acceptable), default=None)
        for offer in standing_offers:
            events = threads[offer["supplier_id"]]
            status = latest(events).get("status")
            if offer["response_conflict"]:
                previous_buyer = _last_buyer_message(events)
                if (status == "open" and offer["remaining_moves"] > 0
                        and not _asked_to_reconcile(previous_buyer)):
                    clarifications.append(offer)
                continue
            if status in {"agreed", "final_offer"} or offer["remaining_moves"] <= 0:
                continue
            previous_buyer = _last_buyer_message(events)
            if offer["missing_supplier_terms"]:
                if can_clarify(events, "incomplete_offer"):
                    recoveries.append((offer["supplier_id"], "incomplete_offer", offer))
                continue
            if (previous_buyer and capacity_refused(latest(events))
                    and can_clarify(events, "capacity")):
                recoveries.append((offer["supplier_id"], "capacity", offer))
                continue
            if (indicative_alternative(latest(events), case["negotiable"])
                    and can_clarify(events, "alternative")
                    and not supplier_alternative_package(
                        case, offer, events, offer.get("supplier_economics")
                    )):
                recoveries.append((offer["supplier_id"], "alternative", offer))
                continue
            progress = _supplier_progress(case, events, offer)
            invited_terms = unasked_trade_terms(events, [
                field for field in _supplier_invited_terms(latest(events))
                if field in case.get("negotiable", [])
            ])
            if (previous_buyer is not None
                    and (("index_clause" in invited_terms and offer["closed_terms"].get("index_clause") is None)
                         or ("ppm_commitment" in invited_terms
                             and "ppm_commitment" in offer["missing_supplier_terms"]))):
                trade_clarifications.append((offer, invited_terms))
                continue
            candidate = self._package_candidate(case, threads, offer, ceiling=ceiling)
            if candidate is not None:
                candidates.append(candidate)
            elif invited_terms and previous_buyer is not None:
                trade_clarifications.append((offer, invited_terms))
            elif (not offer["evaluation"]["valid_for_negotiation"]
                  and can_clarify(events, "feasibility")):
                recoveries.append((offer["supplier_id"], "feasibility", offer))
            elif previous_buyer is not None and progress is False and previous_buyer.get("term_sheets"):
                holds.append(offer)
        if candidates:
            best = min(acceptable, key=lambda offer: offer["standing_cost"], default=None)
            concrete = [candidate for candidate in candidates
                        if (candidate["plan"].get("supplier_alternative") or candidate["plan"].get("offer_restoration"))
                        and best is not None and candidate["best_cost"] < best["standing_cost"] - 0.01]
            if (best is not None and best["opening_goal"] is not None
                    and best["buyer_rounds"] >= self.minimum_rounds
                    and best["standing_cost"] <= best["opening_goal"] + 0.01 and not concrete):
                return self._accept(best, reason="anchored opening buyer-cost goal reached")
            potential = min(candidate["best_cost"] for candidate in candidates)
            if best is not None and potential >= best["standing_cost"] - max(
                0.01, best["standing_cost"] * self.min_improvement_pct / 100
            ) and best["buyer_rounds"] >= self.minimum_rounds:
                if concrete:
                    return self._counter(min(concrete, key=lambda candidate: candidate["best_cost"]), case)
                return self._accept(best, reason="remaining proposals offer only negligible buyer-cost improvement")
            return self._counter(min(candidates, key=lambda candidate: candidate["best_cost"]), case)
        if clarifications:
            return self._answer_requested_evidence(
                self._clarify(min(clarifications, key=lambda offer: offer["standing_cost"])), case, threads)
        if recoveries:
            return self._answer_requested_evidence(self._recover(*recoveries[0]), case, threads)
        if trade_clarifications:
            offer, fields = min(trade_clarifications, key=lambda item: item[0]["standing_cost"])
            return self._answer_requested_evidence(self._clarify_trade(offer, fields), case, threads)
        if holds:
            return self._answer_requested_evidence(
                self._hold(min(holds, key=lambda offer: offer["standing_cost"])), case, threads)
        if acceptable:
            # Do not walk away from a valid offer that already beats the buyer's
            # alternative merely because no new package could be generated.
            return self._accept(min(acceptable, key=lambda offer: offer["standing_cost"]))
        return self._walk(threads, standing_offers)

    def _opening_goal(self, case, supplier_id, events):
        """An aspiration anchored to opening evidence, not to our later concessions."""
        end = next((i + 1 for i, event in enumerate(events)
                    if event.get("from") not in {"buyer", "arena"} and event.get("term_sheets")), None)
        if end is None:
            return None
        prefix = events[:end]
        key = (case.get("case_id"), supplier_id, _terms_key(prefix))
        if key in self.opening_goals:
            return self.opening_goals[key]
        goal = None
        offers = self._standing_offers(case, {supplier_id: prefix})
        if offers:
            opening = offers[0]
            parts = case.get("parts") or []
            context = self._context(prefix, supplier_id, parts[0] if len(parts) == 1 else None)
            impact, _ = _supplier_claim_cost_impact(context)
            economics = opening.get("supplier_economics")
            try:
                plan = plan_packages(case, opening["terms"], (context or {}).get("supplier_profile", {}),
                                     supplier_standard_terms=opening["standard"],
                                     max_discount_pct=self.max_discount_pct,
                                     claimed_cost_impact_pct=max(-self.claim_adjustment_cap_pct,
                                                                 min(self.claim_adjustment_cap_pct, impact)))
                generated = generate_packages(case, opening["terms"], plan["candidate_unit_prices"],
                                              opening["standard"], supplier_economics=economics,
                                              term_constraints_by_price=plan["term_constraints_by_price"])
                goal = min((p["evaluation"]["buyer"]["total_cost"] for p in generated["packages"]
                            if p["evaluation"]["buyer"]["total_cost"] <= opening["reservation_cost"]), default=None)
            except (PackageInputError, EvaluationInputError, TypeError, ValueError):
                pass
        self.opening_goals[key] = goal
        return goal

    def decide_batch(self, case, threads):
        """One send per actionable supplier, with closing chosen only globally.

        The runner can dispatch these independent supplier messages together.
        Per-thread accept/walk suggestions never close a whole RFQ prematurely.
        """
        primary = self.decide(case, threads)
        if primary["message"].get("action"):
            return [primary]
        decisions = [primary]
        ceiling = min((offer["standing_cost"] for offer in self._standing_offers(case, threads)
                       if offer["acceptable"]), default=None)
        for sid in live_threads(threads):
            if sid == primary["supplier_id"]:
                continue
            history_size = len(self.decision_history)
            candidate = self.decide(case, {sid: threads[sid]})
            last = self.decision_history[-1]
            if (candidate["message"].get("action") or (ceiling is not None
                    and last.get("best_package_total_cost", 0) > ceiling)):
                del self.decision_history[history_size:]  # This was considered, not sent.
            else:
                decisions.append(candidate)
        return decisions

    def close(self, case, threads):
        offers = self._standing_offers(case, threads)
        acceptable = [offer for offer in offers if offer["acceptable"]]
        if acceptable:
            return self._accept(min(acceptable, key=lambda offer: offer["standing_cost"]))
        return self._walk(threads, offers)

    def reconsider_close(self, case, threads):
        """Replace an unsent closing decision after authoritative state refresh."""
        if self.decision_history and self.decision_history[-1]["action"] in {"accept", "walk_away"}:
            self.decision_history[-1]["action"] = "superseded_close"
            self.decision_history[-1]["sent"] = False
        result = self.close(case, threads)
        self.decision_history[-1]["reason"] += "; re-evaluated after remote state refresh"
        return result

    def _standing_offers(self, case, threads):
        offers = []
        for supplier_id in live_threads(threads):
            events = threads[supplier_id]
            offer_id, terms = standing(events)
            if not offer_id or not terms.get("unit_price"):
                continue
            try:
                supplier_events = [event for event in events if event.get("from") not in {"buyer", "arena"}]
                if not _compatible_quote_basis(supplier_events):
                    continue
                standard = standard_terms(supplier_events)
                economics = self._supplier_economics(case, supplier_id)
                # Supplier standing sheets may omit fields listed in
                # `missing_fields`; those close on the supplier PDF's standard
                # terms. Apply those before evaluator defaults so reservation
                # checks match the deal the Arena would actually close.
                effective_terms = _effective_standing_terms(case, terms, standard)
                evaluation = evaluate_deal(case, effective_terms, standard, economics)
            except (EvaluationInputError, TypeError, ValueError):
                continue
            cost = evaluation["buyer"]["total_cost"]
            if cost is None:
                continue
            closed_terms = closing_terms(case, evaluation["final_terms"], standard)
            response_conflict = _thread_response_conflict(events, closed_terms)
            offers.append({
                "supplier_id": supplier_id,
                "offer_id": offer_id,
                "terms": deepcopy(terms),
                "standard": standard,
                "supplier_economics": economics,
                "evaluation": evaluation,
                "closed_terms": closed_terms,
                "standing_cost": cost,
                "reservation_cost": _reservation_cost(case, evaluation),
                "status": latest(events).get("status"),
                "remaining_moves": moves_left(case, events),
                "claim_results": deepcopy(latest(events).get("claim_results") or []),
                "response_conflict": response_conflict,
                "cost_breakdown_refused": _cost_breakdown_refused(events),
                "cost_breakdown_requested": any(event.get("from") == "buyer" and
                                                "supporting cost breakdown" in str(event.get("body", "")).lower()
                                                for event in events),
                "missing_supplier_terms": [field for field in case.get("negotiable", [])
                                           if field not in effective_terms],
                "acceptable": (
                    evaluation["valid_for_negotiation"]
                    and evaluation["buyer"]["total_cost"] <= _reservation_cost(case, evaluation)
                    and not response_conflict
                    and all(field in effective_terms for field in case.get("negotiable", []))
                ),
            })
        return offers

    def _package_candidate(self, case, threads, offer, *, ceiling=None):
        events = threads[offer["supplier_id"]]
        parts = case.get("parts") or []
        part_id = offer["terms"].get("part_id") or (parts[0] if len(parts) == 1 else None)
        context = self._context(events, offer["supplier_id"], part_id)
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
                claimed_cost_impact_pct=max(-self.claim_adjustment_cap_pct,
                                            min(self.claim_adjustment_cap_pct, claimed_impact)),
                max_discount_pct=self.max_discount_pct,
            )
            previous_sheets = _last_buyer_sheets(events)
            if previous_sheets:
                _advance_price_ladder(case, plan, events, offer, previous_sheets)
                recheck_buyer_terms(case, plan, offer["terms"], offer["standard"])
            if not plan["candidate_unit_prices"]:
                repairs = restoration_packages(
                    case, offer, previous_sheets, events, offer.get("supplier_economics")
                )
                generated = {"packages": repairs, "selection_policy": "bounded term restoration"}
                plan["term_restoration"] = bool(repairs)
                plan["trade_hypotheses"] = []
            else:
                generated = generate_packages(
                    case,
                    offer["terms"],
                    plan["candidate_unit_prices"],
                    offer["standard"],
                    supplier_economics=offer.get("supplier_economics"),
                    term_constraints_by_price=plan["term_constraints_by_price"],
                )
        except (PackageInputError, EvaluationInputError, ValueError):
            return None
        reservation = _reservation_cost(case, offer["evaluation"])
        packages = [
            package for package in generated["packages"]
            if package["evaluation"]["buyer"]["total_cost"] <= reservation
        ]
        # Same commercial terms at three different prices offer no meaningful
        # choice. Retain the cheapest; the internal ladder remains for planning.
        distinct = {}
        for package in packages:
            key = _terms_key({k: v for k, v in package["terms"].items() if k != "unit_price"})
            distinct.setdefault(key, package)
        packages = list(distinct.values())
        if previous_sheets:
            prior_terms = {_terms_key(sheet.get("terms")) for sheet in previous_sheets}
            packages = [package for package in packages if _terms_key(package["terms"]) not in prior_terms]
        negligible = max(0.01, offer["standing_cost"] * self.min_improvement_pct / 100)
        if not packages or packages[0]["evaluation"]["buyer"]["total_cost"] >= offer["standing_cost"] - negligible:
            responses = response_trade_packages(
                case, offer, events, _supplier_invited_terms(latest(events)),
                offer.get("supplier_economics"),
            )
            if responses:
                packages = responses
                generated = {"packages": responses, "selection_policy": "bounded response trade"}
                plan["response_trade"] = True
                plan["term_restoration"] = False
                plan["trade_hypotheses"] = []
        # A supplier's own fully specified alternative is stronger evidence
        # than another hypothetical discount. Confirm it before it disappears
        # from a later reply; only the primary standing ID is directly accepted.
        if alternative := supplier_alternative_package(
            case, offer, events, offer.get("supplier_economics")
        ):
            packages = [alternative]
            generated = {"packages": packages, "selection_policy": "confirm supplier structured alternative"}
            plan["supplier_alternative"] = True
            plan["response_trade"] = False
            plan["term_restoration"] = False
            plan["trade_hypotheses"] = []
        if restored := restore_prior_offer(case, offer, events, offer.get("supplier_economics")):
            if not plan.get("supplier_alternative") or restored["evaluation"]["buyer"]["total_cost"] < min(
                    p["evaluation"]["buyer"]["total_cost"] for p in packages):
                packages = [restored]
                plan.update(offer_restoration=True, supplier_alternative=False,
                            response_trade=False, term_restoration=False, trade_hypotheses=[])
                generated = {"packages": packages, "selection_policy": "request prior quote renewal"}
        if not packages:
            return None
        considered = deepcopy(packages)
        packages, excluded = select_proposal(
            case, offer, packages, events, ceiling, offer.get("supplier_economics")
        )
        if not packages:
            return None
        plan["selection_audit"] = {"considered": considered, "excluded": excluded,
                                   "selected_terms": deepcopy(packages[0]["terms"])}
        citable_ids = set(case.get("refs") or []) | set((case.get("facts") or {}).keys())
        citable_ids.update(record["Information"]["id"]
                           for record in self.archive_records.get(offer["supplier_id"], []))
        cited_dimensions = {item["profile_dimension"] for item in plan["trade_hypotheses"]}
        if plan["profile_used"]["price_rigid"]:
            cited_dimensions.add("price_rigid")
        profile_refs = sorted({
            evidence["id"]
            for dimension in cited_dimensions
            for evidence in plan["profile_evidence"].get(dimension, [])
            if evidence["id"] in citable_ids
        })[:20]
        plan["supplier_claims_used"] = supplier_claims
        plan["profile_refs"] = profile_refs
        plan["price_evidence_reply"] = price_evidence_reply(case, offer["supplier_id"], events, self.package)
        plan["source_document_reply"] = source_document_reply(
            events, self.archive_records.get(offer["supplier_id"], [])
        )
        return {
            "offer": offer,
            "context": context,
            "plan": plan,
            "generated": generated,
            "packages": packages,
            "best_cost": packages[0]["evaluation"]["buyer"]["total_cost"],
        }

    def _counter(self, candidate, case):
        offer = candidate["offer"]
        packages = candidate["packages"]
        message = {
            "subject": latest_context_subject(offer["supplier_id"], candidate["context"]),
            "body": self._body(candidate["context"], candidate["plan"], packages, offer, case),
            "term_sheets": [{"terms": package["terms"]} for package in packages],
        }
        if candidate["plan"]["profile_refs"]:
            message["refs"] = candidate["plan"]["profile_refs"]
        if argument := candidate["plan"].get("price_evidence_reply"):
            if argument["refs"]:
                message["refs"] = sorted(set(message.get("refs", []) + argument["refs"]))
        if document_reply := candidate["plan"].get("source_document_reply"):
            message["refs"] = sorted(set(message.get("refs", []) + document_reply["refs"]))
            message["attachments"] = document_reply["attachments"]
        self.decision_history.append({
            "supplier_id": offer["supplier_id"],
            "offer_id": offer["offer_id"],
            "action": "counter_packages",
            "supplier_standard_terms": deepcopy(offer["standard"]),
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
            "claim_adjustment_cap_pct": self.claim_adjustment_cap_pct,
            "supplier_claims_cited": candidate["plan"]["supplier_claims_used"],
            "trade_hypotheses": candidate["plan"]["trade_hypotheses"],
            "term_restoration": candidate["plan"].get("term_restoration", False),
            "response_trade": candidate["plan"].get("response_trade", False),
            "supplier_alternative": candidate["plan"].get("supplier_alternative", False),
            "offer_restoration": candidate["plan"].get("offer_restoration", False),
            "price_evidence_reply": candidate["plan"].get("price_evidence_reply"),
            "generated": candidate["generated"],
            "selection_audit": candidate["plan"]["selection_audit"],
            "progress_credit": candidate["plan"].get("progress_credit"),
            "response_signal": packages[0].get("response_signal"),
            "opening_goal": offer.get("opening_goal"),
            "minimum_rounds": self.minimum_rounds,
            "message": message,
        })
        return {"supplier_id": offer["supplier_id"], "message": message}

    def _accept(self, offer, reason="best valid standing offer after available negotiation moves"):
        message = {"action": {"type": "accept", "term_sheet_id": offer["offer_id"]}}
        self.decision_history.append({
            "supplier_id": offer["supplier_id"],
            "offer_id": offer["offer_id"],
            "action": "accept",
            "reason": reason,
            "accepted_terms": deepcopy(offer["closed_terms"]),
            "predicted_cost_breakdown": deepcopy(offer["evaluation"]["buyer"]["cost_breakdown"]),
            "opening_goal": offer.get("opening_goal"),
            "supplier_standard_terms": deepcopy(offer["standard"]),
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
        body = "Before we send another counter, could you identify the term preventing approval?"
        if not offer["cost_breakdown_refused"] and not offer.get("cost_breakdown_requested"):
            body += " If available, please share the supporting cost breakdown."
        message = {
            "subject": latest_context_subject(offer["supplier_id"], None),
            "body": body,
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

    def _clarify(self, offer):
        lead_time = offer["closed_terms"]["lead_time_days"]
        message = {
            "subject": latest_context_subject(offer["supplier_id"], None),
            "body": (
                "Your message and standing term sheet differ on lead time: the sheet lists "
                f"{lead_time} days, but your message says that is not feasible. "
                "Please reconcile the lead time and send one matching price, volume, and delivery package."
            ),
        }
        self.decision_history.append({
            "supplier_id": offer["supplier_id"],
            "offer_id": offer["offer_id"],
            "action": "clarify_terms",
            "response_conflict": offer["response_conflict"],
            "standing_total_cost": offer["standing_cost"],
            "reservation_cost": offer["reservation_cost"],
            "message": message,
        })
        return {"supplier_id": offer["supplier_id"], "message": message}

    def _clarify_trade(self, offer, fields):
        names = ", ".join(field.replace("_", " ") for field in fields)
        message = {
            "subject": latest_context_subject(offer["supplier_id"], None),
            "body": (
                f"You invited a change to {names}. Which concrete values and matching price "
                "could you approve? Please send one complete term sheet so we can evaluate it."
                + (" For indexation, please specify the series, material share, base month, deadband "
                   "and matching unit price; no clause is agreed by this question."
                   if "index_clause" in fields else "")
                + (" For quality, please specify a numeric guaranteed ppm ceiling and matching price."
                   if "ppm_commitment" in fields else "")
            ),
        }
        self.decision_history.append({
            "supplier_id": offer["supplier_id"],
            "offer_id": offer["offer_id"],
            "action": "clarify_trade",
            "invited_terms": fields,
            "standing_total_cost": offer["standing_cost"],
            "reservation_cost": offer["reservation_cost"],
            "message": message,
        })
        return {"supplier_id": offer["supplier_id"], "message": message}

    def _recover(self, supplier_id, issue, offer):
        message = recovery_message(issue)
        self.decision_history.append({
            "supplier_id": supplier_id, "action": "clarify_recovery", "issue": issue,
            "offer_id": offer["offer_id"] if offer else None,
            "standing_total_cost": offer["standing_cost"] if offer else None,
            "reservation_cost": offer["reservation_cost"] if offer else None,
            "validation_warnings": offer["evaluation"]["warnings"] if offer else [],
            "message": message,
        })
        return {"supplier_id": supplier_id, "message": message}

    def _answer_requested_evidence(self, decision, case, threads):
        """A supplier question still deserves an answer when our move is a question."""
        sid, message = decision["supplier_id"], decision["message"]
        events = threads[sid]
        replies = [price_evidence_reply(case, sid, events, self.package),
                   source_document_reply(events, self.archive_records.get(sid, []))]
        for reply in filter(None, replies):
            # Retain full explanations; do not truncate away a qualifier or ref.
            if len(message.get("body", "")) + len(reply["text"]) + 1 > 8000:
                continue
            message["body"] += " " + reply["text"]
            message["refs"] = list(dict.fromkeys(message.get("refs", []) + reply["refs"]))[:20]
            if reply.get("attachments"):
                message["attachments"] = reply["attachments"]
        self.decision_history[-1]["message"] = deepcopy(message)
        return decision

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
            "validation_warnings": offer["evaluation"]["warnings"] if offer else [],
            "missing_supplier_terms": offer["missing_supplier_terms"] if offer else [],
            "response_conflict": offer["response_conflict"] if offer else None,
            "message": message,
        })
        return {"supplier_id": supplier_id, "message": message}

    def _context(self, events, supplier_id, part_id):
        bundle = build_thread_supplier_context(
            events, supplier_id, part_id,
            supplemental_records=self.archive_records.get(supplier_id, []),
        )
        return context_for_part(bundle, part_id)

    @staticmethod
    def _body(context, plan, packages, offer, case):
        used_trades = []
        standing_terms = offer["evaluation"]["final_terms"]
        for index, package in enumerate(packages, 1):
            for hypothesis in plan["trade_hypotheses"]:
                changed = {**hypothesis["buyer_gives"], **hypothesis.get("supplier_gives", {})}
                if all(package["terms"].get(field) == value
                       and standing_terms.get(field) != value
                       for field, value in changed.items()):
                    used_trades.append((index, hypothesis))
        options = "\n".join(
            f"Option {index}: {_describe_terms(package['terms'], case)}"
            for index, package in enumerate(packages, 1)
        )
        claim_sentences = [
            _claim_citation(claim) for claim in plan.get("supplier_claims_used", [])[:3]
        ]
        trade_sentences = []
        for index, hypothesis in used_trades:
            sources = list(dict.fromkeys(
                item["source"] for item in hypothesis["evidence"]
                if item.get("source") and (
                    not _looks_like_arena_id(item["source"]) or item["source"] in plan.get("profile_refs", [])
                )
            ))
            source_note = f" (source: {', '.join(sources[:2])})" if sources else ""
            give_get = {
                "cash_sensitive": "offers earlier payment in exchange for the listed price below your quote",
                "capacity_sensitive": "offers a larger commitment in exchange for the listed price below your quote",
                "quality_sensitive": "pairs your stated quality guarantee with a less aggressive price ask",
            }[hypothesis["profile_dimension"]]
            trade_sentences.append(
                f"Option {index} {give_get}{source_note}."
            )
        return (
            "Thank you for the quotation. Please review our complete conditional proposal:\n"
            + options + ".\nPlease confirm this package or identify the blocking term."
            + (" " + " ".join(claim_sentences) if claim_sentences else "")
            + (" " + " ".join(dict.fromkeys(trade_sentences)) if trade_sentences else "")
            + (f" {REPAIR_MARKER}, we can offer the higher price shown. "
               "These are proposals for your approval, not assumed commitments."
               if plan.get("term_restoration") else "")
            + (f" {RESPONSE_TRADE_MARKER} in exchange for the changed term listed above. "
               "Where an index clause is listed, we retain its series, material share and base month "
               "while proposing the stated deadband. Please confirm a complete option you can approve."
               if plan.get("response_trade") else "")
            + (f" The proposed payment period of {packages[0]['terms']['payment_days']} days replaces "
               f"the quoted {offer['closed_terms'].get('payment_days')} days, together with the proposed price. "
               "Please evaluate them together; we are not retaining a prior early-payment arrangement."
               if packages[0]["terms"].get("payment_days", 0) > offer["closed_terms"].get("payment_days", 0)
               else "")
            + (f" {ALTERNATIVE_MARKER}: the package above repeats its exact terms. "
               "Please confirm it in your standing term sheet so we can close on that package."
               if plan.get("supplier_alternative") else "")
            + (f" {RESTORE_OFFER_MARKER}? The proposal repeats its negotiable terms, "
               "rather than the revised payment/price combination. Please confirm a new standing "
               "offer; we do not assume the earlier quote is still available."
               if plan.get("offer_restoration") else "")
            + (" " + plan["price_evidence_reply"]["text"] if plan.get("price_evidence_reply") else "")
            + (" " + plan["source_document_reply"]["text"] if plan.get("source_document_reply") else "")
            + (" If available, please share the supporting cost breakdown."
               if not offer["cost_breakdown_refused"] and not offer.get("cost_breakdown_requested") else "")
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
    conflicted = False
    for item in context.get("supplier_claims", []):
        if not isinstance(item, dict):
            continue
        data = item.get("data") or {}
        if not item.get("source") or item.get("conflicts") or data.get("conflicts"):
            continue
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
        key = series.strip().upper()
        claim = {
            "series": series.strip().upper(),
            "index_change_pct": change,
            "cost_share_pct": share,
            "impact_pct": change * share / 100,
            "claim_text": _safe_text(data.get("claim_text"), 240),
            "source": _safe_text(item.get("source"), 180),
        }
        previous = by_series.get(key)
        if previous and (previous["index_change_pct"], previous["cost_share_pct"]) != (change, share):
            conflicted = True
        by_series.setdefault(key, claim)
    claims = list(by_series.values())
    if conflicted or sum(item["cost_share_pct"] for item in claims) > 100:
        return 0.0, []
    return sum(item["impact_pct"] for item in claims), claims


def _claim_citation(claim):
    if claim.get("claim_text"):
        assertion = claim["claim_text"]
    else:
        assertion = (
            f"{claim['series']} moved {claim['index_change_pct']:+g}% and is "
            f"{claim['cost_share_pct']:g}% of your cost"
        )
    return f"Your email states: {assertion}. These are your supplied figures, not independently verified costs."


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
    return reservation_cost(case, evaluation)


def _last_buyer_message(events):
    return next((event for event in reversed(events) if event.get("from") == "buyer"), None)


def _last_buyer_sheets(events):
    for event in reversed(events):
        if event.get("from") == "buyer" and event.get("term_sheets"):
            return event["term_sheets"]
    return []


def _terms_key(terms):
    return json.dumps(terms or {}, sort_keys=True, default=str, separators=(",", ":"))


def _advance_price_ladder(case, plan, events, offer, previous_sheets):
    """Share bounded whole-package progress; do not reward a worse valid deal.

    Discounts from each new standing price would make a fresh 5/3/1% ladder
    *more* demanding after the supplier concedes. Anchor instead to our last
    sent prices and move each ask halfway toward the supplier's price movement.
    """
    previous_prices = sorted({
        round(float(sheet["terms"]["unit_price"]), 2)
        for sheet in previous_sheets
        if isinstance(sheet.get("terms", {}).get("unit_price"), (int, float))
    })
    supplier_terms = [
        event["term_sheets"][0].get("terms") or {}
        for event in events if event.get("from") not in {"buyer", "arena"} and event.get("term_sheets")
    ]
    if not previous_prices or len(supplier_terms) < 2:
        return
    current = float(offer["terms"]["unit_price"])
    before = supplier_terms[-2].get("unit_price")
    if not isinstance(before, (int, float)) or isinstance(before, bool):
        return
    prior_index = [i for i, event in enumerate(events)
                   if event.get("from") not in {"buyer", "arena"} and event.get("term_sheets")][-2]
    prior_standard = standard_terms([event for event in events[:prior_index + 1]
                                    if event.get("from") not in {"buyer", "arena"}])
    try:
        economics = offer.get("supplier_economics")
        prior = evaluate_deal(
            case, _effective_standing_terms(case, supplier_terms[-2], prior_standard),
            prior_standard, economics,
        )
        current_terms = {field: offer["closed_terms"][field] for field in case["negotiable"]}
        higher = evaluate_deal(
            case, {**current_terms, "unit_price": current + 1}, offer["standard"], economics
        )
        slope = higher["buyer"]["total_cost"] - offer["standing_cost"]
        benefit = prior["buyer"]["total_cost"] - offer["standing_cost"]
        repaired = not prior["buyer"]["must_haves_ok"] and offer["acceptable"]
        concession = max(0.0, benefit / (2 * slope)) if slope > 0 else 0.0
        plan["progress_credit"] = {"kind": "feasibility_repair" if repaired else "total_cost",
                                   "buyer_cost_improvement": round(benefit, 2)}
    except (KeyError, TypeError, ValueError):
        concession, repaired = 0.0, False
    old_prices = plan["candidate_unit_prices"]
    old_constraints = plan["term_constraints_by_price"]
    old_rationales = plan["rationales_by_price"]
    prices, constraints, rationales = [], {}, {}
    for index, previous in enumerate(previous_prices):
        if previous >= current - 0.005:
            continue  # The standing sheet already beats this prior ask.
        gap_share = max(0, (current - previous) / 2)
        credit = gap_share if repaired else min(concession, gap_share)
        price = round(min(previous + credit, current - 0.01), 2)
        if price in constraints:
            continue
        template = old_prices[min(index, len(old_prices) - 1)]
        prices.append(price)
        constraints[price] = dict(old_constraints[template])
        rationales[price] = ["a bounded reciprocal move from our previous ask"] + [
            reason for reason in old_rationales[template]
            if "below the standing unit price" not in reason
        ]
    plan["candidate_unit_prices"] = prices
    plan["term_constraints_by_price"] = constraints
    plan["rationales_by_price"] = rationales


_TRADE_VERBS = r"(?:adjust\w*|chang\w*|extend\w*|extens\w*|increas\w*|revisit\w*|revis\w*|flexib\w*|consider\w*)"
_INVITED_TERM_LABELS = {
    "contract_months": r"contract\s+(?:duration|term|length)",
    "volume_per_year": r"(?:annual\s+volume|volume\s+per\s+year)",
    "payment_days": r"payment\s+(?:terms|days|period)",
    "index_clause": r"(?:index\s+clause|indexation|Preisgleitklausel)",
    "ppm_commitment": r"(?:quality\s+(?:guarantee|commitment)|ppm\s+(?:ceiling|commitment))",
}


def _supplier_invited_terms(message):
    body = message.get("body")
    if not isinstance(body, str):
        return []
    invited = []
    for field, label in _INVITED_TERM_LABELS.items():
        pattern = rf"(?:{_TRADE_VERBS}).{{0,70}}(?:{label})|(?:{label}).{{0,70}}(?:{_TRADE_VERBS})"
        sentences = [sentence for sentence in supplier_sentences(message)
                     if not re.search(r"\b(?:cannot|can't|will not|do not|not feasible|not possible)\b",
                                      sentence, re.I)]
        # Optional clauses must be supplier invitations, not copied buyer wishes.
        if field in {"index_clause", "ppm_commitment"}:
            pattern = rf"\b(?:offer|explore|require\w*|implement\w*|consider\w*).{{0,90}}(?:{label})"
        else:
            sentences = [sentence for sentence in sentences
                         if re.search(r"\b(?:can|could|would|willing|prepared|please|which|should you)\b",
                                      sentence, re.I)]
        if any(re.search(pattern, sentence, re.I) for sentence in sentences):
            invited.append(field)
    return invited


def _effective_standing_terms(case, terms, standard):
    """Complete missing negotiable supplier terms from its quote PDF."""
    negotiable = case.get("negotiable", [])
    supplier_defaults = {field: standard[field] for field in negotiable if field in standard}
    return {**supplier_defaults, **terms}


def _compatible_quote_basis(events):
    """The Arena model is EUR per item; never guess a conversion from a PDF."""
    for event in reversed(events):
        quotes = [att for att in event.get("attachments", [])
                  if str(att.get("name", "")).lower().startswith("quote")]
        if not quotes:
            continue
        for att in quotes:
            if any(att.get(key) for key in ("parse_error", "pdf_parse_error", "parse_warnings")):
                return False
            if not att.get("text"):
                continue  # Protocol sheets use the Arena EUR/item convention.
            for section in quote_terms(att["text"]).values():
                if section.get("currency") not in (None, "EUR"):
                    return False
                if section.get("price_unit") not in (None, "each", "1 each"):
                    return False
        return True
    return True


def _response_conflict(message, terms):
    """Flag an explicit rejection of the lead time in the standing sheet."""
    lead_time = terms.get("lead_time_days")
    if isinstance(lead_time, bool) or not isinstance(lead_time, (int, float)):
        return None
    body = message.get("body") or ""
    if not isinstance(body, str):
        return None
    days = re.escape(f"{lead_time:g}")
    rejection = r"(?:not feasible|not possible|impossible|cannot be met|can't be met)"
    patterns = (
        rf"\blead[\s-]*time(?:\s+of)?\s+{days}\s*days?\b.{{0,45}}\b{rejection}\b",
        rf"\b{days}[\s-]*day\s+lead[\s-]*time\b.{{0,45}}\b{rejection}\b",
    )
    if any(re.search(pattern, body, re.IGNORECASE | re.DOTALL) for pattern in patterns):
        return f"supplier rejected the standing {lead_time:g}-day lead time in its message"
    return None


def _thread_response_conflict(events, terms):
    """Keep an explicit contradiction until the supplier resolves it in writing."""
    conflict = None
    for event in events:
        if event.get("from") == "buyer":
            continue
        if rejection := _response_conflict(event, terms):
            conflict = rejection
        elif conflict and _lead_time_confirmed(event, terms):
            conflict = None
    return conflict


def _lead_time_confirmed(message, terms):
    lead_time = terms.get("lead_time_days")
    if isinstance(lead_time, bool) or not isinstance(lead_time, (int, float)):
        return False
    body = message.get("body") or ""
    if not isinstance(body, str):
        return False
    days = re.escape(f"{lead_time:g}")
    patterns = (
        rf"\b(?:we|i)\s+confirm\b.{{0,50}}\blead[\s-]*time(?:\s+of)?\s+{days}\s*days?\b",
        rf"\blead[\s-]*time(?:\s+of)?\s+{days}\s*days?\b.{{0,15}}\bis feasible\b",
        rf"\b{days}[\s-]*day\s+lead[\s-]*time\b.{{0,15}}\bis feasible\b",
    )
    return any(re.search(pattern, body, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _asked_to_reconcile(buyer_message):
    return bool(
        buyer_message and "please reconcile the lead time" in str(buyer_message.get("body", "")).lower()
    )


def _cost_breakdown_refused(events):
    for event in events:
        if event.get("from") == "buyer":
            continue
        body = event.get("body")
        if not isinstance(body, str):
            continue
        text = body.lower()
        about_costs = bool(re.search(r"\bcosts?\b|calculation|material", text))
        refused = (
            bool(re.search(r"\b(?:do not|don't|cannot|can't|won't|will not)\s+(?:\w+\s+){0,3}"
                           r"(?:disclose|share|provide)\b", text))
            or "stays internal" in text
            or "remains internal" in text
            or "figures stay with us" in text
            or bool(re.search(r"\bmore detail (?:we|i) (?:do not|don't|cannot|can't) share\b", text))
        )
        if about_costs and refused:
            return True
    return False


def _describe_terms(terms, case):
    descriptions = []
    for field in case.get("negotiable", []):
        if field not in terms:
            continue
        value = terms[field]
        if field == "unit_price" and isinstance(value, (int, float)) and not isinstance(value, bool):
            descriptions.append(f"unit price {value:.2f} per unit")
        elif field == "payment_days":
            descriptions.append(f"payment in {value} days")
        elif field == "lead_time_days":
            descriptions.append(f"{value}-day lead time")
        elif field == "contract_months":
            descriptions.append(f"{value}-month contract")
        elif field == "volume_per_year":
            descriptions.append(f"{value} units per year")
        elif field == "index_clause" and value is None:
            descriptions.append("no index adjustment")
        elif field == "incoterm":
            descriptions.append(f"{value} delivery")
        else:
            descriptions.append(f"{field.replace('_', ' ')} {value}")
    return ", ".join(descriptions)


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
            case, effective_previous_terms, current_offer["standard"], current_offer.get("supplier_economics")
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
