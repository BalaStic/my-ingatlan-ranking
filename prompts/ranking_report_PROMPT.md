# Feladat

Készítsd el az `ingatlan_rangsor.md` fájlt, amely egy emberi fogyasztásra szánt, magyar nyelvű ingatlan rangsorolási jelentés.

## Bemeneti fájlok (mindet csatolom)

1. **`ranked_<LABEL>.txt`** — egy script által generált pontozott rangsor.
   Ez tartalmazza a végleges sorrendet, a pontszámokat, és az egyes kategóriák 
   részpontszámait (kor, terület, állapot, energetika, udvar, extra, kulcsszó).

2. **`ingatlanok.json`** — az ingatlanok nyers adatai (leírás, ár, alapterület, fűtés típusa,
   szigetelés, napelem, stb.). Innen kell kivenni a részletes leírásokhoz szükséges 
   információkat, linkeket, címeket.

3. **`prefilters.json`**  - Kötelező / kizáró peremfeltételek (prefilter)
  Ellenőrizd, hogy megadta-e a felhasználó.
  Ha nincs megadva, az azt jelenti, hogy lényegtelen, mi volt az előszűrési feltétel, mert a felhasználót csak a rangsorolt ingatlanok érdeklik.
  Ha meg van adva, az azt jelenti, hogy a felhasználó egy scripttel ezen információk alapján előszűrte az ingatlanokat, és ennek megfelelően
  találni fogsz kizárt ingatlanokat. A JSON-ben a paraméterek között min és max értékek, engedélyezett szöveges értékek, kerületek vannak.
  
  Related scripts: `prefilters.py`, `check_prefilter_conditions.py`

4. **`scoring.md`**  - Pontozási döntési fa (pszeudokód)
  A felhasználó egy scripptel ezen információk alapján számította ki a pontszámokat, ami a rangsorolás alapját képezte.
  Ez fontos, ez meghatározza a sorrendet.
  Related scripts: `scoring.py`

5. **`scoring_config.json`** — a súlyok konfigurációja (a "default" label alatt).
  A súlyok a felhasználó fontossági preferenciáit reprezentálják.

6. **`rankrules.md`** - A végső sorrendet befolyásoló szabályok
  Ellenőrizd, hogy megadta-e a felhasználó.
  Ha igen, a felhasználó felülbírálta a pontszámok alapján kialakult rangsort a file-ban lévő szabály(ok) alkalmazásával.
  Related script: `rankrules.py`

## Kimeneti fájl formátuma: `ingatlan_rangsor.md`

A fájl az alábbi szerkezetet kövesse:

### 1. Fő szempontok szekció
- Röviden sorold fel a prefilter feltételeket (a `prefilters.json` alapján)
- Sorold fel a preferenciákat és azok súlyait (a `scoring_config.json` `<LABEL>`
  configja alapján)
- Említsd meg a speciális szabályt: pl. "1990 előtti ház nem előzhet meg 2000 utánit"

### 2. Top 10 rangsorolt ingatlan
- A `ranked_<LABEL>.txt` rangsora alapján, pontszám szerint csökkenőben
- Minden ingatlannál:
  - **Cím, pontszám, link** (az ingatlanok.json-ból)
  - **Ár és négyzetméterár** (a scores-ból, kerekítve)
  - **Kiemelt paraméterek**: alapterület, telek, szobák, kor/állapot, energetika, 
    udvar, garázs — a scores.txt adatai + az ingatlanok.json részletei alapján
  - **Indoklás** (2-4 mondat): miért ezt a helyezést kapta, miben erős/gyenge, 
    hogyan teljesítette a preferenciákat, milyen konkrét műszaki részletek 
    (kazán típusa, szigetelés vastagsága, energetikai tanúsítvány) befolyásolták
  - **Egyedi jellemző**: az ingatlanok.json leírásából kigyűjtött nem szokványos 
    tulajdonságok (pl. pince, napelem, medence, akadálymentesítés, fúrt kút, 
    dupla garázs, külön bejáratú lakrészek stb.)

### 3. Kizárt ingatlanok szekció
Kizárólag akkor, ha van a kizárt ingatlanokra vonatkozó információ.
- **Kizárva**: a `ranked_<LABEL>.txt` "KIZÁRT INGATLANOK" listája alapján, 
  indoklással (melyik prefilter feltétel nem teljesült [ha megadtuk])

## Stílus
- Magyar nyelv
- Emberi fogyasztásra szánt, olvasmányos, de precíz
- A műszaki adatok pontosak legyenek (az ingatlanok.json-ból vedd ki)
- A pontszám a `ranked_<LABEL>.txt`-ből származzon
- Használj Markdown formázást (címsorok, felsorolások, **kiemelések**, --- elválasztók)
