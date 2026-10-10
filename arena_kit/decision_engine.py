"""Dummy, deterministic decisions from quote_extract.extract() records.

No offers are sent. Default: counter 5% below each supplied quoted price.
The negotiation adapter can supply a policy price target derived from the
supplier's opening offer. No case baseline or market data is loaded.
Decisions and their supporting records are ranked by argument priority (1 first).
Records with the same explicit supplier_id and part_id share arguments. Records
without both IDs stand alone. Priority selects the lead evidence and message;
it does not change the policy target or establish that a claim is true.
"""

import argparse
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from .supplier_input import ensure_supplier_source


def _number(value):
    """Accept plain dot/comma decimals; reject ambiguous grouping and symbols."""
    if isinstance(value, bool):
        raise ValueError("Expected a number")
    text = str(value).strip()
    if not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", text):
        raise ValueError(f"Not a plain decimal: {value!r}")
    try:
        return Decimal(text.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid number: {value!r}") from exc


def _key(value):
    return re.sub(r"[\s_-]+", "_", value.strip().lower())


PRIORITY_COLUMN = "Priority (Argument wise)"


def _scope(record, index):
    info = record["Information"]
    supplier, part = info.get("supplier_id"), info.get("part_id")
    if all(isinstance(value, str) and value.strip() for value in (supplier, part)):
        return supplier, part
    return (index,)


def decide(records, *, target_price=None, counter_discount_pct=5):
    """Return JSON-ready {engine, decisions} from the extractor's list of dicts.

    target_price is an optional policy target supplied by the negotiation
    adapter, derived from the supplier's own opening quote. It applies to every
    row in this call. The discount is a policy setting. Information and Source
    are retained; no unrelated suppliers/parts are compared or merged. At each
    call, priorities select the lead_argument and order the arguments and
    decisions. Equal priorities retain input order. The message references the
    lead argument; accept/counter prices follow the supplier-derived target.
    """
    if not isinstance(records, list):
        raise ValueError("Expected the JSON array returned by extract(csvs)")
    limit = _number(target_price) if target_price is not None else None
    discount = _number(counter_discount_pct)
    if limit is not None and limit <= 0:
        raise ValueError("target_price must be positive")
    if not 0 <= discount < 100:
        raise ValueError("counter_discount_pct must be in [0, 100)")
    groups = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not isinstance(record.get("Information"), dict):
            raise ValueError(f"Record {index}: Information must be an object")
        priority = record.get(PRIORITY_COLUMN)
        if not isinstance(record.get("Source"), str) or type(priority) is not int or priority not in (1, 2, 3):
            raise ValueError(f"Record {index}: expected Source and priority 1, 2 or 3")
        ensure_supplier_source(record["Source"])
        groups.setdefault(_scope(record, index), []).append({
            "Information": record["Information"],
            "Source": record["Source"],
            PRIORITY_COLUMN: priority,
        })
    for arguments in groups.values():
        arguments.sort(key=lambda argument: argument[PRIORITY_COLUMN])
    decisions = []
    for index, record in enumerate(records):
        info = record["Information"]
        prices = [value for key, value in info.items() if _key(key) in {"unit_price", "price", "preis"}]
        decision = {**record, "action": "request_clarification", "proposed_unit_price": None}
        try:
            if len(prices) != 1:
                raise ValueError("Provide exactly one price column: unit_price, price or preis")
            price = _number(prices[0])
            if price <= 0:
                raise ValueError("Quoted price must be positive")
        except ValueError as exc:
            decision["reason"] = str(exc)
        else:
            if limit is None:
                target = price * (1 - discount / 100)
                decision["action"] = "counter_offer"
                decision["reason"] = f"Dummy policy counters {discount}% below the supplier's quoted price."
            else:
                decision["gap_to_target_pct"] = float((price / limit - 1) * 100)
                if price <= limit:
                    target = price
                    decision["action"] = "accept"
                    decision["reason"] = "Quote is at or below the policy price target."
                else:
                    target = limit
                    decision["action"] = "counter_offer"
                    decision["reason"] = "Quote exceeds the policy price target; counter at that target."
            proposed = target.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if proposed <= 0:
                decision["action"] = "request_clarification"
                decision["reason"] = "Proposed price rounds to zero; clarify price precision."
            else:
                decision["proposed_unit_price"] = float(proposed)
        arguments = groups[_scope(record, index)]
        lead = arguments[0]
        decision["arguments"] = arguments
        decision["lead_argument"] = lead
        decision["message"] = (
            f"Please review the supplied record at {lead['Source']} first "
            f"(argument priority {lead[PRIORITY_COLUMN]}). "
            f"Recorded information: {json.dumps(lead['Information'], ensure_ascii=False)}. "
            f"{decision['reason']}"
        )
        decisions.append(decision)
    decisions.sort(key=lambda decision: decision[PRIORITY_COLUMN])
    return {"engine": "dummy", "decisions": decisions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", type=Path, help="JSON output from quote_extract")
    parser.add_argument("--counter-discount-pct", default="5")
    args = parser.parse_args()
    try:
        records = json.loads(args.json_file.read_text(encoding="utf-8-sig"))
        result = decide(records, counter_discount_pct=args.counter_discount_pct)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
