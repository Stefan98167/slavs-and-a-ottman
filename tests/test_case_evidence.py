import json

from test_kit import CASE
from test_unified import supplier

from arena_kit.agents.unified import UnifiedAgent
from arena_kit.data import DataPackage
from negotiator.case_evidence import CaseSupplierEvidence


def package(tmp_path, records):
    (tmp_path / "facts.json").write_text(json.dumps({
        "sup:A": {"name": "Supplier A"}, "sup:B": {"name": "Supplier B"}, **records,
    }))
    return DataPackage(tmp_path)


def document(**kwargs):
    return {"supplier": "sup:A", "author": "Supplier A", "type": "email",
            "date": "2026-01-01", "body": "We require earlier payment.", **kwargs}


def test_archive_rejects_buyer_other_supplier_other_part_and_future_evidence(tmp_path):
    data = package(tmp_path, {
        "doc:valid": document(),
        "doc:buyer": document(author="Hollerau Pumpenwerke, Purchasing"),
        "doc:other-part": document(part_ids="part:unrelated"),
        "doc:forged": document(supplier="sup:B"),
        "doc:future": document(date="2099-01-01"),
        "doc:no-author": document(author=""),
    })
    records, warnings = CaseSupplierEvidence(data).prepare(CASE)
    assert [r["Information"]["id"] for r in records["sup:A"]] == ["doc:valid"]
    assert records["sup:B"] == []
    assert warnings == []


def test_unified_consumes_archive_and_cites_the_actual_document(tmp_path):
    data = package(tmp_path, {"doc:cash": document()})
    agent = UnifiedAgent(package=data)
    out = agent.decide(CASE, {"sup:A": [supplier("open", 42)]})
    assert "doc:cash" in out["message"]["refs"]
    assert any(s["terms"]["payment_days"] == 14 for s in out["message"]["term_sheets"])
    assert agent.decision_history[-1]["profile_used"]["cash_sensitive"]


def test_live_contradiction_keeps_archived_supplier_motive_unknown(tmp_path):
    data = package(tmp_path, {"doc:cash": document()})
    agent = UnifiedAgent(package=data)
    out = agent.decide(CASE, {"sup:A": [supplier("open", 42, body="We do not require earlier payment.")]})
    assert not agent.decision_history[-1]["profile_used"]["cash_sensitive"]
    assert {s["terms"]["payment_days"] for s in out["message"]["term_sheets"]} == {30}


def test_release_document_is_available_without_replacing_base_data(tmp_path):
    data = package(tmp_path, {"doc:base": document(body="No commercial request.")})
    release = tmp_path / "release-sunday"
    release.mkdir()
    (release / "facts.json").write_text(json.dumps({"doc:new": document()}))
    data = DataPackage(tmp_path)
    records, _ = CaseSupplierEvidence(data).prepare(CASE)
    assert {r["Information"]["id"] for r in records["sup:A"]} == {"doc:base", "doc:new"}
