# Feladat

Készítsd el az `ingatlan_rangsor.md` fájlt, amely egy emberi fogyasztásra szánt, 
magyar nyelvű ingatlan rangsorolási jelentés.

## Bemeneti fájlok (mindet csatolom)

1. **scores_default.txt** — a `score_ingatlan.py` script által generált pontozott rangsor.
   Ez tartalmazza a végleges sorrendet, a pontszámokat, és az egyes kategóriák 
   részpontszámait (kor, terület, állapot, energetika, udvar, extra, kulcsszó).

2. **ingatlanok.json** — az ingatlanok nyers adatai (leírás, ár, alapterület, fűtés típusa,
   szigetelés, napelem, stb.). Innen kell kivenni a részletes leírásokhoz szükséges 
   információkat, linkeket, címeket.

3. **ingatlan_ranking_PROMPT.txt** — a rangsorolási módszertan, peremfeltételek 
   és preferenciák leírása (erre hivatkozz a "Fő szempontok" szekcióban).

4. **scoring_config.json** — a súlyok konfigurációja (a "default" label alatt).

## Kimeneti fájl formátuma: `ingatlan_rangsor.md`

A fájl az alábbi szerkezetet kövesse (lásd a csatolt példát referenciaként):

### 1. Fő szempontok szekció
- Röviden sorold fel a hard constraint-eket (a prompt 1. pontja alapján)
- Sorold fel a preferenciákat és azok súlyait (a scoring_config.json "default" 
  configja alapján)
- Említsd meg a speciális szabályt: "1990 előtti ház nem előzhet meg 2000 utánit"

### 2. Top 10 rangsorolt ingatlan
- A `scores_default.txt` rangsora alapján, pontszám szerint csökkenőben
- Minden ingatlannál:
  - **Cím és link** (az ingatlanok.json-ból)
  - **Ár és négyzetméterár** (a scores-ból, kerekítve)
  - **Kiemelt paraméterek**: alapterület, telek, szobák, kor/állapot, energetika, 
    udvar, garázs — a scores.txt adatai + az ingatlanok.json részletei alapján
  - **Indoklás** (2-4 mondat): miért ezt a helyezést kapta, miben erős/gyenge, 
    hogyan teljesítette a preferenciákat, milyen konkrét műszaki részletek 
    (kazán típusa, szigetelés vastagsága, energetikai tanúsítvány) befolyásolták
  - **Egyedi jellemző**: az ingatlanok.json leírásából kigyűjtött nem szokványos 
    tulajdonságok (pl. pince, napelem, medence, akadálymentesítés, fúrt kút, 
    dupla garázs, külön bejáratú lakrészek stb.)

### 3. Kizárt / súlyosan hátrányos ingatlanok szekció
- **Kizárva**: a `scores_default.txt` "KIZÁRT INGATLANOK" listája alapján, 
  indoklással (melyik hard constraint nem teljesült)
- **Súlyosan hátrányos**: A PRE-1990 kategóriába eső ingatlanok rövid felsorolása 
  a scores.txt adatai alapján

## Stílus
- Magyar nyelv
- Emberi fogyasztásra szánt, olvasmányos, de precíz
- A műszaki adatok pontosak legyenek (az ingatlanok.json-ból vedd ki)
- A pontszám a scores.txt-ből származzon
- Használj Markdown formázást (címsorok, felsorolások, **kiemelések**, --- elválasztók)
