#!/usr/bin/env python3
"""
compare_ranked_ingatlanok.py — Compare two ranked_ingatlanok.json files and
produce a Markdown file showing only the properties that appear in both lists.

Usage:
    python compare_ranked_ingatlanok.py input1 input2 [--output FILE]

Example:
    python compare_ranked_ingatlanok.py "ranked_Balázs ház/ranked_ingatlanok.json" \
                                        "ranked_Encike ház/ranked_ingatlanok.json"

Output (default): compare_result.md in the current working directory.
"""

import argparse
import json
import os
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> list:
    """Load a ranked_ingatlanok.json and always return a list."""
    if not os.path.isfile(path):
        print(f"HIBA: Nem található a fájl: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = list(data.values())
    if not isinstance(data, list):
        print(f"HIBA: Váratlan JSON struktúra: {path}", file=sys.stderr)
        sys.exit(1)
    return data


def make_lookup(items: list) -> dict:
    """
    Build a dict keyed by a canonical identifier for each property.
    Primary key: 'link' (the ingatlan.com URL — most reliable).
    Fallback key: 'cím' (address string).
    Value: (rank_1based, property_dict)
    """
    lookup = {}
    for rank0, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        key = item.get("link", "").strip() or item.get("cím", "").strip()
        if key:
            lookup[key] = (rank0 + 1, item)
    return lookup


def label_from_path(path: str) -> str:
    """
    Derive a human-readable label from the file path.
    'ranked_Balázs ház/ranked_ingatlanok.json' -> 'Balázs ház'
    'ranked_ingatlanok.json' -> 'Input'
    """
    folder = os.path.dirname(path)
    if folder:
        base = os.path.basename(folder)
        # Strip leading 'ranked_' prefix if present
        if base.lower().startswith("ranked_"):
            base = base[len("ranked_"):]
        return base
    return os.path.basename(path)


def format_cell(rank: int, item: dict) -> str:
    """Render one table cell: rank, linked address, price, area."""
    cim  = item.get("cím", "?")
    link = item.get("link", "").strip()
    ar   = item.get("Ár", "?")
    ter  = item.get("Alapterület", "?")

    address_part = f"[{cim}]({link})" if link else cim
    return f"**#{rank}** {address_part} — {ar}, {ter}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compare two ranked_ingatlanok.json files and output matching items as a Markdown table.",
    )
    parser.add_argument("input1", metavar="INPUT1", help="First ranked_ingatlanok.json")
    parser.add_argument("input2", metavar="INPUT2", help="Second ranked_ingatlanok.json")
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        default="compare_result.md",
        help="Output Markdown file (default: compare_result.md)",
    )
    args = parser.parse_args()

    label1 = label_from_path(args.input1)
    label2 = label_from_path(args.input2)

    items1 = load_json(args.input1)
    items2 = load_json(args.input2)

    lookup1 = make_lookup(items1)
    lookup2 = make_lookup(items2)

    # Find common keys (preserve order by rank in list1)
    common_keys = [k for k in lookup1 if k in lookup2]
    # Sort by rank in list1
    common_keys.sort(key=lambda k: lookup1[k][0])

    # ---------------------------------------------------------------------------
    # Build Markdown output
    # ---------------------------------------------------------------------------
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"# Ingatlan összehasonlítás")
    lines.append("")
    lines.append(f"- **{label1}**: `{args.input1}` ({len(items1)} ingatlan)")
    lines.append(f"- **{label2}**: `{args.input2}` ({len(items2)} ingatlan)")
    lines.append(f"- Generálva: {now}")
    lines.append("")

    if not common_keys:
        lines.append("> **No matches found between the two ranked lists.**")
    else:
        lines.append(f"## Egyező ingatlanok ({len(common_keys)} db)")
        lines.append("")
        lines.append(f"| # | {label1} | {label2} |")
        lines.append("|---|" + "-" * max(len(label1) + 2, 20) + "|" + "-" * max(len(label2) + 2, 20) + "|")

        for row_num, key in enumerate(common_keys, 1):
            rank1, item1 = lookup1[key]
            rank2, item2 = lookup2[key]
            cell1 = format_cell(rank1, item1)
            cell2 = format_cell(rank2, item2)
            lines.append(f"| {row_num} | {cell1} | {cell2} |")

    md_content = "\n".join(lines) + "\n"

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Eredmény elmentve: {args.output}")
    if common_keys:
        print(f"Egyező ingatlanok száma: {len(common_keys)}")
    else:
        print("Nincs egyező ingatlan a két listában.")


if __name__ == "__main__":
    main()
