/**
 * content.js — Scrapes ingatlan.com property page data from the DOM.
 * Listens for messages from popup.js, responds with the extracted property data.
 */

// Guard: avoid re-registering if script is injected multiple times
if (!window.__ingatlanScorerLoaded) {
  window.__ingatlanScorerLoaded = true;

const MISSING = 'nincs megadva';

function cleanText(s) {
  return s ? s.replace(/\s+/g, ' ').trim() : '';
}

function scrapeIngatlan() {
  const result = {};

  // --- Build param_map from the page ---
  const paramMap = {};

  function addPair(labelText, valueText) {
    labelText = cleanText(labelText);
    valueText = cleanText(valueText);
    if (labelText && valueText) {
      paramMap[labelText] = valueText;
    }
  }

  // Pattern E: div.listing-property blocks (top summary: Ár, Alapterület, etc.)
  document.querySelectorAll('div[class*="listing-property"]').forEach(lp => {
    const spans = Array.from(lp.children).filter(el => el.tagName === 'SPAN');
    if (spans.length >= 2) {
      addPair(spans[0].textContent, spans[1].textContent);
    } else {
      const texts = Array.from(lp.childNodes)
        .map(n => cleanText(n.textContent))
        .filter(t => t.length > 0);
      if (texts.length >= 2) {
        addPair(texts[0], texts.slice(1).join(' '));
      }
    }
  });

  // Pattern A: dt/dd pairs
  document.querySelectorAll('dt').forEach(dt => {
    const dd = dt.nextElementSibling;
    if (dd && dd.tagName === 'DD') {
      addPair(dt.textContent, dd.textContent);
    }
  });

  // Pattern B: table rows with 2 cells
  document.querySelectorAll('tr').forEach(tr => {
    const cells = tr.querySelectorAll('th, td');
    if (cells.length === 2) {
      addPair(cells[0].textContent, cells[1].textContent);
    }
  });

  // Pattern C: label/value class siblings
  document.querySelectorAll('[class*="label"],[class*="parameter-name"],[class*="param-name"],[class*="key"]').forEach(el => {
    const sibling = el.nextElementSibling;
    if (sibling) {
      addPair(el.textContent, sibling.textContent);
    }
  });

  // Pattern D: find known field names as text nodes, look for next sibling value
  const PARAM_FIELDS = [
    'Alapterület', 'Telekterület', 'Szobák', 'Ingatlan állapota', 'Építés éve',
    'Komfort', 'Épület szintjei', 'Légkondicionáló', 'Akadálymentesített',
    'Fürdő és wc', 'Kilátás', 'Tetőtér', 'Pince', 'Parkolás',
    'Átlag gázfogyasztás', 'Átlag áramfogyasztás', 'Rezsiköltség', 'Közös költség',
    'Fűtés', 'Napelem', 'Szigetelés', 'Energetikai tanúsítvány', 'Ár'
  ];

  const allTextNodes = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const textNodeList = [];
  let node;
  while ((node = allTextNodes.nextNode())) {
    textNodeList.push(node);
  }

  for (const field of PARAM_FIELDS) {
    if (paramMap[field]) continue;
    for (const tn of textNodeList) {
      if (cleanText(tn.textContent) === field) {
        const parent = tn.parentElement;
        if (!parent) continue;
        const sibling = parent.nextElementSibling;
        if (sibling && cleanText(sibling.textContent)) {
          addPair(field, sibling.textContent);
          break;
        }
        const grandSibling = parent.parentElement && parent.parentElement.nextElementSibling;
        if (grandSibling && cleanText(grandSibling.textContent)) {
          addPair(field, grandSibling.textContent);
          break;
        }
      }
    }
  }

  // --- link ---
  let link = '';
  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical) {
    link = canonical.getAttribute('href') || '';
  }
  if (!link) {
    const ogUrl = document.querySelector('meta[property="og:url"]');
    if (ogUrl) link = ogUrl.getAttribute('content') || '';
  }
  if (!link) link = window.location.href;
  result['link'] = link;

  // --- cím ---
  let cim = '';
  const cimSelectors = [
    'section#hero span.fw-bold',
    'span.card-title.fw-bold',
    'h1.js-listing-card-title',
    "h1[class*='title']",
    '.listing-title',
    'h1',
  ];
  for (const sel of cimSelectors) {
    const el = document.querySelector(sel);
    if (el) {
      const text = cleanText(el.textContent);
      if (text) { cim = text; break; }
    }
  }
  result['cím'] = cim || MISSING;

  // --- Ár ---
  result['Ár'] = paramMap['Ár'] || MISSING;

  // --- leírás ---
  let leiras = '';
  // Find heading "Leírás"
  const headings = document.querySelectorAll('h5, h4, h3');
  for (const h of headings) {
    if (/^\s*Leírás\s*$/.test(h.textContent)) {
      const card = h.closest('div[class*="card"]');
      if (card) {
        const paras = card.querySelectorAll('p');
        if (paras.length > 0) {
          leiras = cleanText(Array.from(paras).map(p => p.textContent).join(' '));
        } else {
          const texts = [];
          let el = h.nextElementSibling;
          while (el) {
            const t = cleanText(el.textContent);
            if (t) texts.push(t);
            el = el.nextElementSibling;
          }
          leiras = texts.join(' ');
        }
        break;
      }
    }
  }
  if (!leiras) {
    const descSelectors = [
      '.description__text', '.listing-description', '#listing-description',
      '[data-testid="listing-description"]', '.js-listing-description',
    ];
    for (const sel of descSelectors) {
      const el = document.querySelector(sel);
      if (el) { leiras = cleanText(el.textContent); break; }
    }
  }
  result['leírás'] = leiras || MISSING;

  // --- All other PARAM_FIELDS ---
  for (const field of PARAM_FIELDS.filter(f => f !== 'Ár')) {
    result[field] = paramMap[field] || MISSING;
  }

  return result;
}

