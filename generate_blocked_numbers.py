"""Generate a CSV of phone numbers to block for TCPA-risk reasons.

Background:
    A TCPA plaintiff has been documented to purchase phone numbers whose
    last seven digits form a repeating pattern (e.g. (AAA) 111-1111,
    (AAA) 222-2222, ... (AAA) 999-9999) and waits for unsolicited callers.
    To eliminate that risk we block every (US-area-code)-DDD-DDDD where
    D is 1..9 across all known US/US-territory NPAs.

The script writes ``blocked_numbers.csv`` next to it.  Run with::

    python3 generate_blocked_numbers.py
"""

from __future__ import annotations

import csv
from pathlib import Path

# Active NPAs (area codes) assigned to US states, DC and US territories.
# Compiled from NANPA assignments through 2026.  Each list is sorted
# ascending and deduplicated.  Overlays are included.
US_AREA_CODES: dict[str, list[int]] = {
    "Alabama": [205, 251, 256, 334, 483, 659, 938],
    "Alaska": [907],
    "Arizona": [480, 520, 602, 623, 624, 928],
    "Arkansas": [327, 479, 501, 870],
    "California": [
        209, 213, 279, 310, 323, 341, 350, 357, 369, 408, 415, 424,
        442, 510, 530, 559, 562, 619, 626, 627, 628, 650, 657, 661,
        669, 707, 714, 738, 747, 760, 805, 818, 820, 831, 837, 840,
        858, 909, 916, 925, 935, 949, 951,
    ],
    "Colorado": [303, 719, 720, 748, 970, 983],
    "Connecticut": [203, 475, 860, 959],
    "Delaware": [302],
    "District of Columbia": [202, 771],
    "Florida": [
        239, 305, 321, 324, 352, 386, 407, 448, 561, 645, 656, 689,
        727, 728, 754, 772, 786, 813, 850, 863, 904, 941, 954,
    ],
    "Georgia": [229, 404, 470, 478, 678, 706, 762, 770, 912, 943],
    "Hawaii": [808],
    "Idaho": [208, 986],
    "Illinois": [
        217, 224, 309, 312, 331, 447, 464, 618, 630, 708, 730, 773,
        779, 815, 847, 861, 872,
    ],
    "Indiana": [219, 260, 317, 463, 574, 765, 812, 930],
    "Iowa": [319, 515, 563, 641, 712],
    "Kansas": [316, 620, 785, 913],
    "Kentucky": [270, 364, 502, 606, 859],
    "Louisiana": [225, 318, 337, 457, 504, 985],
    "Maine": [207],
    "Maryland": [227, 240, 301, 410, 443, 667],
    "Massachusetts": [339, 351, 413, 508, 617, 774, 781, 857, 978],
    "Michigan": [
        231, 248, 269, 313, 517, 586, 616, 679, 734, 810, 906, 947, 989,
    ],
    "Minnesota": [218, 320, 507, 612, 651, 763, 924, 952],
    "Mississippi": [228, 471, 601, 662, 769],
    "Missouri": [235, 314, 417, 557, 573, 636, 660, 816, 975],
    "Montana": [406],
    "Nebraska": [308, 402, 531],
    "Nevada": [702, 725, 775],
    "New Hampshire": [603],
    "New Jersey": [201, 551, 609, 640, 732, 848, 856, 862, 908, 973],
    "New Mexico": [505, 575],
    "New York": [
        212, 315, 329, 332, 347, 363, 516, 518, 585, 607, 631, 646,
        680, 716, 718, 838, 845, 914, 917, 929, 934,
    ],
    "North Carolina": [
        252, 336, 472, 704, 743, 828, 910, 919, 980, 984,
    ],
    "North Dakota": [701],
    "Ohio": [
        216, 220, 234, 283, 326, 330, 380, 419, 436, 440, 513, 567,
        614, 740, 937,
    ],
    "Oklahoma": [405, 539, 572, 580, 918],
    "Oregon": [458, 503, 541, 971],
    "Pennsylvania": [
        215, 223, 267, 272, 412, 445, 484, 570, 582, 610, 717, 724,
        814, 835, 878,
    ],
    "Rhode Island": [401],
    "South Carolina": [803, 821, 839, 843, 854, 864],
    "South Dakota": [605],
    "Tennessee": [423, 615, 629, 731, 865, 901, 931],
    "Texas": [
        210, 214, 254, 281, 325, 346, 361, 409, 430, 432, 469, 512,
        682, 713, 726, 737, 806, 817, 825, 830, 832, 868, 903, 915,
        936, 940, 945, 956, 972, 979,
    ],
    "Utah": [385, 435, 801],
    "Vermont": [802],
    "Virginia": [
        276, 434, 540, 571, 686, 703, 757, 804, 826, 948,
    ],
    "Washington": [206, 253, 360, 425, 509, 564],
    "West Virginia": [304, 681],
    "Wisconsin": [262, 274, 353, 414, 534, 608, 715, 920],
    "Wyoming": [307],
    # US territories
    "American Samoa": [684],
    "Guam": [671],
    "Northern Mariana Islands": [670],
    "Puerto Rico": [787, 939],
    "US Virgin Islands": [340],
}

