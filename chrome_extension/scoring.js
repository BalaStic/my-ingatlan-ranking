/**
 * scoring.js — Ingatlan scoring logic ported from scoring.py
 */

// ---------------------------------------------------------------------------
// Parse helpers
// ---------------------------------------------------------------------------

function parseAr(arStr) {
  if (!arStr || arStr === 'nincs megadva') return 0;
  const cleaned = arStr.replace(' millió Ft', '').replace(',', '.').trim().split(/\s+/)[0];
  return parseFloat(cleaned) || 0;
}

function parseTerulet(t) {
  if (!t || t.toLowerCase().includes('nincs')) return 0;
  return parseInt(t.replace(' m2', '').replace(' m²', '').trim()) || 0;
}

function parseTelek(t) {
  if (!t || t.toLowerCase().includes('nincs')) return 0;
  return parseInt(t.replace(' m2', '').replace(' m²', '').trim()) || 0;
}

function parseSzobak(szobakStr) {
  if (!szobakStr || szobakStr.toLowerCase().includes('nincs')) return 0;
  const parts = szobakStr.replace('+', ' ').split(/\s+/);
  let count = 0;
  for (const p of parts) {
    if (/^\d+$/.test(p)) {
      count += parseInt(p);
    } else if (p.includes('fél')) {
      count += 1;
    }
  }
  return count;
}

// ---------------------------------------------------------------------------
// Kor (year built)
// ---------------------------------------------------------------------------

function evToPont(ev) {
  const clamped = Math.max(1950, Math.min(2025, ev));
  return 1.0 + (clamped - 1950) / (2025 - 1950) * 4.0;
}

function korKategoriaStr(ev) {
  if (ev < 1991) return '1990 előtt';
  if (ev <= 2000) return '1991-2000';
  if (ev <= 2009) return '2001-2009';
  return '2010 után';
}

function getKorKategoria(korStr, leiras = '') {
  const MISSING = 'nincs megadva';
  if (!korStr || korStr.toLowerCase().includes('nincs megadva')) {
    // Try to extract years from description
    const matches = [...leiras.matchAll(/\b(19[5-9]\d|20[0-2]\d)\b/g)];
    if (matches.length > 0) {
      const evek = matches.map(m => parseInt(m[1]));
      const ev = Math.round(evek.reduce((a, b) => a + b, 0) / evek.length);
      return { kat: korKategoriaStr(ev), pont: evToPont(ev) };
    }
    if (leiras.toLowerCase().includes('múlt század első felében')) {
      return { kat: '1990 előtt', pont: evToPont(1940) };
    }
    return { kat: 'Ismeretlen', pont: evToPont(1975) };
  }

  // Interval: "1950 és 1980 között"
  const intervalMatch = korStr.match(/(\d{4})\s+és\s+(\d{4})/);
  if (intervalMatch) {
    const ev1 = parseInt(intervalMatch[1]);
    const ev2 = parseInt(intervalMatch[2]);
    const ev = Math.round((ev1 + ev2) / 2);
    return { kat: korKategoriaStr(ev), pont: evToPont(ev) };
  }

  // Specific year(s)
  const years = [...korStr.matchAll(/\b(19[5-9]\d|20[0-2]\d)\b/g)].map(m => parseInt(m[1]));
  if (years.length > 0) {
    const ev = Math.max(...years);
    return { kat: korKategoriaStr(ev), pont: evToPont(ev) };
  }

  return { kat: 'Ismeretlen', pont: evToPont(1975) };
}

// ---------------------------------------------------------------------------
// Állapot
// ---------------------------------------------------------------------------

function getAllapotPont(allapot) {
  if (!allapot) return 2;
  const a = allapot.toLowerCase();
  if (a.includes('újszerű')) return 5;
  if (a.includes('felújított')) return 4;
  if (a.includes('jó állapotú') || a.includes('jó állapot')) return 3;
  if (a.includes('felújítandó')) return 1;
  return 2;
}

// ---------------------------------------------------------------------------
// Energetika
// ---------------------------------------------------------------------------

function getEnergetikaPont(ing) {
  const futes = (ing['Fűtés'] || '').toLowerCase();
  const napelem = (ing['Napelem'] || '').toLowerCase();
  const szigeteles = (ing['Szigetelés'] || '').toLowerCase();
  const energetika = (ing['Energetikai tanúsítvány'] || '').toLowerCase();
  const klima = (ing['Légkondicionáló'] || '').toLowerCase();

  let pont = 1; // base: low (even without gas boiler, minimum 1 after clamp)

  if (napelem.includes('van')) pont += 2;
  if (szigeteles.includes('van')) {
    if (szigeteles.includes('15')) pont += 2;
    else if (szigeteles.includes('10')) pont += 1;
    else pont += 1;
  }
  if (futes.includes('hőszivattyú')) pont += 3;
  else if (futes.includes('kondenzációs')) pont += 2;
  else if (futes.includes('gázkazán') && !futes.includes('vegyes')) pont += 1;
  else if (futes.includes('konvektor')) pont -= 1;

  if (klima.includes('van')) pont += 1;
  if ((energetika.includes('c') || energetika.includes('b')) && !energetika.includes('nincs')) pont += 1;
  if (energetika.includes('a') && !energetika.includes('nincs')) pont += 2;

  // Only hőszivattyú can reach 5; gázkazán/other heating capped at 4
  const cap = futes.includes('hőszivattyú') ? 5 : 4;
  return Math.max(1, Math.min(cap, pont));
}

