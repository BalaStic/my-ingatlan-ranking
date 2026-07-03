# Ingatlan Scorer — Chrome Extension

Google Chrome bővítmény, amely ingatlan.com hirdetésoldalon egyetlen kattintással kiszámítja az ingatlan pontszámát a `scoring_config.json`-ban definiált súlyok alapján.

## Cél

Automatizálja a `scoring.py` logikáját böngészőben: nem kell MHTML-t letölteni, JSON-t konvertálni és Python-t futtatni — elég megnyitni a hirdetést, és kattintani a bővítmény gombjára.

## Funkciók

- **Pontozás egy kattintásra** — az oldal adataiból azonnal kiszámítja az összpontszámot és a relatív %-ot
- **Scorecard befűzése az oldalba** — a pontszám táblázat megjelenik a hirdetés tetején
- **Több config támogatás** — a popupban választható, melyik súlykonfiguráció alapján pontozzon (pl. `Balázs`, `Enikő`)
- **Relatív % pontszám** — különböző súlyösszegű configok pontszámai közvetlenül összehasonlíthatók
- **Auto MHTML mentés** (opcionális) — a pontozás után automatikusan elmenti az oldalt `.mhtml` formátumban a `python ingatlan_com_MHTML_to_JSON.py` pipeline-hoz

## Telepítés

1. Nyisd meg: `chrome://extensions/`
2. Kapcsold be a **Fejlesztői módot** (jobb felső sarok)
3. Kattints: **Kicsomagolt bővítmény betöltése**
4. Válaszd ki a `chrome_extension/` mappát

## Használat

1. Nyisson meg egy ingatlan.com hirdetést
2. Kattints a bővítmény ikonra a böngésző eszköztárán
3. Válassz súlykonfigurációt (pl. `baazs` vagy `encike`)
4. Kattints a **Pontozás** gombra
5. A scorecard megjelenik az oldalon, a popup bezárul

## Súlyok frissítése

A `scoring_config.json` a gyökér mappában van. Ha módosítod, másold át a bővítmény mappájába:

```bat
copy_ScoreConfig_JSON_to_chrome_extension.bat
```

Majd töltsd újra a bővítményt: `chrome://extensions/` → 🔄 **Reload**

## Fájlok

| Fájl | Leírás |
|---|---|
| `manifest.json` | Extension konfiguráció (MV3) |
| `popup.html` / `popup.js` | Felhasználói felület |
| `content.js` | Oldal scraping + scorecard injektálás |
| `scoring.js` | Pontozási logika (portolva `scoring.py`-ból) |
| `background.js` | MHTML mentés service worker (chrome.debugger API) |
| `scoring_config.json` | Súlykonfigurációk másolata |
