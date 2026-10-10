from arena_kit.docs import quote_terms
from negotiator.supplier_evidence import build_thread_supplier_context, quote_pdf_record


P08_QUOTE = """Edelstahl-Service Donautal GmbH
Angebot / Quote offer:70710-0
Offered terms
Unit price (EUR) 6.05
Payment terms (days net) 30
Index clause none
Contract term (months) 12
Our standard terms (apply to everything not stated above)
Quality commitment (ppm) 50
Chargeback per complaint (EUR) 0.00
Terms fixed by your enquiry
Lead time (days) 10
Volume per year (pcs) 94800
Price valid from 2027-01-01
Incoterm DAP
Tooling (EUR) 0.00
Part(s): part:370010.
"""

P01_QUOTE = """Gießerei Brandlhuber GmbH & Co. KG
Angebot / Quote offer:70110-0
Offered terms
Unit price (EUR) 138.55
Price valid from 2026-11-01
Our standard terms (apply to everything not stated above)
Payment terms (days net) 30
Quality commitment (ppm) 900
Chargeback per complaint (EUR) 0.00
Terms fixed by your enquiry
Lead time (days) 42
Volume per year (pcs) 8150
Contract term (months) 12
Index clause none
Incoterm FCA
Tooling (EUR) 0.00
Part(s): part:310010.
"""


def test_supplier_pdf_quote_becomes_sourced_terms_and_quote_history():
    record = quote_pdf_record(P08_QUOTE, "att:70710-0-quote (quote-offer-70710-0.pdf)", "sup:70710")
    bundle = build_thread_supplier_context(
        [{"from": "sales@70710", "attachments": [{"name": "quote-offer-70710-0.pdf",
                                                       "text": P08_QUOTE,
                                                       "attachment_id": "att:70710-0-quote"}],
          "term_sheets": [{"term_sheet_id": "offer:70710-0", "terms": {"unit_price": 6.05}}]}],
        "sup:70710",
    )

    context = bundle["contexts"][0]
    quote = context["quote_history"]["quotes"][0]
    assert record["Information"]["unit_price"] == 6.05
    assert record["Information"]["terms"]["lead_time_days"] == 10
    assert context["quote_history"]["count"] == 1  # PDF and email term sheet deduplicate by offer ID
    assert quote["evidence_id"] == "offer:70710-0"
    assert quote["source"].startswith("att:70710-0-quote")
    assert quote["terms"]["contract_months"] == 12
    assert quote["terms"]["index_clause"] is None


def test_p01_supplier_pdf_keeps_offered_standard_and_fixed_terms():
    record = quote_pdf_record(P01_QUOTE, "att:70110-0-quote (quote-offer-70110-0.pdf)", "sup:70110")
    information = record["Information"]

    assert information["unit_price"] == 138.55
    assert information["currency"] == "EUR"
    assert information["payment_days"] == 30
    assert information["lead_time_days"] == 42
    assert information["volume_per_year"] == 8150
    assert information["part_id"] == "part:310010"
    assert information["term_sections"]["standard"]["payment_days"] == 30
    assert information["term_sections"]["fixed"]["lead_time_days"] == 42


def test_pdf_terms_parse_european_decimal_commas():
    terms = quote_terms("""Offered terms
Unit price (EUR) 138,55
Index clause AS-14404, 45% material, deadband 0,5 %, base 2026-06
""")

    assert terms["stated"]["unit_price"] == 138.55
    assert terms["stated"]["index_clause"] == {
        "series": "AS-14404",
        "material_share": 0.45,
        "deadband_pct": 0.5,
        "base_month": "2026-06",
    }


def test_supplier_message_combines_index_movement_and_cost_share_with_source():
    message = {
        "message_id": "msg:70710-0-0",
        "from": "sales@70710",
        "body": "AS-14404 rose 5.9 % in twelve months and is 45 % of our cost. "
                "LCI-C rose 2.7 % in twelve months and is 5 % of our cost.",
        "claims": [{"type": "index_change", "refs": ["idx:AS-14404@2025-06", "idx:AS-14404@2026-06"],
                    "asserted": {"change_pct": 5.9}}],
        "term_sheets": [{"term_sheet_id": "offer:70710-0", "terms": {"unit_price": 6.05}}],
    }
    bundle = build_thread_supplier_context([message], "sup:70710")
    claims = bundle["contexts"][0]["supplier_claims"]

    alloy = next(claim for claim in claims if claim["data"].get("series") == "AS-14404")
    assert alloy["data"]["index_change_pct"] == 5.9
    assert alloy["data"]["cost_share_pct"] == 45.0
    assert alloy["data"]["time_window"] == "twelve months"
    assert alloy["source"] == "msg:70710-0-0"
    assert alloy["data"]["structured_claim"]["type"] == "index_change"


def test_thread_context_unifies_pdf_csv_quotes_claims_and_provenance():
    csv_record = {
        "Information": {"Part Number": "part:370010", "Payment Terms": "45",
                        "Historical Unit Price": "5.80"},
        "Source": "supplier_attachment_history.csv:2",
        "Priority (Argument wise)": 1,
    }
    event = {
        "message_id": "msg:70710-0-0",
        "from": "sales@70710",
        "body": "AS-14404 rose 5.9 % in twelve months and is 45 % of our cost.",
        "attachments": [
            {"attachment_id": "att:70710-0-quote", "name": "quote-offer-70710-0.pdf", "text": P08_QUOTE},
            {"name": "history.csv", "csv_records": [csv_record]},
        ],
        "term_sheets": [{"term_sheet_id": "offer:70710-0", "terms": {"unit_price": 6.05}}],
    }
    context = build_thread_supplier_context([event], "sup:70710")["contexts"][0]

    assert context["part_id"] == "part:370010"
    assert context["quote_history"]["count"] == 2
    assert context["quote_history"]["latest_unit_price"] == 5.8
    assert context["quote_history"]["fact_sources"]["min_unit_price"] == [
        {"evidence_id": "supplier_attachment_history.csv:2", "source": "supplier_attachment_history.csv:2"}
    ]
    assert context["evidence"]
    assert any(item["kind"] == "claim" for item in context["evidence"])
    assert any(item["source"].startswith("att:70710-0-quote") for item in context["evidence"])