# Repeating-digit central-office + line-number patterns to block.  The
# user requested 111-1111 through 999-9999 — i.e. digits 1..9.
REPEATING_DIGITS = range(1, 10)

# Sequential ascending 7-digit lines (CO must start 2-9, so we drop the
# 0/1 starting positions).  Each NPA gets one line per starting digit.
SEQUENTIAL_ASCENDING_STARTS = [2, 3, 4, 5, 6, 7, 8, 9]

# Sequential descending 7-digit lines.  Same constraint on CO (first
# digit 2-9).  Starting digits 9..2 produce strictly-decreasing strings.
SEQUENTIAL_DESCENDING_STARTS = [9, 8, 7, 6, 5, 4, 3, 2]

# Ascending-then-descending palindromes.  The 7-digit string forms a
# pyramid (e.g. 2345432 — peak at position 4).  Peak digit P with valid
# CO requires the leading digit P-3 ∈ {2..9}, so P ∈ {5..9} … but we
# also include the wrap-around sequence 7890987 (peak 9) and 6789876
# (peak 9) which are the two most memorable. Peak digits 5..9 cover six
# canonical patterns; we also include 8901098 and 9012109 as recognised
# vanity numbers.
PALINDROME_PYRAMID_PATTERNS = [
    "2345432",
    "3456543",
    "4567654",
    "5678765",
    "6789876",
    "7890987",
    "8901098",
    "9012109",
]

# Fictional / reserved-for-TV-and-film line-number range.  NANPA reserves
# 555-0100 through 555-0199 for fictional use; if any are quietly
# assigned to a real line, calling them is a guaranteed plaintiff trap.
FICTIONAL_555_LINE_RANGE = range(100, 200)  # 555-01XX
FICTIONAL_555_CO = "555"

OUTPUT_PATH = Path(__file__).with_name("blocked_numbers.csv")


def _emit(npa: int, jurisdiction: str, pattern: str, seven: str):
    """Helper: format a 7-digit line into the standard tuple."""
    co, line = seven[:3], seven[3:]
    e164 = f"+1{npa}{seven}"
    formatted = f"({npa}) {co}-{line}"
    dashed = f"{npa}-{co}-{line}"
    return e164, formatted, dashed, npa, jurisdiction, pattern


def iter_blocked_numbers():
    """Yield (e164, formatted, dashed, area_code, jurisdiction, pattern)."""
    for jurisdiction, codes in US_AREA_CODES.items():
        for npa in sorted(set(codes)):
            # Repeating digits DDD-DDDD.
            for d in REPEATING_DIGITS:
                seven = str(d) * 7
                yield _emit(npa, jurisdiction, f"repeating_{d}", seven)

            # Sequential ascending.
            for start in SEQUENTIAL_ASCENDING_STARTS:
                seven = "".join(str((start + i) % 10) for i in range(7))
                yield _emit(npa, jurisdiction, f"ascending_from_{start}", seven)

            # Sequential descending.
            for start in SEQUENTIAL_DESCENDING_STARTS:
                seven = "".join(str((start - i) % 10) for i in range(7))
                yield _emit(npa, jurisdiction, f"descending_from_{start}", seven)

            # Pyramid palindromes.
            for seven in PALINDROME_PYRAMID_PATTERNS:
                yield _emit(npa, jurisdiction, f"palindrome_{seven}", seven)

            # Fictional 555-01XX range.
            for line in FICTIONAL_555_LINE_RANGE:
                seven = f"{FICTIONAL_555_CO}{line:04d}"
                yield _emit(npa, jurisdiction, "fictional_555_01XX", seven)


def main() -> None:
    rows = list(iter_blocked_numbers())
    # Dedupe (e.g. ascending_from_5 == 5678901, doesn't collide today but
    # cheap to guard) and sort by area code, then pattern, then number.
    seen: set[str] = set()
    deduped = []
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        deduped.append(r)
    deduped.sort(key=lambda r: (r[3], r[5], r[0]))
    rows = deduped

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "phone_number_e164",
                "phone_number_formatted",
                "phone_number_dashed",
                "area_code",
                "state_or_territory",
                "pattern",
            ]
        )
        for row in rows:
            writer.writerow(row)

    total_codes = sum(len(set(c)) for c in US_AREA_CODES.values())
    print(f"Wrote {len(rows)} rows across {total_codes} area codes to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
