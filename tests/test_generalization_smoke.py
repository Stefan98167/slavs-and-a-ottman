from copy import deepcopy

import pytest

from arena_kit.agents.unified import UnifiedAgent
from arena_kit.play import play
from arena_kit.sim import Sim, SimTable, load_cases


def _variants():
    base = load_cases()["case:S03"]
    fields = {
        "tooling_eur": [0, 250, 500],
        "ppm_commitment": [0, 250, 500],
        "chargeback_eur_per_complaint": [0, 50, 150],
        "incoterm": ["EXW", "FCA", "DAP"],
        "index_clause": [
            None,
            {"series": "MATERIAL-X", "material_share": 0.2, "deadband_pct": 3, "base_month": "2026-09"},
        ],
        "volume_per_year": [8490, 10000, 12000],
        "contract_months": [0, 12, 24],
    }
    variants = []
    for field, options in fields.items():
        case = deepcopy(base)
        case["case_id"] = f"case:S03-synthetic-{field}"
        if field not in case["negotiable"]:
            case["negotiable"].append(field)
        case["term_options"][field] = options
        if field in {"tooling_eur", "ppm_commitment", "chargeback_eur_per_complaint", "volume_per_year"}:
            case["fixed_terms"].pop(field, None)
        variants.append(case)
    return variants


def _run(case):
    sim = Sim({case["case_id"]: case}, no_clock=True)
    table = SimTable(sim)
    result = play(table, case["case_id"], UnifiedAgent())
    session = sim.sessions[table.session_id]
    assert session["status"] == "ended"
    assert session["end_reason"] in {"accepted", "walked_away"}
    for thread in session["threads"].values():
        for message in thread["messages"]:
            if message.get("from") != "buyer":
                continue
            for sheet in message.get("term_sheets") or []:
                assert set(sheet["terms"]) == set(case["negotiable"])
    return result


@pytest.mark.parametrize("case", list(load_cases().values()), ids=lambda case: case["case_id"])
def test_unified_closes_every_simulator_practice_case(case, monkeypatch):
    monkeypatch.delenv("SUPPLIER_ECONOMICS", raising=False)
    monkeypatch.delenv("SUPPLIER_ARCHIVE_EVIDENCE", raising=False)
    _run(case)


@pytest.mark.parametrize("case", _variants(), ids=lambda case: case["case_id"])
def test_unified_closes_unusual_negotiable_field_variants(case, monkeypatch):
    monkeypatch.delenv("SUPPLIER_ECONOMICS", raising=False)
    monkeypatch.delenv("SUPPLIER_ARCHIVE_EVIDENCE", raising=False)
    _run(case)
