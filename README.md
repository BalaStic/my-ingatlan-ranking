# Ingatlan Ranking

Ingatlan hirdetések pontozása és rangsorolása konfigurálható súlyokkal, az `ingatlan_ranking_PROMPT.txt`-ben definiált preferenciák alapján.

## Fájlstruktúra

| Fájl | Leírás |
|---|---|
| `score_ingatlan.py` | Fő pontozó és rangsoroló script. Bemenet: `ingatlanok.json`, kimenet: `scores_{LABEL}.txt` |
| `scoring_config.json` | Súlykonfigurációk (több `label`-lel). A `score_ingatlan.py` innen olvassa a súlyokat |
| `ingatlanok.json` | Az ingatlan hirdetések adatai JSON formátumban |
| `ingatlan_com_MHTML_to_JSON.py` | MHTML fájlokból nyeri ki az ingatlan adatokat és menti JSON-ba |
| `check_constraints.py` | Hard constraint-ek ellenőrzése a JSON adatokon |
| `ingatlan_ranking_PROMPT.txt` | A rangsorolási prompt, ami a preferenciákat és szabályokat definiálja |
| `ranking_report_PROMPT.md` | Prompt az AI chatbot számára a végső riport (`ingatlan_rangsor.md`) generálásához |
| `debug_html.py` | HTML debug segédeszköz (MHTML elemzéshez) |
| `test_single.py` | Egyetlen MHTML fájl tesztelése |

## Használat

### Pontozás és rangsorolás

```bash
# Alapértelmezett config (label: "default") → scores_default.txt
python score_ingatlan.py

# Egyedi config választása
python score_ingatlan.py -c most_modern

# Egyedi bemeneti fájl
python score_ingatlan.py -i masik_adatok.json

# Egyedi kimeneti fájl
python score_ingatlan.py -o eredmenyek.txt

# Összes opció együtt
python score_ingatlan.py -i ingatlanok.json -c default -o eredmenyek.txt
```

### Hard constraint-ek ellenőrzése

```bash
python check_constraints.py
```

### MHTML → JSON konvertálás

```bash
python ingatlan_com_MHTML_to_JSON.py
```

## Scoring konfiguráció

A `scoring_config.json` több névvel ellátott (`label`) súlykonfigurációt tartalmaz. A `score_ingatlan.py` a `-c` kapcsolóval kiválasztott label alapján olvassa be a súlyokat.

### Formátum

```json
{
  "configs": [
    {
      "label": "default",
      "description": "Alapértelmezett súlyozás",
      "weights": {
        "kor": 9,
        "terulet": 8,
        "allapot": 7,
        "energetika": 5,
        "udvar": 6,
        "extra": 2,
        "kulcsszo": 2
      }
    }
  ]
}
```

### Súlyok jelentése

| Kulcs | Preferencia | Leírás |
|---|---|---|
| `kor` | Építés éve | 2010 után > 2001-2009 > 1991-2000 > 1990 előtt |
| `terulet` | Alapterület | Nagyobb > kisebb |
| `allapot` | Ingatlan állapota | Újszerű > felújított > jó állapotú > felújítandó |
| `energetika` | Energiahatékonyság | Hőszivattyú+napelem > modern gázkazán > konvektor |
| `udvar` | Udvar / kert mérete | Telekterület - alapterület alapján |
| `extra` | Extra funkciók | Akadálymentesítés, tetőtér, klíma, riasztó, öntöző |
| `kulcsszo` | Kulcsszavak | "modern", "igényes" = +1; "antik", "cserépkályha" = -1 |

### Új konfiguráció hozzáadása

Adj hozzá egy új objektumot a `configs` tömbhöz egyedi `label`-lel és a kívánt `weights` értékekkel (1-10 skálán).

## Teljes munkafolyamat

Az alábbi lépések egy teljes végighasználási példát mutatnak be — az ingatlan hirdetések letöltésétől az olvasható riportig.

### 1. MHTML fájlok letöltése és konvertálása

Töltsd le az ingatlan hirdetési oldalakat MHTML formátumban az `ingatlan_com` mappába, majd konvertáld JSON-ba:

```bash
python ingatlan_com_MHTML_to_JSON.py
```

Ez generálja az `ingatlanok.json` fájlt.

### 2. Pontozás és rangsorolás

Futtasd a pontozó scriptet a kívánt konfigurációval:

```bash
# Alapértelmezett súlyokkal
python score_ingatlan.py -c default

# Vagy egyedi konfigurációval (pl. a "most_modern" label)
python score_ingatlan.py -c most_modern
```

A script generál egy `scores_default.txt` (vagy `scores_{LABEL}.txt`) fájlt, ami tartalmazza:
- Az összes ingatlan részletes pontozását, kategóriákra bontva
- A végső rangsort pontszám szerint
- A pre-1990 vs post-2000 ellenőrzést
- A hard constraint-ek miatt kizárt ingatlanok listáját

### 3. Riport generálás AI chatbot segítségével

Utolsó lépésként egy olvasható, magyar nyelvű riportot (`ingatlan_rangsor.md`) készíthetsz bármely AI chatbot (ChatGPT, Claude, stb.) segítségével. **Másold be a `ranking_report_PROMPT.md` teljes tartalmát** a chatbe, és **csatold hozzá az alábbi 4 fájlt**:

| Fájl | Szerep |
|---|---|
| `scores_default.txt` | A pontozott rangsor (a 2. lépés kimenete) |
| `ingatlanok.json` | A nyers ingatlan adatok (linkek, leírások, műszaki részletek) |
| `ingatlan_ranking_PROMPT.txt` | A rangsorolási módszertan és preferenciák leírása |
| `scoring_config.json` | A használt súlykonfiguráció |

> **Megjegyzés:** A `ranking_report_PROMPT.md` úgy van megírva, hogy bármely AI chatbot megértse a feladatot. Egyszerűen másold be a promptot, csatold a fájlokat, és a chatbot legenerálja az `ingatlan_rangsor.md`-t. A riport a `scores_default.txt` rangsorát követi, az `ingatlanok.json`-ból veszi a linkeket és részletes adatokat, a promptból és configból pedig a módszertant.

## Függőségek

- Python 3.8+
- `beautifulsoup4` — HTML parsing (MHTML feldolgozáshoz)
- `lxml` — HTML parser backend

Telepítés:

```bash
pip install beautifulsoup4 lxml