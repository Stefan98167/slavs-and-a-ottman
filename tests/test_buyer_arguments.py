import base64
from copy import deepcopy

import pytest
from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent
from negotiator.buyer_arguments import price_evidence_reply, source_document_reply


def quote(**overrides):
    return {"supplier": "sup:A", "part": "part:T1", "unit_price": 38.5,
            "price_unit": 1, "currency": "EUR", "date": "2026-01-01", **overrides}


def request():
    return [supplier("open", 41, body="Please provide the data supporting your target price.")]


def test_case_referenced_quote_is_not_a_floor_or_profile():
    case = {**CASE, "refs": ["quote:old"], "facts": {"quote:old": quote()}}
    out = price_evidence_reply(case, "sup:A", request())
    assert out["refs"] == ["quote:old"]
    assert "EUR 38.5 per one unit" in out["text"]
    assert "not your cost floor" in out["text"]
    decision = UnifiedAgent().decide(case, {"sup:A": request()})
    assert decision["message"]["refs"] == ["quote:old"]
    assert {s["terms"]["payment_days"] for s in decision["message"]["term_sheets"]} == {30}


@pytest.mark.parametrize("change", [
    {"supplier": None}, {"part": "part:other"}, {"currency": None}, {"currency": "USD"},
    {"price_unit": 100}, {"price_unit": True}, {"date": "2099-01-01"}, {"date": None},
    {"unit_price": float("nan")}, {"unit_price": True},
])
def test_unusable_quote_is_not_cited(change):
    case = {**CASE, "refs": ["quote:bad"], "facts": {"quote:bad": quote(**change)}}
    out = price_evidence_reply(case, "sup:A", request())
    assert not out["refs"]
    assert "not a claim about your costs" in out["text"]


def test_latest_quote_and_case_cutoff_and_no_repeated_fact():
    case = deepcopy(CASE)
    case.update(as_of="2026-09-30", refs=["quote:first", "quote:future"],
                facts={"quote:first": quote(), "quote:future": quote(date="2026-10-01")})
    assert price_evidence_reply(case, "sup:A", request())["refs"] == ["quote:first"]
    events = [{"from": "buyer", "refs": ["quote:first"]}, *request()]
    assert price_evidence_reply(case, "sup:A", events)["refs"] == []
    assert price_evidence_reply(case, "sup:A", [supplier("open", 42)]) is None


def test_opening_price_argument_uses_two_recent_distinct_lower_same_supplier_orders():
    case = {**CASE, "as_of": "2026-09-30", "facts": {
        "po:old": quote(unit_price=37.0, date="2026-01-01"),
        "po:new": quote(unit_price=38.0, date="2026-08-01"),
        "po:duplicate": quote(unit_price=39.0, date="2026-08-02"),
        "po:other-supplier": quote(supplier="sup:B", unit_price=20.0),
        "po:other-part": quote(part="part:other", unit_price=20.0),
    }}
    events = [supplier("open", 41.0)]

    out = price_evidence_reply(case, "sup:A", events, proactive=True)

    assert out["kind"] == "purchase_order_history"
    assert out["refs"] == ["po:duplicate", "po:new"]
    assert "EUR 39 per unit on 2026-08-02" in out["text"]
    assert "not a claim about your costs" in out["text"]


def test_opening_price_argument_skips_weak_or_non_comparable_history():
    events = [supplier("open", 41.0)]
    one_order = {**CASE, "facts": {"po:one": quote(unit_price=30.0)}}
    too_close = {**CASE, "facts": {
        "po:first": quote(unit_price=40.8), "po:second": quote(unit_price=40.9, date="2026-02-01")}}
    assert price_evidence_reply(one_order, "sup:A", events, proactive=True) is None
    assert price_evidence_reply(too_close, "sup:A", events, proactive=True) is None
    assert price_evidence_reply(CASE, "sup:A", events, proactive=True) is None


def test_unified_cites_qualifying_purchase_history_in_first_counter_only(monkeypatch):
    monkeypatch.setenv("UNIFIED_PROACTIVE_PRICE_EVIDENCE", "1")
    case = {**CASE, "facts": {
        "po:first": quote(unit_price=37.0),
        "po:second": quote(unit_price=38.0, date="2026-02-01"),
    }}
    agent = UnifiedAgent()
    first = agent.decide(case, {"sup:A": [supplier("open", 41.0)]})
    assert set(first["message"]["refs"]) == {"po:first", "po:second"}
    assert "recent purchase orders" in first["message"]["body"]

    later_events = [supplier("open", 41.0), {**first["message"], "from": "buyer"},
                    supplier("open", 40.0)]
    second = agent.decide(case, {"sup:A": later_events})
    assert not set(second["message"].get("refs", [])) & {"po:first", "po:second"}


