"""
prefilters.py — Prefilter feltételek dinamikus kiértékelése a prefilters.json alapján.
Ezt importálja mind a main.py (get_kizart_set), mind a check_prefilter_conditions.py (get_prefilter_issues).
"""

import json
import os
import re
import sys
from scoring import parse_ar, parse_terulet, parse_telek, parse_szobak, get_kor_kategoria

def _parse_kor_range(kor_str):
    """Parse a kor condition string like '1981-2000 között' or '2011 után' into (min_year, max_year)."""
    kor_str = kor_str.lower()
    match = re.match(r'(\d{4})\s*[-–]\s*(\d{4})\s*között', kor_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.match(r'(\d{4})\s*előtt', kor_str)
    if match:
        return 1950, int(match.group(1)) - 1
    match = re.match(r'(\d{4})\s*után', kor_str)
    if match:
        return int(match.group(1)), 2025
    return None, None

def load_prefilter_config(config_file, config_label):
    """Load a specific prefilter configuration from the JSON file."""
    if not os.path.isfile(config_file):
        print(f"HIBA: A prefilter konfigurációs fájl nem található: {config_file}", file=sys.stderr)
        sys.exit(1)
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
        
    configs = config_data.get('configs', [])
    for cfg in configs:
        if cfg.get('label') == config_label:
            conditions = cfg.get('conditions', {})
            # Normalize "ingatlan_jellege": remove "építésű" word so
            # e.g. "tégla építésű lakás" becomes "tégla lakás" matching the "típus" field
            if 'ingatlan_jellege' in conditions:
                jellege = conditions['ingatlan_jellege']
                if isinstance(jellege, list):
                    conditions['ingatlan_jellege'] = [
                        re.sub(r'\s*építésű\s*', ' ', j).strip() for j in jellege
                    ]
                elif isinstance(jellege, str):
                    conditions['ingatlan_jellege'] = re.sub(r'\s*építésű\s*', ' ', jellege).strip()
            return conditions
            
    available = [c.get('label', '?') for c in configs]
    print(f"HIBA: A(z) '{config_label}' prefilter konfiguráció nem található a(z) {config_file} fájlban.", file=sys.stderr)
    print(f"Elérhető prefilter konfigurációk: {', '.join(available)}", file=sys.stderr)
    sys.exit(1)

def _check_min_max(value, condition):
    """Helper to check if a numeric value satisfies a min/max condition."""
    if not condition:
        return True
    
    if 'min' in condition and value < condition['min']:
        return False
    if 'max' in condition and value > condition['max']:
        return False
    return True

def get_prefilter_issues(ing, conditions):
    """Return a list of human-readable strings describing which prefilter conditions
    the given property fails. An empty list means the property passes all conditions."""
    issues = []
    
    try:
        ar       = parse_ar(ing.get('Ár', ''))
        terulet  = parse_terulet(ing.get('Alapterület', ''))
        telek    = parse_telek(ing.get('Telekterület', ''))
        szobak   = parse_szobak(ing.get('Szobák', ''))
        leiras   = ing.get('leírás', '').lower()
    except Exception:
        issues.append('Hiba az ingatlan adatainak feldolgozása közben')
        return issues

    parkolas = ing.get('Parkolás', '').lower()
    cim      = ing.get('cím', '')
    allapot  = ing.get('Ingatlan állapota', '').lower()

    # 1. Ár ellenőrzés
    if 'ár' in conditions:
        ar_cond = conditions['ár']
        if not _check_min_max(ar, ar_cond):
            issues.append(f"Ár nem megfelelő: {ar}M (Elvárt: {ar_cond})")

    # 2. Kerületek / Cím ellenőrzés
    if 'kerületek' in conditions:
        allowed_districts = conditions['kerületek']
        # Extract roman numeral if present in cim, e.g. "Budapest XVIII. kerület" -> "XVIII. kerület"
        found = False
        cim_lower = cim.lower()
        for district in allowed_districts:
            # Use negative lookbehind to avoid substring false positives:
            # e.g. "X. kerület" must NOT match inside "XX. kerület"
            pattern = r'(?<![A-Za-z])' + re.escape(district.lower())
            if re.search(pattern, cim_lower):
                found = True
                break
        
        # If specific districts are defined, and the property isn't in any of them, exclude it.
        # However, if it's outside Budapest completely, the prompt usually just checked "Budapest".
        # If 'kerületek' is provided, we strictly check for those districts.
        if not found and 'Budapest' in cim:
             issues.append(f"Kerület nem megfelelő: {cim}")
        elif 'Budapest' not in cim:
             issues.append('Nem budapesti')

    # 3. Alapterület ellenőrzés
    if 'alapterület' in conditions:
        if not _check_min_max(terulet, conditions['alapterület']):
            issues.append(f"Alapterület nem megfelelő: {terulet} m²")

    # 4. Telek méret ellenőrzés
    if 'telek_méret' in conditions:
        if not _check_min_max(telek, conditions['telek_méret']):
            issues.append(f"Telek mérete nem megfelelő: {telek} m²")

    # 5. Szobák száma
    if 'szobák_száma' in conditions:
        szoba_cond = conditions['szobák_száma']
        if not _check_min_max(szobak, szoba_cond):
            issues.append(f"Szobák száma nem megfelelő: {szobak}")

    # 6. Állapot
    if 'állapot' in conditions:
        allowed_states = [s.lower() for s in conditions['állapot']]
        # If condition is an array and current state is not among them
        if allapot and allapot not in allowed_states:
            # Sometimes 'újszerű' could be inside the description, but usually it's in the field
            issues.append(f"Állapot nem megfelelő: {allapot}")

    # 7. Parkolás / Garázs (Text array or string)
    if 'parkolás' in conditions:
        parkolas_conds = conditions['parkolás']
        if isinstance(parkolas_conds, list):
            if not any(p.lower() in parkolas for p in parkolas_conds):
                issues.append(f"Parkolás nem megfelelő: {parkolas}")
        elif isinstance(parkolas_conds, str):
            if parkolas_conds.lower() not in parkolas:
                issues.append(f"Parkolás nem megfelelő: {parkolas}")
                
    if 'garázs' in conditions:
        garazs_conds = conditions['garázs']
        if isinstance(garazs_conds, list):
            if not any(g.lower() in parkolas for g in garazs_conds):
                issues.append(f"Garázs nem megfelelő: {parkolas}")
        elif isinstance(garazs_conds, str):
            if garazs_conds.lower() not in parkolas:
                issues.append(f"Garázs nem megfelelő: {parkolas}")

    # 8. Ingatlan típusa (eladó / kiadó)
    if 'ingatlan_típusa' in conditions:
        tipus_cond = conditions['ingatlan_típusa'].lower()
        tipus_field = ing.get('típus', '').lower()
        if tipus_field:
            # Use the "típus" field (e.g. "Eladó tégla lakás", "Kiadó családi ház")
            if tipus_cond == 'eladó' and not tipus_field.startswith('eladó'):
                issues.append(f"Ingatlan típusa nem eladó: {tipus_field}")
            elif tipus_cond == 'kiadó' and not tipus_field.startswith('kiadó'):
                issues.append(f"Ingatlan típusa nem kiadó: {tipus_field}")
        else:
            # Fallback: old heuristic based on Ár string
            ar_str = ing.get('Ár', '').lower()
            if tipus_cond == 'eladó' and 'millió' not in ar_str:
                issues.append(f"Ingatlan típusa nem eladó: {ar_str}")
            elif tipus_cond == 'kiadó' and 'millió' in ar_str:
                issues.append(f"Ingatlan típusa nem kiadó: {ar_str}")

    # 9. Kategória (lakás / ház)
    if 'kategória' in conditions:
        kat = conditions['kategória'].lower()
        tipus_field = ing.get('típus', '').lower()
        if tipus_field:
            # Use the "típus" field (e.g. "Eladó tégla lakás", "Eladó családi ház")
            if kat == 'lakás':
                if 'lakás' not in tipus_field:
                    issues.append(f"Kategória nem lakás (típus: {tipus_field})")
            elif kat == 'ház':
                if 'ház' not in tipus_field:
                    issues.append(f"Kategória nem ház (típus: {tipus_field})")
        else:
            # Fallback: old heuristic based on telek
            if kat == 'lakás':
                if telek > 0:
                    issues.append(f"Kategória nem lakás (van telek: {telek} m²)")
            elif kat == 'ház':
                if telek == 0:
                    issues.append(f"Kategória nem ház (nincs telek)")

    # 10. Kor (építés éve)
    if 'kor' in conditions:
        kor_kat, kor_pont, kor_ev = get_kor_kategoria(ing.get('Építés éve', ''), leiras)
        kor_allowed = conditions['kor']
        if isinstance(kor_allowed, list):
            found_kor = False
            for kr_str in kor_allowed:
                min_ev, max_ev = _parse_kor_range(kr_str)
                if min_ev is not None and min_ev <= kor_ev <= max_ev:
                    found_kor = True
                    break
            if not found_kor:
                issues.append(f"Kor nem megfelelő: {kor_kat} (~{kor_ev}) (Elvárt: {kor_allowed})")

    # 11. Komfort
    if 'komfort' in conditions:
        komfort_str = ing.get('Komfort', '').lower()
        allowed_komfort = [k.lower() for k in conditions['komfort']]
        if komfort_str and komfort_str != 'nincs megadva':
            if komfort_str not in allowed_komfort:
                issues.append(f"Komfort nem megfelelő: {komfort_str}")

    # 12. Ingatlan jellege (pl. tégla lakás, családi ház)
    if 'ingatlan_jellege' in conditions:
        jellege_conds = conditions['ingatlan_jellege']
        tipus_field = ing.get('típus', '').lower()
        if tipus_field:
            # Use the "típus" field (e.g. "Eladó tégla lakás", "Eladó családi ház")
            if isinstance(jellege_conds, list):
                if not any(j.lower() in tipus_field for j in jellege_conds):
                    issues.append(f"Ingatlan jellege nem megfelelő (típus: {tipus_field}, elvárt: {jellege_conds})")
            elif isinstance(jellege_conds, str):
                if jellege_conds.lower() not in tipus_field:
                    issues.append(f"Ingatlan jellege nem megfelelő (típus: {tipus_field}, elvárt: {jellege_conds})")
        else:
            # Fallback: search in description
            if isinstance(jellege_conds, list):
                if not any(j.lower() in leiras for j in jellege_conds):
                    issues.append(f"Ingatlan jellege nem megfelelő (leírásban nincs: {jellege_conds})")
            elif isinstance(jellege_conds, str):
                if jellege_conds.lower() not in leiras:
                    issues.append(f"Ingatlan jellege nem megfelelő: {jellege_conds}")

    return issues

def get_kizart_set(data, conditions):
    """Detect properties that fail the prefilter conditions. Returns set of 0-based indices."""
    if not conditions:
        return set()
    return {i for i, ing in enumerate(data) if get_prefilter_issues(ing, conditions)}
