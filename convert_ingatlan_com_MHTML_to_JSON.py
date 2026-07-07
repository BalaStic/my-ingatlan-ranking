#!/usr/bin/env python3
"""
extract_ingatlan.py — Extract property data from ingatlan.com MHTML files.

Usage:
    python extract_ingatlan.py <file1.mhtml> [file2.mhtml ...] [--output FILE]

Wildcards are supported (e.g. *.mhtml).
"""

import argparse
import email
import glob
import json
import os
import re
import sys
from email import policy

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Field definitions — maps the JSON key to the Hungarian label(s) on the page
# ---------------------------------------------------------------------------
PARAM_FIELDS = [
    "Alapterület",
    "Telekterület",
    "Szobák",
    "Ingatlan állapota",
    "Építés éve",
    "Komfort",
    "Épület szintjei",
    "Légkondicionáló",
    "Akadálymentesített",
    "Fürdő és wc",
    "Kilátás",
    "Tetőtér",
    "Pince",
    "Parkolás",
    "Átlag gázfogyasztás",
    "Átlag áramfogyasztás",
    "Rezsiköltség",
    "Közös költség",
    "Fűtés",
    "Napelem",
    "Szigetelés",
    "Energetikai tanúsítvány",
]

MISSING = "nincs megadva"


# ---------------------------------------------------------------------------
# MHTML → HTML
# ---------------------------------------------------------------------------

def extract_html_from_mhtml(mhtml_path: str) -> tuple[str, str]:
    """Return (html_content, source_url) extracted from an MHTML file."""
    with open(mhtml_path, "rb") as f:
        raw = f.read()

    msg = email.message_from_bytes(raw, policy=policy.compat32)

    source_url = msg.get("Snapshot-Content-Location", "") or msg.get("Content-Location", "")

    html_part = None
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    html_part = payload.decode(charset, errors="replace")
                    # prefer the first html part (main page)
                    break
    else:
        ct = msg.get_content_type()
        if ct == "text/html":
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload:
                html_part = payload.decode(charset, errors="replace")

    if html_part is None:
        raise ValueError(f"No text/html part found in {mhtml_path}")

    return html_part, source_url


# ---------------------------------------------------------------------------
# HTML → data
# ---------------------------------------------------------------------------

def clean_text(s: str) -> str:
    """Strip and normalise whitespace."""
    return re.sub(r"\s+", " ", s).strip()


