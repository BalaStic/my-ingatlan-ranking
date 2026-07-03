"""
prefilters.py — Prefilter feltételek dinamikus kiértékelése a prefilters.json alapján.
Ezt importálja mind a main.py (get_kizart_set), mind a check_prefilter_conditions.py (get_prefilter_issues).
"""

import json
import os
import sys
from scoring import parse_ar, parse_terulet, parse_telek, parse_szobak

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
            return cfg.get('conditions', {})
            
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
    
    ar       = parse_ar(ing.get('Ár', ''))
    terulet  = parse_terulet(ing.get('Alapterület', ''))
    telek    = parse_telek(ing.get('Telekterület', ''))
    szobak   = parse_szobak(ing.get('Szobák', ''))
    parkolas = ing.get('Parkolás', '').lower()
    cim      = ing.get('cím', '')
    leiras   = ing.get('leírás', '').lower()
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
        for district in allowed_districts:
            # We lowercase both to do a robust check
            if district.lower() in cim.lower():
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

    return issues

def get_kizart_set(data, conditions):
    """Detect properties that fail the prefilter conditions. Returns set of 0-based indices."""
    if not conditions:
        return set()
    return {i for i, ing in enumerate(data) if get_prefilter_issues(ing, conditions)}
