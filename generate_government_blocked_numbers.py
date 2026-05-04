"""Generate a CSV of US government phone numbers to suppress for TCPA compliance.

Background:
    A TCPA law firm has advised us that the FCC monitors calls placed to
    government phone numbers (federal, state, municipal) as honeypot /
    traceback signals.  Calling one in an outbound campaign can trigger
    a regulatory traceback, so we suppress all of them up front.

Coverage:
    * Federal — Congress, White House, Cabinet departments, regulatory
      agencies (FCC, FTC, CFPB, SEC, etc.), federal courts.
    * State — All 50 states + DC + 5 territories: governor, AG (incl.
      consumer-protection division), PUC/PSC, secretary of state,
      treasurer, comptroller, state legislatures, supreme court,
      insurance commissioner, banking regulator, dept of revenue.
    * Municipal — Top ~200 US cities: mayor, city hall, city council,
      city attorney, city clerk, police non-emergency, consumer affairs.

The script writes ``government_blocked_numbers.csv`` next to it.  Run with::

    python3 generate_government_blocked_numbers.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

OUTPUT_PATH = Path(__file__).with_name("government_blocked_numbers.csv")

# ---------------------------------------------------------------------------
# Data — populated by research agents.  Each entry must have these keys:
#   phone, entity_name, entity_type, jurisdiction, level, office_type, source_url
# Phone numbers are E.164 (+1XXXXXXXXXX, no formatting).
# ---------------------------------------------------------------------------

ENTRIES_FEDERAL: list[dict] = [
    # Populated below from research
]

ENTRIES_STATE: list[dict] = [
    # Populated below from research
]

ENTRIES_MUNICIPAL: list[dict] = [
    # Populated below from research
]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

E164_RE = re.compile(r"^\+1\d{10}$")


def format_phone(e164: str) -> tuple[str, str]:
    """Return (formatted, dashed) variants for an E.164 +1NXXNXXXXXX number."""
    digits = e164[2:]  # strip leading +1
    formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    dashed = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return formatted, dashed


def validate(entries: list[dict], label: str) -> list[dict]:
    """Filter out malformed entries and warn about them."""
    seen: set[str] = set()
    clean: list[dict] = []
    for e in entries:
        phone = e.get("phone", "")
        if not E164_RE.match(phone):
            print(f"  [skip] {label}: bad E.164 {phone!r} for {e.get('entity_name')!r}")
            continue
        if phone in seen:
            continue
        seen.add(phone)
        clean.append(e)
    return clean


def main() -> None:
    fed = validate(ENTRIES_FEDERAL, "federal")
    state = validate(ENTRIES_STATE, "state")
    muni = validate(ENTRIES_MUNICIPAL, "municipal")

    all_rows = fed + state + muni

    # Cross-bucket dedup by phone (keep first occurrence)
    seen: set[str] = set()
    deduped = []
    for e in all_rows:
        if e["phone"] in seen:
            continue
        seen.add(e["phone"])
        deduped.append(e)

    deduped.sort(key=lambda r: (r["level"], r["jurisdiction"], r["entity_name"]))

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "phone_number_e164",
                "phone_number_formatted",
                "phone_number_dashed",
                "entity_name",
                "entity_type",
                "jurisdiction",
                "level",
                "office_type",
                "source_url",
            ]
        )
        for e in deduped:
            formatted, dashed = format_phone(e["phone"])
            writer.writerow(
                [
                    e["phone"],
                    formatted,
                    dashed,
                    e["entity_name"],
                    e["entity_type"],
                    e["jurisdiction"],
                    e["level"],
                    e.get("office_type", ""),
                    e.get("source_url", ""),
                ]
            )

    print(
        f"Wrote {len(deduped)} rows "
        f"(federal={len(fed)}, state={len(state)}, municipal={len(muni)}) "
        f"to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
