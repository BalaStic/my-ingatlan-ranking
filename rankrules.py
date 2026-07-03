"""
rankrules.py — Végső rangsorolási szabályok alkalmazása.

A scoring.py által pontszám szerint rendezett listára alkalmazza
a speciális rangsorolási feltételeket. Az itt definiált függvények sorrendben
kerülnek meghívásra az apply_ranking_rules() orchestratoron keresztül.
"""


def apply_pre1990_rule(results):
    """
    Egy 1990 előtt épült ingatlan NEM előzhet meg egy 2000 után épültet
    az összesített rangsorban.

    Az input már pontszám szerint csökkenő sorrendben van.
    Megvalósítás: három csoportra bontás a pre1990 és post2000 flag-ek alapján:
      - post2000 (2001 után) — elöl
      - middle (1991–2000) — középen, szabadon rangsorolnak
      - pre1990 — hátul
    A relatív sorrend (pontszám alapján) minden csoporton belül megmarad.
    """
    post2000 = [r for r in results if r['post2000']]
    middle   = [r for r in results if not r['pre1990'] and not r['post2000']]
    pre1990  = [r for r in results if r['pre1990']]
    return post2000 + middle + pre1990


def apply_ranking_rules(results):
    """
    Összes végső rangsorolási szabály alkalmazása — orchestrator.

    A results lista már pontszám szerint rendezett (scoring.py adja át).
    Ide kerüljenek a jövőbeni új szabályok is: adj hozzá újabb
    apply_*_rule() hívást sorban.
    """
    results = apply_pre1990_rule(results)
    return results
