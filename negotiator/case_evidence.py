"""Read relevant, attributable supplier letters from the optional data package.

Buyer notes, scorecards and market data are not statements of supplier motive.
This adapter never routes the bundled ERP CSVs through the supplier CSV parser.
"""

import re
from datetime import date


class CaseSupplierEvidence:
    def __init__(self, package):
        self.package = package
        self.documents = [(ref, package.record(ref)) for ref in package.ids("doc:")]

    def prepare(self, case):
        output = {sid: [] for sid in case.get("suppliers", [])}
        warnings = []
        parts = set(case.get("parts") or [])
        requested = set(case.get("refs") or []) | {case.get("trigger_doc")}
        try:
            cutoff = date.fromisoformat(case.get("as_of") or date.today().isoformat())
        except (TypeError, ValueError):
            cutoff = date.today()
        for ref, row in self.documents:
            sid = row.get("supplier_id") or row.get("supplier")
            if sid not in output:
                continue
            supplier = self.package.record(sid)
            author = str(row.get("author") or "").strip().casefold()
            known_authors = {sid.casefold(), str(supplier.get("name") or "").strip().casefold()} - {""}
            if author not in known_authors or (row.get("kind") or row.get("type")) not in {"email", "letter"}:
                continue
            scoped_parts = set(re.findall(r"part:[\w.-]+", str(row.get("part_ids") or row.get("part_id") or "")))
            if scoped_parts and (not parts or not scoped_parts <= parts):
                continue
            try:
                document_date = date.fromisoformat(row.get("date") or "")
            except (TypeError, ValueError):
                warnings.append(f"{ref}: no usable document date")
                continue
            if document_date > cutoff:
                continue
            try:
                text = self.package.document(ref)
            except (OSError, ValueError) as exc:
                warnings.append(f"{ref}: {type(exc).__name__}")
                continue
            output[sid].append({
                "Information": {
                    "id": ref, "kind": "document", "supplier_id": sid,
                    "part_id": next(iter(parts)) if len(parts) == 1 else None,
                    "document_text": text[:20000], "document_date": row["date"],
                    "archive_source": True,
                },
                "Source": ref,
                "Priority (Argument wise)": 2 if ref in requested else 3,
            })
        return output, warnings