// ---------------------------------------------------------------------------
// Scorecard injection
// ---------------------------------------------------------------------------

function buildScorecard(scoreResult, ing, configLabel) {
  const { total, pct, breakdown, ar, terulet } = scoreResult;
  const nmAr = (terulet > 0 && ar > 0)
    ? Math.round(ar * 1000000 / terulet).toLocaleString('hu-HU')
    : '—';
  const cim = ing['cím'] || '—';

  const CATEGORY_NAMES = {
    kor: 'Kor', terulet: 'Terület', allapot: 'Állapot',
    energetika: 'Energetika', udvar: 'Udvar', extra: 'Extra', kulcsszo: 'Kulcsszó',
  };

  // Remove existing scorecard if present
  const existing = document.getElementById('ingatlan-scorer-card');
  if (existing) existing.remove();

  // --- Build card DOM ---
  const card = document.createElement('div');
  card.id = 'ingatlan-scorer-card';
  card.style.cssText = [
    'font-family: Segoe UI, Arial, sans-serif',
    'font-size: 13px',
    'color: #222',
    'background: #f5f7fa',
    'border: 2px solid #1a73e8',
    'border-radius: 8px',
    'overflow: hidden',
    'margin: 16px 0 24px 0',
    'box-shadow: 0 2px 8px rgba(26,115,232,0.15)',
  ].join(';');

  // Header
  const header = document.createElement('div');
  header.style.cssText = [
    'background: #1a73e8',
    'color: white',
    'padding: 10px 16px',
    'display: flex',
    'justify-content: space-between',
    'align-items: center',
    'flex-wrap: wrap',
    'gap: 6px',
  ].join(';');
  const headerLeft = document.createElement('div');
  headerLeft.innerHTML = `<strong style="font-size:15px">📊 ${cim}</strong>`;
  const headerRight = document.createElement('div');
  headerRight.style.cssText = 'text-align:right;font-size:13px';
  headerRight.innerHTML =
    `<span style="font-size:20px;font-weight:700">${total.toFixed(1)} pt &nbsp;<span style="font-size:15px;opacity:0.9">(${pct !== undefined ? pct.toFixed(1) : '?'}%)</span></span>` +
    `<br><span style="opacity:0.85">config: ${configLabel}` +
    (ar > 0 ? ` &nbsp;|&nbsp; ${ar} M Ft` : '') +
    (terulet > 0 && ar > 0 ? ` &nbsp;(${nmAr} Ft/m²)` : '') +
    `</span>`;
  header.appendChild(headerLeft);
  header.appendChild(headerRight);
  card.appendChild(header);

  // Table
  const table = document.createElement('table');
  table.style.cssText = [
    'width: 100%',
    'border-collapse: collapse',
    'background: white',
  ].join(';');

  // Table header row
  const thead = document.createElement('thead');
  const headTr = document.createElement('tr');
  headTr.style.background = '#e8f0fe';
  ['Kategória', 'Részletek', 'Pont', 'Súly', 'Részpont'].forEach(text => {
    const th = document.createElement('th');
    th.textContent = text;
    th.style.cssText = [
      'padding: 6px 10px',
      'text-align: left',
      'font-size: 11px',
      'font-weight: 700',
      'color: #1a73e8',
      'text-transform: uppercase',
      'letter-spacing: 0.4px',
      'border-bottom: 1px solid #e0e0e0',
    ].join(';');
    if (['Pont', 'Súly', 'Részpont'].includes(text)) th.style.textAlign = 'right';
    headTr.appendChild(th);
  });
  thead.appendChild(headTr);
  table.appendChild(thead);

  // Table body
  const tbody = document.createElement('tbody');
  Object.entries(breakdown).forEach(([key, vals], idx) => {
    const tr = document.createElement('tr');
    tr.style.background = idx % 2 === 0 ? '#ffffff' : '#fafafa';

    const tdName = document.createElement('td');
    tdName.textContent = CATEGORY_NAMES[key] || key;
    tdName.style.cssText = 'padding:5px 10px;font-weight:600;border-bottom:1px solid #f0f0f0';

    const tdLabel = document.createElement('td');
    tdLabel.textContent = vals.label || '';
    tdLabel.style.cssText = 'padding:5px 10px;font-size:11px;color:#666;border-bottom:1px solid #f0f0f0';

    const tdPont = document.createElement('td');
    tdPont.textContent = vals.pont.toFixed(2);
    tdPont.style.cssText = 'padding:5px 10px;text-align:right;color:#444;border-bottom:1px solid #f0f0f0';

    const tdWeight = document.createElement('td');
    tdWeight.textContent = '×' + vals.weight;
    tdWeight.style.cssText = 'padding:5px 10px;text-align:right;color:#444;border-bottom:1px solid #f0f0f0';

    const tdSub = document.createElement('td');
    tdSub.textContent = vals.subtotal.toFixed(1);
    tdSub.style.cssText = 'padding:5px 10px;text-align:right;font-weight:700;color:#1a73e8;border-bottom:1px solid #f0f0f0';

    tr.appendChild(tdName);
    tr.appendChild(tdLabel);
    tr.appendChild(tdPont);
    tr.appendChild(tdWeight);
    tr.appendChild(tdSub);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  card.appendChild(table);

  return card;
}

function injectScorecard(scoreResult, ing, configLabel) {
  const card = buildScorecard(scoreResult, ing, configLabel);

  // Insert before the gallery section
  const gallery = document.querySelector('[data-controller="details-page--gallery"]');
  if (gallery && gallery.parentNode) {
    gallery.parentNode.insertBefore(card, gallery);
  } else {
    // Fallback: prepend to main content area or body
    const main = document.querySelector('main') || document.body;
    main.prepend(card);
  }

  // Scroll the card into view
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ---------------------------------------------------------------------------
// Message listener
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'scrape') {
    try {
      const data = scrapeIngatlan();
      sendResponse({ success: true, data });
    } catch (e) {
      sendResponse({ success: false, error: e.message });
    }
  } else if (request.action === 'injectScorecard') {
    try {
      injectScorecard(request.scoreResult, request.ing, request.configLabel);
      sendResponse({ success: true });
    } catch (e) {
      sendResponse({ success: false, error: e.message });
    }
  }
  return true; // keep channel open for async
});

} // end guard: window.__ingatlanScorerLoaded
