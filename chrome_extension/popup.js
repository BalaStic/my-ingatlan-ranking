/**
 * popup.js — Handles the extension popup UI logic.
 * Loads scoring configs from scoring_config.json, scores the current ingatlan.com page.
 */

const CATEGORY_NAMES = {
  kor:        'Kor',
  terulet:    'Terület',
  allapot:    'Állapot',
  energetika: 'Energetika',
  udvar:      'Udvar',
  extra:      'Extra',
  kulcsszo:   'Kulcsszó',
};

// Loaded asynchronously from scoring_config.json
let scoringConfigs = [];
let appSettings = {};

// ---------------------------------------------------------------------------
// Load scoring configs via XHR (reliable in MV3 extension popup)
// ---------------------------------------------------------------------------

function loadConfigs() {
  return new Promise((resolve, reject) => {
    const url = chrome.runtime.getURL('scoring_config.json');
    const xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.onload = () => {
      if (xhr.status === 200) {
        try {
          const data = JSON.parse(xhr.responseText);
          resolve({
            configs: data.configs || [],
            settings: data.settings || {},
          });
        } catch (e) {
          reject(new Error('JSON parse hiba: ' + e.message));
        }
      } else {
        reject(new Error('HTTP ' + xhr.status));
      }
    };
    xhr.onerror = () => reject(new Error('Hálózati hiba'));
    xhr.send();
  });
}

// ---------------------------------------------------------------------------
// MHTML save — fire-and-forget to background SW (which handles the full download)
// ---------------------------------------------------------------------------

function saveMhtml(tabId, tabUrl, cim) {
  // Fire-and-forget: background.js handles capture AND download dialog
  chrome.runtime.sendMessage({ action: 'saveMhtml', tabId, tabUrl, cim });
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------

function setStatus(msg) {
  document.getElementById('status').textContent = msg;
}

function showError(msg) {
  const el = document.getElementById('error');
  el.textContent = msg;
  el.style.display = 'block';
  document.getElementById('result').style.display = 'none';
  document.getElementById('status').textContent = '';
}

function hideError() {
  document.getElementById('error').style.display = 'none';
}

function renderResult(scoreResult, ing, configLabel) {
  hideError();
  document.getElementById('result').style.display = 'block';
  document.getElementById('status').textContent = '';

  const { total, pct, breakdown, ar, terulet } = scoreResult;

  document.getElementById('totalValue').textContent = total.toFixed(1) + ' (' + pct.toFixed(1) + '%)';
  document.getElementById('configLabel').textContent = configLabel;
  document.getElementById('arValue').textContent = ar > 0 ? ar + ' M Ft' : '';

  // Meta info
  const nmAr = (terulet > 0 && ar > 0)
    ? Math.round(ar * 1000000 / terulet).toLocaleString('hu-HU')
    : '—';
  const cim = ing['cím'] || '—';
  document.getElementById('metaBox').innerHTML =
    `<strong>${cim}</strong><br>` +
    `${terulet > 0 ? terulet + ' m²' : '—'} · ` +
    `${ing['Szobák'] || '—'} szoba · ` +
    `Nm-ár: ${nmAr} Ft/m²`;

  // Breakdown table
  const tbody = document.getElementById('breakdown');
  tbody.innerHTML = '';

  for (const [key, vals] of Object.entries(breakdown)) {
    const name = CATEGORY_NAMES[key] || key;
    const tr = document.createElement('tr');

    const tdName = document.createElement('td');
    tdName.textContent = name;
    if (vals.label) {
      const detail = document.createElement('div');
      detail.className = 'detail';
      detail.textContent = vals.label;
      tdName.appendChild(detail);
    }
    tr.appendChild(tdName);

    const tdPont = document.createElement('td');
    tdPont.className = 'num';
    tdPont.textContent = vals.pont.toFixed(2);
    tr.appendChild(tdPont);

    const tdWeight = document.createElement('td');
    tdWeight.className = 'num';
    tdWeight.textContent = '×' + vals.weight;
    tr.appendChild(tdWeight);

    const tdSub = document.createElement('td');
    tdSub.className = 'sub';
    tdSub.textContent = vals.subtotal.toFixed(1);
    tr.appendChild(tdSub);

    tbody.appendChild(tr);
  }
}

// ---------------------------------------------------------------------------
// Main init
// ---------------------------------------------------------------------------

function init() {
  const select = document.getElementById('configSelect');
  const btn = document.getElementById('scoreBtn');

  // Attach click handler immediately — unconditionally, regardless of config load status
  btn.addEventListener('click', async () => {
    if (scoringConfigs.length === 0) {
      showError('A konfiguráció még nem töltődött be. Próbáld újra!');
      return;
    }

    btn.disabled = true;
    hideError();
    document.getElementById('result').style.display = 'none';
    setStatus('Adatok beolvasása...');

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (!tab || !tab.url || !tab.url.includes('ingatlan.com')) {
        showError('Kérjük, nyisson meg egy ingatlan.com hirdetést!');
        return;
      }

      // Try sending message to content script; inject if needed
      let response;
      try {
        response = await chrome.tabs.sendMessage(tab.id, { action: 'scrape' });
      } catch (e) {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content.js'],
        });
        response = await chrome.tabs.sendMessage(tab.id, { action: 'scrape' });
      }

      if (!response || !response.success) {
        showError('Nem sikerült beolvasni az oldalt: ' +
          (response && response.error ? response.error : 'ismeretlen hiba'));
        return;
      }

      const ing = response.data;
      setStatus('Pontszámítás...');

      const selectedLabel = select.value;
      const cfg = scoringConfigs.find(c => c.label === selectedLabel);
      if (!cfg) {
        showError('Nem található a kiválasztott konfiguráció.');
        return;
      }

      const scoreResult = scoreIngatlan(ing, cfg.weights);
      renderResult(scoreResult, ing, cfg.label);

      // Inject scorecard into the page
      chrome.tabs.sendMessage(tab.id, {
        action: 'injectScorecard',
        scoreResult,
        ing,
        configLabel: cfg.label,
      });

      // Auto save MHTML if enabled in settings (fire-and-forget — background handles it)
      if (appSettings.auto_save_mhtml) {
        saveMhtml(tab.id, tab.url, ing['cím']);
      }

      // Close popup: scorecard is in the page, save dialog will appear from background
      window.close();

    } catch (e) {
      showError('Hiba: ' + e.message);
      btn.disabled = false;
    }
  });

  // Load configs asynchronously — populate select when ready
  setStatus('Konfiguráció betöltése...');

  loadConfigs().then(({ configs, settings }) => {
    scoringConfigs = configs;
    appSettings = settings;
    select.innerHTML = '';
    for (const cfg of configs) {
      const opt = document.createElement('option');
      opt.value = cfg.label;
      opt.textContent = cfg.label;
      select.appendChild(opt);
    }
    setStatus('Nyomj a Pontozás gombra!');
  }).catch(err => {
    showError('Nem sikerült betölteni a scoring_config.json-t: ' + err.message);
  });
}

// Run immediately — scripts are at bottom of body so DOM is already ready.
// readyState check handles edge cases.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
