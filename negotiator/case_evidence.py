"""Read relevant, attributable supplier letters from the optional data package.

Buyer notes, scorecards and market data are not statements of supplier motive.
This adapter never routes the bundled ERP CSVs through the supplier CSV parser.
"""

import re
from collections.abc import Mapping
from datetime import date


class CaseSupplierEvidence:
    def __init__(self, package=None):
        self.package = package
        self.documents = (
            [(ref, package.record(ref)) for ref in package.ids("doc:")]
            if package is not None else []
        )

    def prepare(self, case):
        output = {sid: [] for sid in case.get("suppliers", [])}
        warnings = []
        parts = set(case.get("parts") or [])
        requested = set(case.get("refs") or []) | {case.get("trigger_doc")}
        documents = dict(self.documents)
        if self.package is not None:
            documents.update((ref, self.package.record(ref)) for ref in self.package.ids("news:"))
        case_facts = case.get("facts")
        if isinstance(case_facts, Mapping):
            for ref, fact in case_facts.items():
                if isinstance(ref, str) and ref.startswith(("doc:", "news:")) and isinstance(fact, Mapping):
                    base = (self.package.record(ref) or {}) if self.package is not None else {}
                    documents[ref] = {**base, **fact}
        try:
            cutoff = date.fromisoformat(case.get("as_of") or date.today().isoformat())
        except (TypeError, ValueError):
            cutoff = date.today()
        for ref, row in documents.items():
            is_news = ref.startswith("news:")
            sid = row.get("supplier_id") or row.get("supplier")
            if sid not in output:
                continue
            if not is_news:
                supplier = self.package.record(sid) if self.package is not None else {}
                author = str(row.get("author") or "").strip().casefold()
                known_authors = {sid.casefold(), str(supplier.get("name") or "").strip().casefold()} - {""}
                if (author not in known_authors
                        or (row.get("kind") or row.get("type")) not in {"email", "letter"}):
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
                text = next((row.get(key) for key in ("document_text", "body", "text")
                             if isinstance(row.get(key), str) and row[key]), None)
                if text is None:
                    if self.package is None:
                        raise FileNotFoundError(ref)
                    text = self.package.document(ref)
            except (OSError, ValueError) as exc:
                warnings.append(f"{ref}: {type(exc).__name__}")
                continue
            information = {
                "id": ref,
                "kind": "news" if is_news else "document",
                "supplier_id": sid,
                "part_id": next(iter(parts)) if len(parts) == 1 else None,
            }
            if is_news:
                information.update({
                    "news_headline": row.get("headline") or row.get("title"),
                    "news_body": text[:20000],
                    "news_date": row["date"],
                })
            else:
                information.update({
                    "document_text": text[:20000], "document_date": row["date"],
                    "archive_source": True,
                })
            output[sid].append({
                "Information": information,
                "Source": ref,
                "Priority (Argument wise)": 2 if ref in requested else 3,
            })
        return output, warnings