def test_unified_proactive_price_evidence_is_off_by_default(monkeypatch):
    monkeypatch.delenv("UNIFIED_PROACTIVE_PRICE_EVIDENCE", raising=False)
    case = {**CASE, "facts": {
        "po:first": quote(unit_price=37.0),
        "po:second": quote(unit_price=38.0, date="2026-02-01"),
    }}
    decision = UnifiedAgent().decide(case, {"sup:A": [supplier("open", 41.0)]})
    assert not decision["message"].get("refs")
    assert "recent purchase orders" not in decision["message"]["body"]


def test_partial_material_share_disclosure_is_still_a_refusal_of_more_details():
    agent = UnifiedAgent()
    out = agent.decide(CASE, {"sup:A": [supplier("open", 42, body=(
        "Material accounts for about 30 % of our cost; more detail we do not share."
    ))]})
    assert "please share the supporting cost breakdown" not in out["message"]["body"]


def test_document_request_shares_only_previously_cited_verified_sources_once():
    events = [{"from": "buyer", "refs": ["doc:verified", "doc:untrusted"]},
              supplier("open", 41, body="Please share the document you referenced.")]
    records = [{"Information": {"id": ref, "document_text": "We require earlier payment.",
                                "archive_source": trusted}}
               for ref, trusted in [("doc:verified", True), ("doc:untrusted", False), ("doc:uncited", True)]]
    reply = source_document_reply(events, records)
    assert reply["refs"] == ["doc:verified"]
    assert base64.b64decode(reply["attachments"][0]["content_b64"]).decode() == "We require earlier payment."
    events.extend([{**reply, "from": "buyer"}, events[-1]])
    assert source_document_reply(events, records) is None


def test_document_request_integrates_with_verified_supplier_archive(tmp_path):
    from test_case_evidence import document, package

    data = package(tmp_path, {"doc:cash": document()})
    agent = UnifiedAgent(package=data)
    events = [supplier("open", 42)]
    first = agent.decide(CASE, {"sup:A": events})
    events += [{**first["message"], "from": "buyer"},
               supplier("open", 41, body="Please share the document you referenced.")]
    out = agent.decide(CASE, {"sup:A": events})
    assert out["message"]["attachments"][0]["type"] == "md"
    assert "doc:cash" in out["message"]["refs"]


def test_arbitrary_old_quote_is_not_a_grader_supported_quote_argument():
    case = {**CASE, "facts": {"quote:old": quote()}}
    assert price_evidence_reply(case, "sup:A", request())["refs"] == []


def test_two_same_part_orders_use_documented_order_history_argument():
    case = {**CASE, "facts": {"po:first": quote(), "po:second": quote(date="2026-02-01"),
                              "po:other": quote(supplier="sup:B"), "po:wrong": quote(part="part:wrong")}}
    out = price_evidence_reply(case, "sup:A", request())
    assert set(out["refs"]) == {"po:first", "po:second"}
    assert out["kind"] == "purchase_order_history"
    events = [{"from": "buyer", "refs": out["refs"]}, *request()]
    assert price_evidence_reply(case, "sup:A", events)["refs"] == []
    del case["facts"]["po:second"]
    assert price_evidence_reply(case, "sup:A", request())["refs"] == []


@pytest.mark.parametrize("body", [
    "We checked the price history data you cited; it holds, but it does not change our calculation.",
    "We acknowledge the evidence supporting your target price.",
    "Please do not send the data supporting your target price.",
    'You wrote: "Please provide data supporting your target price."',
])
def test_acknowledgement_refusal_and_quotation_do_not_trigger_more_evidence_disclosure(body):
    case = {**CASE, "facts": {"po:first": quote(), "po:second": quote(date="2026-02-01")}}
    assert price_evidence_reply(case, "sup:A", [supplier("open", 41, body=body)]) is None


def test_a_real_new_request_still_works_after_acknowledging_old_evidence():
    body = ("We checked the price history data you cited. "
            "Please provide independent data supporting your target price.")
    case = {**CASE, "facts": {"po:first": quote(), "po:second": quote(date="2026-02-01")}}
    assert price_evidence_reply(case, "sup:A", [supplier("open", 41, body=body)])["kind"] == "purchase_order_history"


@pytest.mark.parametrize("body", [
    "Please provide the data supporting your target price, as the referenced document was not included.",
    "The letter you mentioned is missing.",
    "Your source document was not attached.",
])
def test_indirect_source_requests_are_recognized(body):
    events = [{"from": "buyer", "refs": ["doc:source"]}, supplier("open", 41, body=body)]
    records = [{"Information": {"id": "doc:source", "document_text": "We require earlier payment.",
                                "archive_source": True}}]
    assert source_document_reply(events, records)["refs"] == ["doc:source"]
