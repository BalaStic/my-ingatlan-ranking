#!/usr/bin/env python3
"""
main.py — CLI belépési pont az ingatlan pontozáshoz és rangsoroláshoz.
Bemenet: JSON/ingatlanok.json, kimenet: ranked_{LABEL}.txt

Használat:
  python main.py -i JSON/ingatlanok.json -c most_modern
  python main.py -i masik_adatok.json -c legmodernebb -p "Balázs lakás 1"
"""

import argparse
import io
import json
import os
import shutil
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from scoring import (
    parse_ar, parse_terulet, parse_telek, parse_szobak,
    get_kor_kategoria, get_allapot_pont, get_energetika_pont,
    get_udvar_pont, get_extra_pont, get_kulcsszo_pont,
    get_egyedi_jellemzo, load_weights,
)
from prefilters import get_kizart_set, get_prefilter_issues, load_prefilter_config
from rankrules import apply_ranking_rules


def main() -> str:
    parser = argparse.ArgumentParser(
        description="Score and rank properties from a JSON input file using the ingatlan ranking prompt.",
    )
    parser.add_argument(
        "--input", "-i",
        metavar="FILE",
        required=True,
        help="Input JSON file (e.g. JSON/ingatlanok.json)",
    )
    parser.add_argument(
        "--config", "-c",
        metavar="LABEL",
        required=True,
        help="Config label to use from scoring_config.json",
    )
    parser.add_argument(
        "--config-file",
        metavar="FILE",
        default="JSON/scoring_config.json",
        help="JSON file with scoring weight configs (default: JSON/scoring_config.json)",
    )
    parser.add_argument(
        "--prefilter", "-p",
        metavar="LABEL",
        default=None,
        help="Prefilter config label to use from prefilters.json (disables prefilter if not provided)",
    )
    parser.add_argument(
        "--enable-reranking",
        action="store_true",
        help="Enable final reranking based on ranking rules",
    )
    args = parser.parse_args()

    args.output = f"ranked_{args.config}.txt"

    weights, config_desc = load_weights(args.config_file, args.config)

    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if args.prefilter:
        conditions = load_prefilter_config("JSON/prefilters.json", args.prefilter)
        kizart = get_kizart_set(data, conditions)
        with open("JSON/prefilters.json", 'r', encoding='utf-8') as f:
            prefilter_data = json.load(f)
        selected_prefilter_config = next(
            (c for c in prefilter_data['configs'] if c['label'] == args.prefilter), None
        )
    else:
        kizart = set()
        selected_prefilter_config = None

    out = io.StringIO()
    p = lambda *a, **kw: print(*a, **kw, file=out)

    p(f"=== INGATLANOK ELEMZÉSE (súlyok: {args.config}) ===\n")

    results = []
    for i, ing in enumerate(data):
        if i in kizart:
            continue

        ar           = parse_ar(ing['Ár'])
        terulet      = parse_terulet(ing['Alapterület'])
        telek        = parse_telek(ing['Telekterület'])
        szobak       = parse_szobak(ing['Szobák'])
        kor_kat, kor_pont, kor_ev = get_kor_kategoria(ing['Építés éve'], ing.get('leírás', ''))
        allapot_pont = get_allapot_pont(ing.get('Ingatlan állapota', ''))
        energetika_pont = get_energetika_pont(ing)
        udvar_pont   = get_udvar_pont(telek, terulet)
        extra_pont   = get_extra_pont(ing)
        kulcsszo_pont = get_kulcsszo_pont(ing.get('leírás', ''))
        egyedi       = get_egyedi_jellemzo(ing)

        terulet_pont = min(5, terulet / 45)

        total = (
            kor_pont      * weights['kor'] +
            terulet_pont  * weights['terulet'] +
            allapot_pont  * weights['allapot'] +
            energetika_pont * weights['energetika'] +
            udvar_pont    * weights['udvar'] +
            extra_pont    * weights['extra'] +
            kulcsszo_pont * weights['kulcsszo']
        )
        max_pont = 5 * sum(weights.values())
        pct  = total / max_pont * 100 if max_pont > 0 else 0
        nm_ar = ar / terulet * 1_000_000 if terulet > 0 else 0

        pre1990  = kor_ev < 1991
        post2000 = kor_ev > 2000

        results.append({
            'index': i + 1,
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
            'pct': pct,
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
            'epites_eve_raw': ing.get('Építés éve', ''),
        })

    # Rendezés pontszám szerint, majd végső rangsorolási szabályok alkalmazása
    results.sort(key=lambda x: x['total'], reverse=True)
    if args.enable_reranking:
        results = apply_ranking_rules(results)

    # Részletes elemzés rendezett sorrendben (első 10 részletesen)
    for rank, r in enumerate(results, 1):
        if rank > 10:
            break
        p(f'#{rank} {r["cim"]}')
        p(f'   Ár: {r["ar"]}M | Terület: {r["terulet"]}m² | Nm-ár: {r["nm_ar"]:,.0f} Ft/m²')
        p(f'   Kor: {r["kor_kat"]} ({r["epites_eve_raw"]}) [{r["kor_pont"]}*{weights["kor"]}]')
        p(f'   Állapot: {r["allapot"]} [{r["allapot_pont"]}*{weights["allapot"]}]')
        p(f'   Terület pont: {min(5, r["terulet"]/45):.1f}*{weights["terulet"]} | Energetika: [{r["energetika_pont"]}*{weights["energetika"]}] | Udvar: [{r["udvar_pont"]}*{weights["udvar"]}]')
        p(f'   Extra: [{r["extra_pont"]}*{weights["extra"]}] | Kulcsszó: [{r["kulcsszo_pont"]}*{weights["kulcsszo"]}]')
        p(f'   Egyedi: {r["egyedi"]}')
        p(f'   >>> ÖSSZPONT: {r["total"]:.1f} ({r["pct"]:.1f}%)')
        p()

    p("=== RANGSOR PONTSZÁM SZERINT ===\n")
    for rank, r in enumerate(results, 1):
        p(f'{rank}. [{r["total"]:.1f} / {r["pct"]:.1f}%] {r["cim"]} (Kor: {r["kor_kat"]})')

    if kizart:
        p("\n=== KIZÁRT INGATLANOK ===\n")
        for i in sorted(kizart):
            ing = data[i]
            issues = get_prefilter_issues(ing, conditions)
            p(f'#{i+1} {ing["cím"]}')
            for issue in issues:
                p(f'    — {issue}')

    output_text = out.getvalue()

    folder_name = f"ranked_{args.config}"
    if os.path.exists(folder_name):
        shutil.rmtree(folder_name)
    os.makedirs(folder_name, exist_ok=True)

    out_filename = os.path.basename(args.output)
    out_path = os.path.join(folder_name, out_filename)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(output_text)
    print(f"Pontszámok elmentve: {out_path}", file=sys.stderr)

    files_to_copy = [
        "JSON/scoring_config.json",
        "PROMPTS/ranking_report_PROMPT.md",
        "PROMPTS/scoring.md"
    ]
    if args.prefilter and selected_prefilter_config:
        prefilter_out_path = os.path.join(folder_name, "prefilter.json")
        with open(prefilter_out_path, 'w', encoding='utf-8') as f:
            json.dump(selected_prefilter_config, f, ensure_ascii=False, indent=2)
        print(f"Prefilter config elmentve: {prefilter_out_path}", file=sys.stderr)
    if args.enable_reranking:
        files_to_copy.extend(["rankrules.md", "rankrules.py"])
        
    for file in files_to_copy:
        if os.path.exists(file):
            shutil.copy(file, folder_name)
        else:
            print(f"Figyelmeztetés: {file} nem található, így nem lett átmásolva.", file=sys.stderr)

    # Filtered input JSON — top 10 ranked items
    top10_indices = [r['index'] - 1 for r in results[:10]]
    filtered = [data[i] for i in top10_indices]
    filtered_json_path = os.path.join(folder_name, "ranked_ingatlanok.json")
    with open(filtered_json_path, 'w', encoding='utf-8') as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)
    print(f"Szűrt ingatlanok JSON elmentve: {filtered_json_path}", file=sys.stderr)

    print(output_text)
    return output_text


if __name__ == "__main__":
    main()
