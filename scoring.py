#!/usr/bin/env python3
"""
score_ingatlan.py — Ingatlan pontozó függvények könyvtára.
Importálható modul: from score_ingatlan import ...
A CLI belépési pont: main.py
"""

import json
import math
import os
import re
import sys

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_ar(ar_str):
    ar_ertek = ar_str.replace(' millió Ft', '').replace(',', '.').split()[0].strip()
    return float(ar_ertek)

def parse_terulet(t):
    return int(t.replace(' m2', '').strip()) if t and 'nincs' not in t.lower() else 0

def parse_telek(t):
    return int(t.replace(' m2', '').strip()) if t and 'nincs' not in t.lower() else 0

def parse_szobak(szobak_str, leiras=''):
    """A fél szobát egésznek számoljuk."""
    if not szobak_str or 'nincs' in szobak_str.lower():
        return 0
    parts = szobak_str.replace('+', ' ').split()
    count = 0
    for p in parts:
        if p.isdigit():
            count += int(p)
        elif 'fél' in p:
            count += 1
    return count

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _ev_to_pont(ev: int) -> float:
    """Lineáris pontozás: 1950 → 1.0, 2025 → 5.0"""
    ev_clamped = max(1950, min(2025, ev))
    return 1.0 + (ev_clamped - 1950) / (2025 - 1950) * 4.0

def _kor_kategoria_str(ev: int) -> str:
    """Kategória-szöveg a pre/post flag-ekhez."""
    if ev < 1981:
        return '1981 előtt'
    if ev <= 2000:
        return '1981-2000'
    if ev <= 2010:
        return '2001-2010'
    return '2011 után'

def get_kor_kategoria(kor_str, leiras=''):
    """Visszaadja a kor kategóriát, lineáris pontszámot és a becsült évszámot (1.0–5.0).
    Intervallumnál (pl. '1950 és 1980 között') a középpontot veszi.
    Ismeretlen esetén konzervatív becsléssel él.
    Visszatérés: (kat_str, pont, ev) — ahol ev a pontozáshoz használt év.
    """
    YEAR_RE = re.compile(r'(19[5-9]\d|20[0-2]\d)')

    def _try_precise_year(desc):
        """Próbál precíz évszámot kinyerni a leírásból
        (pl. „1981-ben épült", „2023-as építésű").
        Visszatér az évvel vagy None-nal."""
        precise = re.findall(r'(\d{4})\s*-\s*(?:ben|ban)\s+épült', desc)
        if not precise:
            precise = re.findall(r'(\d{4})\s*-\s*(?:as|es)\s+építésű', desc)
        if not precise:
            precise = re.findall(r'épült\s+(\d{4})\s*-\s*(?:ban|ben)', desc)
        if precise:
            evek = [int(y) for y in precise if 1945 <= int(y) <= 2030]
            if evek:
                return int(round(sum(evek) / len(evek)))
        return None

    if not kor_str or 'nincs megadva' in kor_str.lower():
        precise_ev = _try_precise_year(leiras)
        if precise_ev is not None:
            return _kor_kategoria_str(precise_ev), _ev_to_pont(precise_ev), precise_ev

        # Fallback: bármilyen 1950–2029 közötti évszám a leírásban
        evek = [int(m) for m in YEAR_RE.findall(leiras)]
        if evek:
            ev = int(round(sum(evek) / len(evek)))
            return _kor_kategoria_str(ev), _ev_to_pont(ev), ev
        if 'múlt század első felében' in leiras.lower():
            return '1981 előtt', _ev_to_pont(1940), 1940
        return 'Ismeretlen', _ev_to_pont(1975), 1975

    match = re.search(r'(\d{4})\s+és\s+(\d{4})', kor_str)
    if match:
        # Intervallum esetén is először próbálj precíz évszámot találni a leírásban
        precise_ev = _try_precise_year(leiras)
        if precise_ev is not None:
            return str(precise_ev), _ev_to_pont(precise_ev), precise_ev

        ev1, ev2 = int(match.group(1)), int(match.group(2))
        midpoint = (ev1 + ev2) / 2
        ev = int(midpoint)  # floor: conservatively use the lower bound for scoring
        display_ev = int(math.ceil(midpoint))  # ceil: display the approximate higher year
        kat = f'~{display_ev}'
        return kat, _ev_to_pont(ev), ev

    years = [int(m) for m in YEAR_RE.findall(kor_str)]
    if years:
        ev = max(years)
        return _kor_kategoria_str(ev), _ev_to_pont(ev), ev

    return 'Ismeretlen', _ev_to_pont(1975), 1975

def get_allapot_pont(allapot):
    a = allapot.lower()
    if 'újszerű' in a:
        return 5
    if 'felújított' in a:
        return 4
    if 'jó állapotú' in a or 'jó állapot' in a:
        return 3
    if 'felújítandó' in a:
        return 1
    return 2