// ---------------------------------------------------------------------------
// Udvar
// ---------------------------------------------------------------------------

function getUdvarPont(telek, terulet) {
  const kert = telek - terulet;
  if (kert <= 0) return 1;
  if (kert > 300) return 5;
  if (kert > 150) return 4;
  if (kert > 50) return 3;
  return 2;
}

// ---------------------------------------------------------------------------
// Extra
// ---------------------------------------------------------------------------

function getExtraPont(ing) {
  let pont = 0;
  if ((ing['Akadálymentesített'] || '').toLowerCase() === 'igen') pont += 1;
  if ((ing['Tetőtér'] || '').toLowerCase().includes('beépített')) pont += 1;
  if ((ing['Légkondicionáló'] || '').toLowerCase() === 'van') pont += 1;
  const furdo = (ing['Fürdő és wc'] || '').toLowerCase();
  if (furdo.includes('külön és egyben is')) pont += 1;
  const leiras = (ing['leírás'] || '').toLowerCase();
  if (leiras.includes('riasztó')) pont += 1;
  if (leiras.includes('öntöző')) pont += 1;
  return Math.min(5, pont);
}

// ---------------------------------------------------------------------------
// Kulcsszó
// ---------------------------------------------------------------------------

function getKulcsszoPoint(leiras) {
  let pont = 0;
  const l = leiras.toLowerCase();
  if (l.includes('modern')) pont += 1;
  if (l.includes('igényes')) pont += 1;
  if (l.includes('szép')) pont += 1;
  if (l.includes('korszerű')) pont += 1;
  if (l.includes('antik')) pont -= 1;
  if (l.includes('cserépkályha')) pont -= 1;
  if (l.includes('kemence')) pont -= 1;
  return pont;
}

// ---------------------------------------------------------------------------
// Main score function
// ---------------------------------------------------------------------------

function scoreIngatlan(ing, weights) {
  const ar = parseAr(ing['Ár']);
  const terulet = parseTerulet(ing['Alapterület']);
  const telek = parseTelek(ing['Telekterület']);
  const leiras = ing['leírás'] || '';

  const { kat: korKat, pont: korPont } = getKorKategoria(ing['Építés éve'], leiras);
  const allapotPont = getAllapotPont(ing['Ingatlan állapota']);
  const energetikaPont = getEnergetikaPont(ing);
  const udvarPont = getUdvarPont(telek, terulet);
  const extraPont = getExtraPont(ing);
  const kulcsszoPoint = getKulcsszoPoint(leiras);
  const teruletPont = Math.min(5, terulet / 45);

  const rawKor = ing['Építés éve'] || '';
  const intervalMatch = rawKor.match(/(\d{4})\s+és\s+(\d{4})/);
  const korLabel = intervalMatch
    ? intervalMatch[1] + '-' + intervalMatch[2] + ' között'
    : (rawKor || '?');

  const breakdown = {
    kor:        { pont: korPont,       weight: weights.kor,        subtotal: korPont * weights.kor,        label: korLabel },
    terulet:    { pont: teruletPont,   weight: weights.terulet,    subtotal: teruletPont * weights.terulet, label: terulet + ' m²' },
    allapot:    { pont: allapotPont,   weight: weights.allapot,    subtotal: allapotPont * weights.allapot, label: ing['Ingatlan állapota'] || 'ismeretlen' },
    energetika: { pont: energetikaPont,weight: weights.energetika, subtotal: energetikaPont * weights.energetika, label: (ing['Fűtés'] || 'ismeretlen') },
    udvar:      { pont: udvarPont,     weight: weights.udvar,      subtotal: udvarPont * weights.udvar,     label: (telek - terulet) + ' m² kert' },
    extra:      { pont: extraPont,     weight: weights.extra,      subtotal: extraPont * weights.extra,     label: '' },
    kulcsszo:   { pont: kulcsszoPoint, weight: weights.kulcsszo,   subtotal: kulcsszoPoint * weights.kulcsszo, label: '' },
  };

  const total = Object.values(breakdown).reduce((sum, v) => sum + v.subtotal, 0);
  const maxPont = 5 * Object.values(weights).reduce((a, b) => a + b, 0);
  const pct = maxPont > 0 ? (total / maxPont * 100) : 0;

  return { total, pct, breakdown, ar, terulet, telek };
}
