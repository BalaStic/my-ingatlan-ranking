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
// MHTML save — background SW handles the full download
// ---------------------------------------------------------------------------

function saveMhtml(tabId, tabUrl, cim) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action: 'saveMhtml', tabId, tabUrl, cim }, (response) => {
      resolve(response);
    });
  });
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

const MAX_LINKS = 25; // limit for opening links to avoid overwhelming the user or the PC

/**
 * Function injected into the active tab to find all ingatlan.com listing links.
 * @returns {string[]} deduplicated array of full listing URLs
 */
function findIngatlanLinks() {
  const HREF_RE = /^\/(\d{8})(?:\/|\?|#|$)/;
  const seen = new Set();
  const allLinks = document.querySelectorAll('a[href]');
  const results = [];
  for (const a of allLinks) {
    const rawHref = a.getAttribute('href');
    if (rawHref && HREF_RE.test(rawHref)) {
      const fullUrl = a.href;
      if (!seen.has(fullUrl)) {
        seen.add(fullUrl);
        results.push(fullUrl);
      }
    }
  }
  return results;
}

function init() {
  const select = document.getElementById('configSelect');
  const btn = document.getElementById('scoreBtn');
  const saveAllBtn = document.getElementById('saveAllBtn');
  const saveFromPageBtn = document.getElementById('saveFromPageBtn');

  if (saveFromPageBtn) {
    saveFromPageBtn.addEventListener('click', async () => {
      saveFromPageBtn.disabled = true;
      saveAllBtn.disabled = true;
      btn.disabled = true;
      hideError();
      setStatus('Linkek keresése az aktív oldalon...');

      try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab || !tab.id) {
          setStatus('Nincs aktív fül.');
          setTimeout(() => {
            setStatus('Nyomj a Pontozás gombra!');
            saveFromPageBtn.disabled = false;
            saveAllBtn.disabled = false;
            btn.disabled = false;
          }, 2500);
          return;
        }

        const results = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: findIngatlanLinks,
          args: []
        });

        const links = results[0]?.result || [];
        if (links.length === 0) {
          setStatus('Nem található ingatlan link az oldalon.');
          setTimeout(() => {
            setStatus('Nyomj a Pontozás gombra!');
            saveFromPageBtn.disabled = false;
            saveAllBtn.disabled = false;
            btn.disabled = false;
          }, 2500);
          return;
        }

        const toSave = links.slice(0, MAX_LINKS);
        setStatus(`${toSave.length} link mentése elindítva (összesen ${links.length} találat)...`);

        // Send URLs to background service worker — popup closes immediately
        chrome.runtime.sendMessage({ action: 'saveFromLinks', urls: toSave }, (response) => {
          if (chrome.runtime.lastError) {
            return;
          }
          if (response) {
            const { savedCount, failedCount } = response;
            if (failedCount > 0) {
              setStatus(`Kész! ${savedCount} mentve, ${failedCount} sikertelen.`);
            } else {
              setStatus(`Kész! ${savedCount} ingatlan mentve.`);
            }
          }
          saveFromPageBtn.disabled = false;
          saveAllBtn.disabled = false;
          btn.disabled = false;
        });

        // Close popup — service worker takes over
        setTimeout(() => window.close(), 200);
      } catch (e) {
        showError('Hiba: ' + e.message);
        saveFromPageBtn.disabled = false;
        saveAllBtn.disabled = false;
        btn.disabled = false;
      }
    });
  }

  if (saveAllBtn) {
    saveAllBtn.addEventListener('click', async () => {
      saveAllBtn.disabled = true;
      setStatus('Nyitott ingatlanok keresése...');
      
      try {
        const tabs = await chrome.tabs.query({});
        let ingatlanTabs = tabs.filter(tab => tab.url && tab.url.match(/^https?:\/\/(?:www\.)?ingatlan\.com\/\d{8}(?:\/|\?|#|$)/));
        
        // Sort to ensure the active tab is processed last, so the popup stays open until the end
        const activeTabs = await chrome.tabs.query({ active: true, currentWindow: true });
        const activeTabId = activeTabs.length > 0 ? activeTabs[0].id : null;
        
        ingatlanTabs.sort((a, b) => {
          if (a.id === activeTabId) return 1;
          if (b.id === activeTabId) return -1;
          return 0;
        });
        
        if (ingatlanTabs.length === 0) {
          setStatus('Nincs megnyitott ingatlan (8 számjegyű URL).');
          setTimeout(() => { setStatus('Nyomj a Pontozás gombra!'); saveAllBtn.disabled = false; }, 2500);
          return;
        }

        setStatus(`${ingatlanTabs.length} ingatlan mentése folyamatban...`);
        let savedCount = 0;
        let previousTabId = null;
        
        for (const tab of ingatlanTabs) {
          if (previousTabId !== null) {
            chrome.tabs.remove(previousTabId).catch(e => console.error('Hiba a tab bezárásakor:', e));
          }
          await saveMhtml(tab.id, tab.url, tab.title);
          previousTabId = tab.id;
          savedCount++;
          await new Promise(r => setTimeout(r, 600));
        }
        
        if (previousTabId !== null) {
          chrome.tabs.remove(previousTabId).catch(e => console.error('Hiba a tab bezárásakor:', e));
        }
        
        setStatus(`Kész! ${savedCount} ingatlan mentve.`);
      } catch (e) {
        showError('Hiba mentés közben: ' + e.message);
        saveAllBtn.disabled = false;
      }
    });
  }

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