def extract_data(html: str, source_url: str, mhtml_path: str = "") -> dict:
    soup = BeautifulSoup(html, "lxml")

    result = {}

    # --- link ---
    # Format: https://ingatlan.com/<ID>
    # The ID is the number at the end of the MHTML filename (e.g. "#35245146.mhtml")
    link = ""
    if mhtml_path:
        m = re.search(r"#?(\d+)\.mhtml$", os.path.basename(mhtml_path), re.IGNORECASE)
        if m:
            link = f"https://ingatlan.com/{m.group(1)}"
    # Fallback: extract numeric ID from canonical URL
    if not link:
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            m = re.search(r"/(\d+)(?:[/?#]|$)", canonical["href"])
            if m:
                link = f"https://ingatlan.com/{m.group(1)}"
    # Last resort: use the full canonical or og:url
    if not link:
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            link = canonical["href"].strip()
    if not link:
        og_url = soup.find("meta", property="og:url")
        if og_url and og_url.get("content"):
            link = og_url["content"].strip()
    if not link:
        link = source_url.strip()
    result["link"] = link or MISSING

    # --- cím (title / address) ---
    # ingatlan.com uses <span class="card-title ... fw-bold ..."> inside section#hero for the address.
    # There is no <h1> on the page.
    cim = ""
    for selector in [
        "section#hero span.fw-bold",
        "span.card-title.fw-bold",
        "h1.js-listing-card-title",
        "h1[class*='title']",
        ".listing-title",
        "h1",
    ]:
        el = soup.select_one(selector)
        if el:
            text = clean_text(el.get_text())
            if text:
                cim = text
                break
    result["cím"] = cim or MISSING

    # --- típus (property type, e.g. "Eladó tégla lakás") ---
    # Located in the hero section as a <span class="card-title"> sibling right after the address span.
    # The address span has class "fw-bold"; the típus span has "card-title" but NOT "fw-bold".
    tipus = ""
    for hero in soup.select("section#hero"):
        # Find the address span (which has fw-bold), then its next card-title sibling (without fw-bold)
        addr_span = hero.select_one("span.card-title.fw-bold")
        if addr_span:
            parent = addr_span.parent
            if parent:
                # Find the next card-title span that is NOT fw-bold
                for sib in parent.find_all("span", class_="card-title", recursive=False):
                    classes = sib.get("class", [])
                    if "fw-bold" not in classes and sib is not addr_span:
                        tipus = clean_text(sib.get_text())
                        if tipus:
                            break
        if tipus:
            break
    result["típus"] = tipus or MISSING

    # --- Build param_map first (needed for Ár and all parameter fields) ---
    # ingatlan.com renders params as label/value pairs in various container structures.
    param_map = {}

    def add_pair(label_text: str, value_text: str):
        label_text = clean_text(label_text)
        value_text = clean_text(value_text)
        if label_text and value_text:
            param_map[label_text] = value_text

    # Pattern E (highest priority): div.listing-property blocks
    # Structure: <div class="listing-property ..."><span>LABEL</span><span>VALUE</span></div>
    # These cover the top summary row: Ár, Alapterület, Telekterület, Szobák
    for lp in soup.find_all("div", class_=re.compile(r"\blisting-property\b")):
        spans = lp.find_all("span", recursive=False)
        if len(spans) >= 2:
            add_pair(spans[0].get_text(), spans[1].get_text())
        elif len(spans) == 1:
            # label is a direct text node, value is in the span (or vice-versa)
            texts = [t.strip() for t in lp.strings if t.strip()]
            if len(texts) >= 2:
                add_pair(texts[0], texts[1])
        else:
            # fallback: split all text into first-token label, rest value
            texts = [t.strip() for t in lp.strings if t.strip()]
            if len(texts) >= 2:
                add_pair(texts[0], " ".join(texts[1:]))

    # Pattern A: <dt>/<dd> pairs
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            add_pair(dt.get_text(), dd.get_text())

    # Pattern B: table rows with two cells
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) == 2:
            add_pair(cells[0].get_text(), cells[1].get_text())

    # Pattern C: divs/spans with a "label" class next to a "value" class sibling
    for label_el in soup.find_all(class_=re.compile(r"(label|parameter-name|param-name|key)", re.I)):
        value_el = label_el.find_next_sibling()
        if value_el:
            add_pair(label_el.get_text(), value_el.get_text())

    # Pattern D: look for elements whose text matches our known field names exactly
    # (they often appear as standalone spans/divs next to a value sibling)
    all_label_fields = PARAM_FIELDS + ["Ár"]
    for field in all_label_fields:
        if field in param_map:
            continue
        tags = soup.find_all(string=re.compile(r"^\s*" + re.escape(field) + r"\s*$"))
        for tag in tags:
            parent = tag.parent
            # try next sibling element
            sibling = parent.find_next_sibling()
            if sibling and sibling.get_text(strip=True):
                add_pair(field, sibling.get_text())
                break
            # try parent's next sibling
            grand_sibling = parent.parent.find_next_sibling() if parent.parent else None
            if grand_sibling and grand_sibling.get_text(strip=True):
                add_pair(field, grand_sibling.get_text())
                break

    # --- Ár (price) ---
    result["Ár"] = param_map.get("Ár", MISSING)

    # --- leírás (description) ---
    # Find the card that has an h5 "Leírás" heading, then grab the paragraph text below it.
    leiras = ""
    leiras_heading = soup.find(["h5", "h4", "h3"], string=re.compile(r"^\s*Leírás\s*$"))
    if leiras_heading:
        card = leiras_heading.find_parent("div", class_=re.compile(r"\bcard\b"))
        if card:
            paras = card.find_all("p")
            if paras:
                leiras = clean_text(" ".join(p.get_text() for p in paras))
            else:
                # grab all text after the heading
                texts = []
                for sib in leiras_heading.find_next_siblings():
                    t = clean_text(sib.get_text())
                    if t:
                        texts.append(t)
                leiras = " ".join(texts)
    if not leiras:
        for selector in [
            ".description__text",
            ".listing-description",
            "#listing-description",
            "[data-testid='listing-description']",
            ".js-listing-description",
        ]:
            el = soup.select_one(selector)
            if el:
                leiras = clean_text(el.get_text())
                break
    result["leírás"] = leiras or MISSING

    # Fill result for each parameter field
    for field in PARAM_FIELDS:
        result[field] = param_map.get(field, MISSING)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def expand_patterns(patterns: list[str]) -> list[str]:
    """Expand glob patterns into actual file paths."""
    files = []
    for pattern in patterns:
        expanded = glob.glob(pattern)
        if expanded:
            files.extend(expanded)
        else:
            files.append(pattern)  # keep as-is so we can report the error
    return files


def main():
    parser = argparse.ArgumentParser(
        description="Extract property data from ingatlan.com MHTML files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="FILE",
        help="MHTML file(s) or glob pattern(s), e.g. *.mhtml",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        default=None,
        help="Write JSON output to FILE instead of stdout",
    )
    args = parser.parse_args()

    files = expand_patterns(args.inputs)

    results = []
    for path in files:
        if not os.path.isfile(path):
            print(f"WARNING: file not found: {path}", file=sys.stderr)
            continue
        try:
            html, source_url = extract_html_from_mhtml(path)
            data = extract_data(html, source_url, mhtml_path=path)
            results.append(data)
            print(f"OK: {path}", file=sys.stderr)
        except Exception as exc:
            print(f"ERROR processing {path}: {exc}", file=sys.stderr)

    output_json = json.dumps(results, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Wrote {len(results)} record(s) to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
