"""
check_prefilter_conditions.py — Prefilter feltételek ellenőrzése az ingatlanok.json fájlon.
A feltételek logikája a prefilter.py::get_prefilter_issues() függvényben van definiálva;
ezt hívja get_kizart_set() is.
"""

import argparse
import io
import json
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from scoring import parse_ar, parse_terulet, parse_telek, parse_szobak, get_kor_kategoria
from prefilters import get_prefilter_issues, load_prefilter_config

INPUT_FILE = 'ingatlanok.json'

parser = argparse.ArgumentParser(description="Ellenőrzi az ingatlanok.json-t a prefilters.json egyik konfigurációja alapján.")
parser.add_argument(
    "--prefilter", "-p",
    metavar="LABEL",
    required=True,
    help="A prefilters.json-ban definiált config label (pl. 'Encike ház 1')",
)
args = parser.parse_args()

conditions = load_prefilter_config("prefilters.json", args.prefilter)

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

ok_count = 0
kizart_count = 0

for i, ing in enumerate(data, 1):
    ar       = parse_ar(ing['Ár'])
    cim      = ing.get('cím', '')
    terulet  = parse_terulet(ing['Alapterület'])
    telek    = parse_telek(ing['Telekterület'])
    szobak   = parse_szobak(ing['Szobák'])
    parkolas = ing.get('Parkolás', '')
    kor_raw  = ing.get('Építés éve', '')
    leiras   = ing.get('leírás', '')

    kor_kat, _, kor_ev = get_kor_kategoria(kor_raw, leiras)
    pre1990    = kor_ev < 1991

    issues = get_prefilter_issues(ing, conditions)

    if issues:
        status = '✗ KIZÁRVA: ' + '; '.join(issues)
        kizart_count += 1
    else:
        status = '✓ OK'
        ok_count += 1

    print(f'{i}. {cim}')
    print(f'   Ár: {ar}M | Terület: {terulet} m² | Telek: {telek} m² | Szobák: {szobak} ({ing.get("Szobák", "")})')
    print(f'   Kor: {kor_kat} ({kor_raw}) | Pre-1990: {pre1990}')
    print(f'   Parkolás: {parkolas}')
    print(f'   >>> {status}')
    print()

print(f'=== ÖSSZESÍTŐ: {ok_count} ✓ OK  /  {kizart_count} ✗ KIZÁRVA ===')
