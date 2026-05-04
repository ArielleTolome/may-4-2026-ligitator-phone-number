"""Generate a CSV of US government phone numbers to suppress for TCPA compliance.

Background:
    A TCPA law firm has advised us that the FCC monitors calls placed to
    government phone numbers (federal, state, municipal) as honeypot /
    traceback signals.  Calling one in an outbound campaign can trigger
    a regulatory traceback, so we suppress all of them up front.

Coverage (loaded from government_data/*.json):
    * Federal — Congress (all 100 senators), White House, Cabinet
      departments, regulatory agencies (FCC, FTC, CFPB, SEC, etc.),
      federal courts.
    * State — All 50 states + DC + 5 territories: governors (47),
      attorneys general (all), AG consumer-protection lines, PUC/PSC,
      secretaries of state, insurance commissioners, etc.
    * Municipal — Top ~77 US cities: mayor, city hall, city council,
      city attorney, city clerk, police non-emergency, consumer affairs.

The script writes ``government_blocked_numbers.csv`` next to it.  Run with::

    python3 generate_government_blocked_numbers.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).with_name("government_data")
OUTPUT_PATH = Path(__file__).with_name("government_blocked_numbers.csv")

E164_RE = re.compile(r"^\+1\d{10}$")


def format_phone(e164: str) -> tuple[str, str]:
    """Return (formatted, dashed) variants for an E.164 +1NXXNXXXXXX number."""
    digits = e164[2:]
    return (
        f"({digits[:3]}) {digits[3:6]}-{digits[6:]}",
        f"{digits[:3]}-{digits[3:6]}-{digits[6:]}",
    )


def load_bucket(name: str) -> list[dict]:
    path = DATA_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate(entries: list[dict], label: str) -> list[dict]:
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
    fed = validate(load_bucket("federal"), "federal")
    state = validate(load_bucket("state"), "state")
    muni = validate(load_bucket("municipal"), "municipal")

    seen: set[str] = set()
    deduped = []
    for entry in fed + state + muni:
        if entry["phone"] in seen:
            continue
        seen.add(entry["phone"])
        deduped.append(entry)

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
