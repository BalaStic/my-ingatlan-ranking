
---

## Pontozási döntési fa (pszeudokód)

---

### 1. KOR — Építés éve
```
ha az "Építés éve" nincs megadva:
    próbál évet kinyerni a szöveges leírásból
    ha talál → vedd az átlagot
    ha „múlt század első felében" szerepel → 1940-et becsül
    egyébként → 1975-öt becsül (konzervatív)

ha intervallum (pl. "1950 és 1980 között"):
    → középpont = (1950+1980) / 2 = 1965

egyébként:
    → a legújabb évszámot veszi

KOR PONT = 1.0 + (év - 1950) / (2025 - 1950) × 4.0
    → lineáris skála: 1950 → 1.0 pt, 2025 → 5.0 pt
    → közbenső példák: 1975 → 2.3, 2000 → 3.7, 2015 → 4.5
```

---

### 2. TERÜLET — Alapterület
```
TERÜLET PONT = min(5 ; alapterület / 50)

példák:
    150 m² → 3.0 pt
    200 m² → 4.0 pt
    250 m² → 5.0 pt (maximum)
    300 m² → 5.0 pt (capped)
```

---

### 3. ÁLLAPOT — Ingatlan állapota
```
ha "újszerű"     → 5 pt
ha "felújított"  → 4 pt
ha "jó állapotú" → 3 pt
ha "felújítandó" → 1 pt
egyébként        → 2 pt
```

---

### 4. ENERGETIKA — Komplex számítás
```
alap: 1 pont

ha napelem = "van"          → +2 pt
ha szigetelés tartalmaz "van":
    ha tartalmaz "15" (cm)  → +2 pt
    ha tartalmaz "10" (cm)  → +1 pt
    egyébként               → +1 pt

ha fűtés = "hőszivattyú"       → +3 pt
egyébként ha "kondenzációs"    → +2 pt
egyébként ha "gázkazán" (nem vegyes fűtés) → +1 pt
egyébként ha "konvektor"       → -1 pt

ha klíma = "van"               → +1 pt

ha energetikai tanúsítvány tartalmaz "c" vagy "b" (és nem "nincs megadva") → +1 pt
ha energetikai tanúsítvány tartalmaz "a" (és nem "nincs megadva")          → +2 pt

MAXIMUM korlátozás:
    ha hőszivattyú:   max = 5
    egyébként:        max = 4   ← gázkazán soha nem érheti el az 5-öt

VÉGSŐ PONT = max(1 ; min(cap ; összeg))

példák:
    gázkazán alone:                      1+1 = 2
    gázkazán + 15cm szigetelés:          1+1+2 = 4
    gázkazán + 15cm + klíma:             1+1+2+1 = 5 → capped → 4
    hőszivattyú:                         1+3 = 4
    hőszivattyú + napelem:               1+3+2 = 6 → capped → 5
    hőszivattyú + napelem + 15cm:        1+3+2+2 = 8 → capped → 5
```

---

### 5. UDVAR — Kertet becsül (telek - alapterület)
```
kert mérete = telekterület - alapterület

ha kert ≤ 0 m²  → 1 pt  (nincs kert)
ha kert ≤ 50 m² → 2 pt  (kis kert)
ha kert ≤ 150 m²→ 3 pt  (közepes)
ha kert ≤ 300 m²→ 4 pt  (nagy)
ha kert > 300 m²→ 5 pt  (nagyon nagy)
```

---

### 6. EXTRA — Extra funkciók  (0-tól indul, max 5)
```
ha akadálymentesített = "igen"           → +1 pt
ha beépített tetőtér                     → +1 pt
ha klíma = "van"                         → +1 pt
ha „fürdő és wc" = "külön és egyben is"  → +1 pt
ha „riasztó" szerepel a leírásban        → +1 pt
ha „öntöző" szerepel a leírásban         → +1 pt

VÉGSŐ PONT = min(5 ; összeg)
```

---

### 7. KULCSSZÓ — Leírásból (pozitív és negatív)
```
ha "modern"    → +1 pt
ha "igényes"   → +1 pt
ha "szép"      → +1 pt
ha "korszerű"  → +1 pt
ha "antik"     → -1 pt
ha "cserépkályha" → -1 pt
ha "kemence"   → -1 pt

(nincs hard cap, de a súlya általában kicsi)
```

---

### ÖSSZPONT és RELATÍV %
```
összpont = kor×kor_súly + terület×terület_súly + állapot×állapot_súly
         + energetika×energetika_súly + udvar×udvar_súly
         + extra×extra_súly + kulcsszó×kulcsszó_súly

max_elérhető = 5 × (összes súly összege)
relatív% = összpont / max_elérhető × 100
```

---
