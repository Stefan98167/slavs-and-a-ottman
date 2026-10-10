import json
from pathlib import Path

import pytest

from negotiator.intelligence import (
    EvidenceInputError,
    bind_evidence_scope,
    build_supplier_context,
    filter_evidence,
    load_evidence,
)

FIXTURE = Path(__file__).parent / "fixtures" / "intelligence_quotes.json"


def test_load_normalizes_values_and_preserves_unknown_fields():
    evidence = load_evidence(FIXTURE)

    first = evidence[0]
    assert first["id"] == "quote:7100001"
    assert first["kind"] == "quote"
    assert first["data"]["unit_price"] == 142.5
    assert first["data"]["payment_days"] == 30
    assert first["data"]["awarded"] is True
    assert evidence[1]["priority"] == 2
    assert evidence[1]["data"]["future_quote_field"] == "kept"


def test_filter_and_context_are_traceable_and_do_not_infer_profile_traits():
    evidence = load_evidence(json.loads(FIXTURE.read_text()))
    matches = filter_evidence(evidence, "sup:70110", "part:310010")
    context = build_supplier_context(evidence, "sup:70110", "part:310010")

    assert len(matches) == 2
    assert context["quote_history"]["count"] == 2
    assert context["quote_history"]["latest_quote_date"] == "2025-02-01"
    assert context["quote_history"]["latest_unit_price"] == 130
    assert context["quote_history"]["min_unit_price"] == 130
    assert context["quote_history"]["max_unit_price"] == 142.5
    assert context["quote_history"]["awarded_quote_count"] == 1
    assert context["quote_history"]["fact_sources"]["min_unit_price"] == [
        {"evidence_id": "quote:7100004", "source": "data/data/quotes.csv:5"}
    ]
    assert all(
        profile["state"] == "unknown" and profile["confidence"] == 0.0
        for profile in context["supplier_profile"].values()
    )
    assert context["evidence_gaps"] == [
        "No payment, financial, document, capacity, or quality evidence is available in this input."
    ]
    assert json.loads(json.dumps(context)) == context


def test_future_evidence_and_non_quote_fields_are_tolerated():
    evidence = load_evidence(
        [
            {
                "Information": {"id": "document:12", "supplier_id": "sup:70110", "reviewed": "false"},
                "Source": "documents.csv:2",
                "Extra Wrapper Field": {"score": "1.5"},
            }
        ]
    )

    context = build_supplier_context(evidence, "sup:70110")
    assert context["evidence"][0]["data"]["reviewed"] is False
    assert context["evidence"][0]["record_fields"]["Extra Wrapper Field"]["score"] == 1.5
    assert context["quote_history"]["count"] == 0


def test_supplier_csv_records_can_be_bound_to_live_scope_with_traceable_quote_history():
    extracted = [
        {
            "Information": {"Unit Price": "17.47", "Currency": "EUR", "Payment Terms": "30"},
            "Source": "supplier_upload.csv:2",
            "Priority (Argument wise)": 1,
        }
    ]
    evidence = bind_evidence_scope(load_evidence(extracted), "sup:live", "part:live")
    context = build_supplier_context(evidence, "sup:live", "part:live")

    assert context["quote_history"]["count"] == 1
    assert context["quote_history"]["min_unit_price"] == 17.47
    assert context["quote_history"]["fact_sources"]["min_unit_price"] == [
        {"evidence_id": "supplier_upload.csv:2", "source": "supplier_upload.csv:2"}
    ]
    assert context["evidence"][0]["data"]["Unit Price"] == 17.47
    assert context["evidence"][0]["data"]["unit_price"] == 17.47


def test_scope_binding_refuses_a_conflicting_explicit_identity():
    evidence = load_evidence([
        {"Information": {"supplier_id": "sup:other"}, "Source": "supplier_upload.csv:2"}
    ])

    with pytest.raises(EvidenceInputError, match="belongs to"):
        bind_evidence_scope(evidence, "sup:live")


@pytest.mark.parametrize("value", [{}, 3])
def test_non_list_python_input_has_clear_custom_error(value):
    with pytest.raises(EvidenceInputError, match="top-level array|path or an already-loaded list"):
        load_evidence(value)


def test_non_array_json_document_has_clear_custom_error(tmp_path):
    invalid_document = tmp_path / "invalid.json"
    invalid_document.write_text('{"not": "an array"}')

    with pytest.raises(EvidenceInputError, match="top-level array"):
        load_evidence(invalid_document)
