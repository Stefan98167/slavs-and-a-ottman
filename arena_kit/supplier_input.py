"""Guard the supplier-only pipeline against known bundled evidence sources."""

import re


def ensure_supplier_source(source):
    """Reject references to bundled procurement data; do not silently reuse demos.

    Arbitrary uploads still need to be supplied by the caller. A filename cannot
    establish real-world provenance; this guard catches known package sources.
    """
    normalized = str(source).replace("\\", "/")
    if re.search(r"(?:^|/)data/data/", normalized):
        raise ValueError(
            "Bundled data/data evidence is not allowed in the supplier-only pipeline. "
            "Extract the supplier's actual files and use that JSON instead."
        )