def get_energetika_pont(ing):
    """Energiahatékonyság pontozása."""
    futes      = ing.get('Fűtés', '').lower()
    napelem    = ing.get('Napelem', '').lower()
    szigeteles = ing.get('Szigetelés', '').lower()
    energetika = ing.get('Energetikai tanúsítvány', '').lower()
    klima      = ing.get('Légkondicionáló', '').lower()

    pont = 1

    if 'van' in napelem:
        pont += 2
    if 'van' in szigeteles:
        if '15' in szigeteles:
            pont += 2
        else:
            pont += 1
    if 'hőszivattyú' in futes:
        pont += 3
    elif 'kondenzációs' in futes:
        pont += 2
    elif 'gázkazán' in futes and 'vegyes' not in futes:
        pont += 1
    elif 'konvektor' in futes:
        pont -= 1
    if 'van' in klima:
        pont += 1
    if ('c' in energetika or 'b' in energetika) and 'nincs' not in energetika:
        pont += 1
    if 'a' in energetika and 'nincs' not in energetika:
        pont += 2

    cap = 5 if 'hőszivattyú' in futes else 4
    return max(1, min(cap, pont))

def get_udvar_pont(telek, terulet):
    kert = telek - terulet
    if kert <= 0:
        return 1
    if kert > 300:
        return 5
    if kert > 150:
        return 4
    if kert > 50:
        return 3
    return 2

def get_extra_pont(ing):
    """Extra funkciók pontozása."""
    pont = 0
    if ing.get('Akadálymentesített', '').lower() == 'igen':
        pont += 1
    if 'beépített' in ing.get('Tetőtér', '').lower():
        pont += 1
    if ing.get('Légkondicionáló', '').lower() == 'van':
        pont += 1
    furdo = ing.get('Fürdő és wc', '').lower()
    if 'külön és egyben is' in furdo:
        pont += 1
    leiras = ing.get('leírás', '').lower()
    if 'riasztó' in leiras:
        pont += 1
    if 'öntöző' in leiras:
        pont += 1
    return min(5, pont)

def get_kulcsszo_pont(leiras):
    """Kulcsszavak a leírásban."""
    pont = 0
    l = leiras.lower()
    if 'modern' in l:       pont += 1
    if 'igényes' in l:      pont += 1
    if 'szép' in l:         pont += 1
    if 'korszerű' in l:     pont += 1
    if 'antik' in l:        pont -= 1
    if 'cserépkályha' in l: pont -= 1
    if 'kemence' in l:      pont -= 1
    return pont

def get_egyedi_jellemzo(ing):
    """Egyedi jellemzők."""
    jellemzok = []
    if 'van' in ing.get('Pince', '').lower():
        jellemzok.append('pince')
    tetoter = ing.get('Tetőtér', '').lower()
    if 'beépített' in tetoter:
        jellemzok.append('beépített tetőtér')
    elif 'beépíthető' in tetoter:
        jellemzok.append('beépíthető tetőtér')
    if ing.get('Napelem', '').lower() == 'van':
        jellemzok.append('napelem')
    if ing.get('Akadálymentesített', '').lower() == 'igen':
        jellemzok.append('akadálymentesített')
    leiras = ing.get('leírás', '')
    if 'kandalló' in leiras.lower():     jellemzok.append('kandalló')
    if 'fúrt kút' in leiras.lower():    jellemzok.append('fúrt kút')
    if 'medence' in leiras.lower():     jellemzok.append('medence')
    szintek = ing.get('Épület szintjei', '')
    if 'három' in szintek or '3' in szintek:
        jellemzok.append('többszintes')
    if 'négy' in szintek or '4' in szintek:
        jellemzok.append('többszintes')
    if 'kétgenerációs' in leiras.lower() or 'többgenerációs' in leiras.lower():
        jellemzok.append('többgenerációs kialakítás')
    return jellemzok

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_weights(config_file, config_label):
    """Load scoring weights from a JSON config file. Returns (weights_dict, description)."""
    if not os.path.isfile(config_file):
        print(f"HIBA: A konfigurációs fájl nem található: {config_file}", file=sys.stderr)
        sys.exit(1)
    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    configs = config_data.get('configs', [])
    for cfg in configs:
        if cfg.get('label') == config_label:
            return cfg['weights'], cfg.get('description', '')
    available = [c.get('label', '?') for c in configs]
    print(f"HIBA: A(z) '{config_label}' konfiguráció nem található a(z) {config_file} fájlban.", file=sys.stderr)
    print(f"Elérhető konfigurációk: {', '.join(available)}", file=sys.stderr)
    sys.exit(1)

