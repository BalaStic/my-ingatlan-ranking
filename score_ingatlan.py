#!/usr/bin/env python3
"""
score_ingatlan.py — Score and rank properties from results.json using the ingatlan ranking prompt.
Outputs to stdout and writes scores_{LABEL}.txt by default. Use -o to specify a different output file.
"""

import argparse
import json
import io
import os
import sys

# ---------------------------------------------------------------------------
# Parameter definitions — keep the kizart set dynamic
# ---------------------------------------------------------------------------

def parse_ar(ar_str):
    ar_ertek = ar_str.replace(' millió Ft', '').replace(',', '.').split()[0].strip()
    return float(ar_ertek)

def parse_terulet(t):
    return int(t.replace(' m2', '').strip()) if t and 'nincs' not in t.lower() else 0

def parse_telek(t):
    return int(t.replace(' m2', '').strip()) if t and 'nincs' not in t.lower() else 0

def parse_szobak(szobak_str, leiras=''):
    """A fél szobát egésznek számoljuk"""
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

def get_kor_kategoria(kor_str, leiras=''):
    """Visszaadja a kor kategóriát és pontszámot"""
    if 'nincs megadva' in kor_str.lower():
        if 'múlt század első felében' in leiras.lower():
            return '1990 előtt', 1
        if '1994' in leiras or '1992' in leiras:
            return '1991-2000', 3
        return 'Ismeretlen', 2  # közepes
    if '1950 és 1980' in kor_str:
        return '1990 előtt', 1
    if '1981 és 2000' in kor_str:
        return '1991-2000', 3
    if '2001 és 2010' in kor_str:
        return '2001-2009', 4
    for year in range(2010, 2030):
        if str(year) in kor_str:
            return '2010 után', 5
    return 'Ismeretlen', 2

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
    """Energiahatékonyság pontozása"""
    futes = ing.get('Fűtés', '').lower()
    napelem = ing.get('Napelem', '').lower()
    szigeteles = ing.get('Szigetelés', '').lower()
    energetika = ing.get('Energetikai tanúsítvány', '').lower()
    klima = ing.get('Légkondicionáló', '').lower()
    
    pont = 2  # alapértelmezett közepes
    
    if 'van' in napelem:
        pont += 2
    if 'van' in szigeteles:
        if '15' in szigeteles:
            pont += 2
        elif '10' in szigeteles:
            pont += 1
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
    if 'c' in energetika or 'b' in energetika:
        pont += 1
    if 'a' in energetika and 'nincs' not in energetika:
        pont += 2
    
    return max(1, min(8, pont))

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
    """Extra funkciók pontozása (súly: 1)"""
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
    return pont

def get_kulcsszo_pont(leiras):
    """Kulcsszavak a leírásban"""
    pont = 0
    l = leiras.lower()
    if 'modern' in l: pont += 1
    if 'igényes' in l: pont += 1
    if 'szép' in l: pont += 1
    if 'korszerű' in l: pont += 1
    if 'antik' in l: pont -= 1
    if 'cserépkályha' in l: pont -= 1
    if 'kemence' in l: pont -= 1
    return pont

def get_egyedi_jellemzo(ing):
    """Egyedi jellemzők"""
    jellemzok = []
    pince = ing.get('Pince', '').lower()
    if 'van' in pince:
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
    if 'kandalló' in leiras.lower():
        jellemzok.append('kandalló')
    if 'fúrt kút' in leiras.lower():
        jellemzok.append('fúrt kút')
    if 'medence' in leiras.lower():
        jellemzok.append('medence')
    szintek = ing.get('Épület szintjei', '')
    if 'három' in szintek or '3' in szintek:
        jellemzok.append('többszintes')
    if 'négy' in szintek or '4' in szintek:
        jellemzok.append('többszintes')
    if 'kétgenerációs' in leiras.lower() or 'többgenerációs' in leiras.lower():
        jellemzok.append('többgenerációs kialakítás')
    return jellemzok

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
            w = cfg['weights']
            return w, cfg.get('description', '')
    # Config label not found — list available labels
    available = [c.get('label', '?') for c in configs]
    print(f"HIBA: A(z) '{config_label}' konfiguráció nem található a(z) {config_file} fájlban.", file=sys.stderr)
    print(f"Elérhető konfigurációk: {', '.join(available)}", file=sys.stderr)
    sys.exit(1)

