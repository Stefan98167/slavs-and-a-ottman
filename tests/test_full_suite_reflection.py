from copy import deepcopy

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent, _supplier_invited_terms
from arena_kit.play import RemoteTable, current_thread_events, play, standing
from negotiator.buyer_arguments import source_document_reply
from negotiator.offer_restoration import RESTORE_OFFER_MARKER, restore_prior_offer
from negotiator.response_trades import RESPONSE_TRADE_MARKER


@pytest.mark.parametrize("price", [12, 42, 307])
def test_restore_better_prior_quote_after_unhelpful_experiment_but_never_accept_old_id(price):
    case = deepcopy(CASE)
    case["buyer"]["fallback_unit_price"] = price * 2
    old = supplier("open", price, payment_days=45)
    current = supplier("open", price * 1.03, payment_days=90)
    events = [old, {"from": "buyer", "body": RESPONSE_TRADE_MARKER,
                    "term_sheets": [{"terms": {"unit_price": round(price * 1.005, 2), "payment_days": 90}}]}, current]
    agent = UnifiedAgent()
    offer = agent._standing_offers(case, {"sup:A": events})[0]
    restored = restore_prior_offer(case, offer, events)
    assert restored["terms"] == old["term_sheets"][0]["terms"]
    result = agent.decide(case, {"sup:A": events})
    assert result["message"].get("action") is None
    assert RESTORE_OFFER_MARKER in result["message"]["body"]
    assert result["message"]["term_sheets"] == [{"terms": restored["terms"]}]
    assert not restore_prior_offer(case, offer, [*events, {"from": "buyer", **result["message"]}, current])
    current["status"] = "final_offer"
    assert agent.decide(case, {"sup:A": events})["message"]["action"]["term_sheet_id"] == current[
        "term_sheets"][0]["term_sheet_id"]


def test_restoration_requires_real_quote_complete_terms_and_current_constraints():
    old, current = supplier("open", 40, payment_days=30), supplier("open", 42, payment_days=90)
    events = [old, {"from": "buyer", "body": RESPONSE_TRADE_MARKER}, current]
    agent = UnifiedAgent()
    case = deepcopy(CASE)
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 60}]
    offer = agent._standing_offers(case, {"sup:A": events})[0]
    assert restore_prior_offer(case, offer, events) is None
    case["buyer"]["must_haves"] = []
    del old["term_sheets"][0]["terms"]["payment_days"]
    assert restore_prior_offer(case, offer, events) is None
    old["term_sheets"][0]["terms"]["payment_days"] = 30
    old["from"] = "buyer"
    assert restore_prior_offer(case, offer, events) is None


@pytest.mark.parametrize("body", [
    "We need 33.00 to cover the extended 90-day payment terms.",
    "We cannot extend payment terms.",
    'You wrote: "We can extend payment terms."',
    "We adjusted payment terms. Our current offer is 42.",
])
def test_current_terms_negative_and_quoted_text_are_not_new_invitations(body):
    assert _supplier_invited_terms(supplier("open", 42, body=body)) == []


@pytest.mark.parametrize("body", [
    "We can extend payment terms for a higher price.",
    "Extension of payment terms would require a higher price.",
])
def test_concrete_prospective_payment_exchange_is_retained(body):
    assert _supplier_invited_terms(supplier("open", 42, body=body)) == ["payment_days"]


def test_clarification_also_answers_real_evidence_request_without_inventing_data():
    case = deepcopy(CASE)
    case["negotiable"].append("index_clause")
    case["term_options"]["index_clause"] = [None]
    opening = supplier("open", 42)
    opening["term_sheets"][0]["terms"]["index_clause"] = None
    agent = UnifiedAgent()
    first = agent.decide(case, {"sup:A": [opening]})
    response = deepcopy(opening)
    response["body"] = "We can offer an index clause. Which figures is that based on? Please send us the data."
    result = agent.decide(case, {"sup:A": [opening, {"from": "buyer", **first["message"]}, response]})
    assert agent.decision_history[-1]["action"] == "clarify_trade"
    assert "not a claim about your costs" in result["message"]["body"]
    assert not result["message"]["refs"]


@pytest.mark.parametrize("body", [
    "Please do not send the document.", 'You said: "Please send the document."',
    "Thank you for providing the source document.",
])
def test_unrequested_document_is_not_disclosed(body):
    events = [{"from": "buyer", "refs": ["doc:A"]}, supplier("open", 42, body=body)]
    records = [{"Information": {"id": "doc:A", "archive_source": True, "document_text": "Source"}}]
    assert source_document_reply(events, records) is None


def test_timeout_snapshot_uses_matching_current_terms_never_old_terms_under_new_id():
    thread = {"messages": [supplier("open", 42)], "offer_id": "offer:new", "status": "open",
              "timeouts": [{"offer_id": "offer:new", "terms": {"unit_price": 43, "payment_days": 30}}]}
    assert standing(current_thread_events(thread)) == ("offer:new", {"unit_price": 43, "payment_days": 30})
    thread["timeouts"] = []
    assert standing(current_thread_events(thread)) == (None, {})
    thread["status"] = "walked_away"
    assert current_thread_events(thread)[-1]["status"] == "walked_away"


def test_runner_revalidates_after_refresh_and_cannot_accept_stale_or_over_budget_offer():
    class Table:
        def __init__(self, updated):
            self.updated = updated

        def open(self, case_id):
            return CASE, {"sup:A": [supplier("final_offer", 40)]}

        def refresh_threads(self, previous):
            assert standing(previous["sup:A"])[0] == "offer:40"
            return {"sup:A": [supplier("final_offer", self.updated)]}

        def close(self, sid, msg):
            return msg["action"]

    agent = UnifiedAgent()
    assert play(Table(41), CASE["case_id"], agent) == {"type": "accept", "term_sheet_id": "offer:41"}
    assert agent.decision_history[-2]["action"] == "superseded_close"
    assert not agent.decision_history[-2]["sent"]
    assert play(Table(100), CASE["case_id"], UnifiedAgent()) == {"type": "walk_away"}


def test_remote_refresh_preserves_parsed_quote_and_reconciles_timeout():
    opening = supplier("open", 42)
    opening["attachments"] = [{"attachment_id": "att:1", "name": "quote.pdf",
                               "text": "Our standard terms\nPayment terms (days net) 30"}]
    raw = deepcopy(opening)
    del raw["attachments"][0]["text"]

    class Client:
        def session(self, sid):
            return {"status": "open", "threads": {"sup:A": {}}}

        def thread(self, session, supplier_id):
            return {"messages": [raw], "status": "open", "offer_id": "offer:new",
                    "timeouts": [{"offer_id": "offer:new", "terms": {"unit_price": 41}}]}

        def attachment(self, *args):
            raise AssertionError("already parsed attachment should not be downloaded again")

    table = RemoteTable(Client(), CASE)
    table.session_id = "session:test"
    refreshed = table.refresh_threads({"sup:A": [opening]})
    assert refreshed["sup:A"][0]["attachments"][0]["text"] == opening["attachments"][0]["text"]
    assert standing(refreshed["sup:A"])[0] == "offer:new"
    assert UnifiedAgent().close(CASE, refreshed)["message"]["action"]["term_sheet_id"] == "offer:new"