def get_kizart_set(data):
    """Detect properties that fail hard constraints. Returns set of 0-based indices."""
    kizart = set()
    for i, ing in enumerate(data):
        ar = parse_ar(ing['Ár'])
        terulet = parse_terulet(ing['Alapterület'])
        szobak = parse_szobak(ing['Szobák'])
        parkolas = ing.get('Parkolás', '').lower()
        cim = ing.get('cím', '')
        
        if ar > 150:
            kizart.add(i)
        if 'Budapest' not in cim:
            kizart.add(i)
        if terulet < 120:
            kizart.add(i)
        if 'önálló garázs' not in parkolas:
            kizart.add(i)
        if szobak < 5:
            kizart.add(i)
    return kizart

# ---------------------------------------------------------------------------
# Main scoring and output
# ---------------------------------------------------------------------------

def main() -> str:
    parser = argparse.ArgumentParser(
        description="Score and rank properties from results.json using the ingatlan ranking prompt.",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        default=None,
        help="Output file (default: scores_{LABEL}.txt, e.g. scores_default.txt)",
    )
    parser.add_argument(
        "--input", "-i",
        metavar="FILE",
        default="ingatlanok.json",
        help="Input JSON file (default: ingatlanok.json)",
    )
    parser.add_argument(
        "--config", "-c",
        metavar="LABEL",
        default="default",
        help="Config label to use from scoring_config.json (default: default)",
    )
    parser.add_argument(
        "--config-file",
        metavar="FILE",
        default="scoring_config.json",
        help="JSON file with scoring weight configs (default: scoring_config.json)",
    )
    args = parser.parse_args()

    # Default output file: scores_{LABEL}.txt
    if args.output is None:
        args.output = f"scores_{args.config}.txt"

    weights, config_desc = load_weights(args.config_file, args.config)

    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    kizart = get_kizart_set(data)
    
    # Build output in a StringIO
    out = io.StringIO()
    p = lambda *a, **kw: print(*a, **kw, file=out)
    
    p(f"=== INGATLANOK ELEMZÉSE (súlyok: {args.config}) ===\n")
    
    results = []
    for i, ing in enumerate(data):
        if i in kizart:
            continue
        
        ar = parse_ar(ing['Ár'])
        terulet = parse_terulet(ing['Alapterület'])
        telek = parse_telek(ing['Telekterület'])
        szobak = parse_szobak(ing['Szobák'])
        kor_kat, kor_pont = get_kor_kategoria(ing['Építés éve'], ing.get('leírás', ''))
        allapot_pont = get_allapot_pont(ing.get('Ingatlan állapota', ''))
        energetika_pont = get_energetika_pont(ing)
        udvar_pont = get_udvar_pont(telek, terulet)
        extra_pont = get_extra_pont(ing)
        kulcsszo_pont = get_kulcsszo_pont(ing.get('leírás', ''))
        egyedi = get_egyedi_jellemzo(ing)
        
        terulet_pont = min(5, terulet / 50)
        
        total = (
            kor_pont * weights['kor'] +
            terulet_pont * weights['terulet'] +
            allapot_pont * weights['allapot'] +
            energetika_pont * weights['energetika'] +
            udvar_pont * weights['udvar'] +
            extra_pont * weights['extra'] +
            kulcsszo_pont * weights['kulcsszo']
        )
        
        nm_ar = ar / terulet * 1000000 if terulet > 0 else 0
        
        pre1990 = '1990 előtt' in kor_kat
        post2000 = '2001-2009' in kor_kat or '2010 után' in kor_kat
        
        results.append({
            'index': i+1,
            'cim': ing['cím'],
            'link': ing.get('link', ''),
            'ar': ar,
            'terulet': terulet,
            'telek': telek,
            'szobak': szobak,
            'nm_ar': nm_ar,
            'kor_kat': kor_kat,
            'kor_pont': kor_pont,
            'allapot_pont': allapot_pont,
            'allapot': ing.get('Ingatlan állapota', ''),
            'energetika_pont': energetika_pont,
            'udvar_pont': udvar_pont,
            'extra_pont': extra_pont,
            'kulcsszo_pont': kulcsszo_pont,
            'total': total,
            'pre1990': pre1990,
            'post2000': post2000,
            'egyedi': egyedi,
            'futes': ing.get('Fűtés', ''),
            'napelem': ing.get('Napelem', ''),
            'szigeteles': ing.get('Szigetelés', ''),
            'energetika': ing.get('Energetikai tanúsítvány', ''),
            'klima': ing.get('Légkondicionáló', ''),
            'leiras': ing.get('leírás', ''),
            'parkolas': ing.get('Parkolás', ''),
            'epites_eve': ing.get('Építés éve', ''),
            'epites_eve_raw': ing.get('Építés éve', ''),
        })
    
    # Rendezés pontszám szerint
    results.sort(key=lambda x: x['total'], reverse=True)
    
    # Részletes elemzés rendezett sorrendben
    for rank, r in enumerate(results, 1):
        p(f'#{rank} {r["cim"]}')
        p(f'   Ár: {r["ar"]}M | Terület: {r["terulet"]}m² | Nm-ár: {r["nm_ar"]:,.0f} Ft/m²')
        p(f'   Kor: {r["kor_kat"]} ({r["epites_eve_raw"]}) [{r["kor_pont"]}*{weights["kor"]}]')
        p(f'   Állapot: {r["allapot"]} [{r["allapot_pont"]}*{weights["allapot"]}]')
        p(f'   Terület pont: {r["terulet"]/50:.1f}*{weights["terulet"]} | Energetika: [{r["energetika_pont"]}*{weights["energetika"]}] | Udvar: [{r["udvar_pont"]}*{weights["udvar"]}]')
        p(f'   Extra: [{r["extra_pont"]}*{weights["extra"]}] | Kulcsszó: [{r["kulcsszo_pont"]}*{weights["kulcsszo"]}]')
        p(f'   Egyedi: {r["egyedi"]}')
        p(f'   >>> ÖSSZPONT: {r["total"]:.1f}')
        p()
    
    p("=== RANGSOR PONTSZÁM SZERINT ===\n")
    for rank, r in enumerate(results, 1):
        p(f'{rank}. [{r["total"]:.1f}] {r["cim"]} (Kor: {r["kor_kat"]})')
    
    p("\n=== PRE-1990 vs POST-2000 SZABÁLY ELLENŐRZÉS ===\n")
    p("  PRE-1990:")
    for r in results:
        if r['pre1990']:
            p(f'    {r["cim"]} [{r["total"]:.1f}]')
    p("  POST-2000:")
    for r in results:
        if r['post2000']:
            p(f'    {r["cim"]} [{r["total"]:.1f}]')
    
    p("\n=== KIZÁRT INGATLANOK ===\n")
    for i in kizart:
        ing = data[i]
        p(f'#{i+1} {ing["cím"]} — Alapterület: {ing["Alapterület"]} (< 120 m²)'
          if parse_terulet(ing['Alapterület']) < 120
          else f'#{i+1} {ing["cím"]} — Nem felel meg a hard constraint-eknek')
    
    output_text = out.getvalue()
    
    # Write to file
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_text)
    print(f"Pontszámok elmentve: {args.output}", file=sys.stderr)
    
    # Print to stdout
    print(output_text)
    
    return output_text

if __name__ == "__main__":
    main()