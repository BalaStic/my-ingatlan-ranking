/**
 * background.js — Service worker for Ingatlan Scorer extension.
 * Uses chrome.debugger + Page.captureSnapshot (CDP) to reliably capture MHTML in MV3.
 * Returns base64-encoded MHTML to the popup for download.
 */

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'saveMhtml') {
    const { tabId, tabUrl, cim } = request;
    const filename = buildMhtmlFilename(tabUrl, cim);
    captureMhtml(tabId, filename, sendResponse);
    return true; // keep message channel open for async response
  }
  if (request.action === 'saveFromLinks') {
    saveFromLinks(request.urls).then(result => sendResponse(result));
    return true;
  }
});

// ---------------------------------------------------------------------------
// MHTML capture with pre-detach, Page.enable, and retry
// ---------------------------------------------------------------------------

function captureMhtml(tabId, filename, sendResponse) {
  const target = { tabId };

  // Pre-detach: clean up any leftover debugger session from a previous run
  chrome.debugger.detach(target, () => {
    void chrome.runtime.lastError; // suppress "not attached" error
    doAttachAndCapture(target, filename, 0, sendResponse);
  });
}

function doAttachAndCapture(target, filename, attempt, sendResponse) {
  chrome.debugger.attach(target, '1.3', () => {
    if (chrome.runtime.lastError) {
      sendResponse({ success: false, error: 'Attach hiba: ' + chrome.runtime.lastError.message });
      return;
    }

    // Enable the Page domain before using Page commands
    chrome.debugger.sendCommand(target, 'Page.enable', {}, () => {
      if (chrome.runtime.lastError) {
        chrome.debugger.detach(target, () => {});
        sendResponse({ success: false, error: 'Page.enable hiba: ' + chrome.runtime.lastError.message });
        return;
      }

      chrome.debugger.sendCommand(target, 'Page.captureSnapshot', {}, (result) => {
        const captureError = chrome.runtime.lastError;
        const failed = captureError || !result || !result.data;

        if (failed && attempt < 2) {
          // Retry: detach and try again after a short delay
          chrome.debugger.detach(target, () => {});
          setTimeout(() => {
            doAttachAndCapture(target, filename, attempt + 1, sendResponse);
          }, 600);
          return;
        }

        // Always detach after capture (success or final failure)
        chrome.debugger.detach(target, () => {});

        if (failed) {
          const msg = captureError
            ? captureError.message
            : 'Üres snapshot adat';
          sendResponse({ success: false, error: 'CDP snapshot hiba: ' + msg });
          return;
        }

        // Trigger download directly from background via data: URL
        // (avoids URL.createObjectURL unavailability in service workers)
        try {
          const uint8 = new TextEncoder().encode(result.data);
          let binary = '';
          const chunkSize = 8192;
          for (let i = 0; i < uint8.length; i += chunkSize) {
            binary += String.fromCharCode(...uint8.subarray(i, i + chunkSize));
          }
          const base64 = btoa(binary);
          const dataUrl = 'data:application/octet-stream;base64,' + base64;

          chrome.downloads.download(
            { url: dataUrl, filename, saveAs: false },
            () => {
              if (chrome.runtime.lastError) {
                sendResponse({ success: false, error: 'Letöltés hiba: ' + chrome.runtime.lastError.message });
              } else {
                sendResponse({ success: true });
              }
            }
          );
        } catch (e) {
          sendResponse({ success: false, error: 'Encode hiba: ' + e.message });
        }
      });
    });
  });
}

// ---------------------------------------------------------------------------
// Filename builder
// ---------------------------------------------------------------------------

function buildMhtmlFilename(tabUrl, cim) {
  const idMatch = (tabUrl || '').match(/\/(\d+)(?:[/?#]|$)/);
  const id = idMatch ? idMatch[1] : 'unknown';

  const cleanCim = (cim || '')
    .replace(/[,\.\/\\:*?"<>|]/g, '')
    .replace(/\s+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '');

  return `#${id}_${cleanCim}.mhtml`;
}

// ---------------------------------------------------------------------------
// Progressive scroll — adapted from example for ingatlan.com pages
// ---------------------------------------------------------------------------

function progressiveScroll() {
  // Try to find the main scroll container on ingatlan.com
  const container =
    document.querySelector('main') ||
    document.querySelector('[role="main"]') ||
    document.querySelector('.page__content') ||
    document.querySelector('#main-content');

  if (container) {
    console.log('[progressiveScroll] Found scroll container:', container.tagName, container.className,
      '| scrollHeight:', container.scrollHeight, '| clientHeight:', container.clientHeight);

    const step = container.clientHeight || 600;
    let scrolled = 0;
    const maxScroll = container.scrollHeight - container.clientHeight;

    const scrollDown = () => {
      if (scrolled >= maxScroll) {
        console.log('[progressiveScroll] Reached bottom, stopping.');
        return;
      }
      scrolled = Math.min(scrolled + step, maxScroll);
      container.scrollTo(0, scrolled);
      console.log('[progressiveScroll] Scrolled to:', scrolled, 'of', maxScroll);
    };

    console.log('[progressiveScroll] Starting progressive scroll...');
    scrollDown();

    const interval = setInterval(() => {
      if (scrolled >= container.scrollHeight - container.clientHeight) {
        clearInterval(interval);
        console.log('[progressiveScroll] Done scrolling (interval cleared).');
        return;
      }
      scrollDown();
    }, 400);

    // Stop after 15s max
    setTimeout(() => {
      clearInterval(interval);
      console.log('[progressiveScroll] Timeout reached, stopped.');
    }, 15000);
  } else {
    console.warn('[progressiveScroll] No scroll container found, falling back to window.scrollTo');
    window.scrollTo(0, document.body.scrollHeight);
  }
}

// ---------------------------------------------------------------------------
// Pre-load: activate tab, inject progressive scroll, wait, then capture
// ---------------------------------------------------------------------------

async function preloadAndCapture(tabId, filename, sendResponse) {
  let responded = false;
  const TIMEOUT_MS = 30000;

  const timeout = setTimeout(() => {
    if (!responded) {
      responded = true;
      sendResponse({ success: false, error: 'Időtúllépés a preload/save folyamatban' });
    }
  }, TIMEOUT_MS);

  const safeRespond = (resp) => {
    if (!responded) {
      responded = true;
      clearTimeout(timeout);
      sendResponse(resp);
    }
  };

  try {
    // 1. Activate the tab so we can see it and the page renders its content
    console.log('[preloadAndCapture] Activating tab', tabId);
    await chrome.tabs.update(tabId, { active: true });

    // 2. Wait for the page to render (inactive tabs may have deferred content)
    await new Promise(r => setTimeout(r, 1500));

    // 3. Inject progressive scroll
    console.log('[preloadAndCapture] Injecting progressiveScroll...');
    await chrome.scripting.executeScript({
      target: { tabId },
      func: progressiveScroll
    });

    // 4. Let scrolling run + lazy content load
    console.log('[preloadAndCapture] Scroll injected, waiting 3s for lazy loads...');
    await new Promise(r => setTimeout(r, 3000));

    console.log('[preloadAndCapture] Preload done, capturing...');
  } catch (e) {
    console.error('[preloadAndCapture] Preload failed:', e);
  }

  captureMhtmlWithSafeRespond(tabId, filename, safeRespond);
}

function captureMhtmlWithSafeRespond(tabId, filename, safeRespond) {
  const target = { tabId };

  chrome.debugger.detach(target, () => {
    void chrome.runtime.lastError;
    doAttachAndCaptureSafe(target, filename, 0, safeRespond);
  });
}

function doAttachAndCaptureSafe(target, filename, attempt, safeRespond) {
  chrome.debugger.attach(target, '1.3', () => {
    if (chrome.runtime.lastError) {
      safeRespond({ success: false, error: 'Attach hiba: ' + chrome.runtime.lastError.message });
      return;
    }

    chrome.debugger.sendCommand(target, 'Page.enable', {}, () => {
      if (chrome.runtime.lastError) {
        chrome.debugger.detach(target, () => {});
        safeRespond({ success: false, error: 'Page.enable hiba: ' + chrome.runtime.lastError.message });
        return;
      }

      chrome.debugger.sendCommand(target, 'Page.captureSnapshot', {}, (result) => {
        const captureError = chrome.runtime.lastError;
        const failed = captureError || !result || !result.data;

        if (failed && attempt < 2) {
          chrome.debugger.detach(target, () => {});
          setTimeout(() => {
            doAttachAndCaptureSafe(target, filename, attempt + 1, safeRespond);
          }, 600);
          return;
        }

        chrome.debugger.detach(target, () => {});

        if (failed) {
          const msg = captureError ? captureError.message : 'Üres snapshot adat';
          safeRespond({ success: false, error: 'CDP snapshot hiba: ' + msg });
          return;
        }

        try {
          const uint8 = new TextEncoder().encode(result.data);
          let binary = '';
          const chunkSize = 8192;
          for (let i = 0; i < uint8.length; i += chunkSize) {
            binary += String.fromCharCode(...uint8.subarray(i, i + chunkSize));
          }
          const base64 = btoa(binary);
          const dataUrl = 'data:application/octet-stream;base64,' + base64;

          chrome.downloads.download(
            { url: dataUrl, filename, saveAs: false, conflictAction: 'overwrite' },
            () => {
              if (chrome.runtime.lastError) {
                safeRespond({ success: false, error: 'Letöltés hiba: ' + chrome.runtime.lastError.message });
              } else {
                safeRespond({ success: true });
                chrome.tabs.remove(target.tabId, () => void chrome.runtime.lastError);
              }
            }
          );
        } catch (e) {
          safeRespond({ success: false, error: 'Encode hiba: ' + e.message });
        }
      });
    });
  });
}

// ---------------------------------------------------------------------------
// processOneTab: activate, scroll, capture, download, close
// ---------------------------------------------------------------------------

function processOneTab(tabId, tabUrl, tabTitle) {
  return new Promise((resolve) => {
    const filename = buildMhtmlFilename(tabUrl, tabTitle);
    preloadAndCapture(tabId, filename, (result) => {
      resolve(result && result.success);
    });
  });
}

// ---------------------------------------------------------------------------
// waitForTabLoad: wait for a newly created tab to finish loading
// ---------------------------------------------------------------------------

function waitForTabLoad(tabId, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error(`Tab ${tabId} load timeout`));
    }, timeoutMs);

    const listener = (updatedTabId, changeInfo, tab) => {
      if (updatedTabId === tabId && changeInfo.status === 'complete') {
        clearTimeout(timeout);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(tab);
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
  });
}

// ---------------------------------------------------------------------------
// saveFromLinks: open each URL, load, scroll, capture, download, close
// ---------------------------------------------------------------------------

async function saveFromLinks(urls) {
  if (!urls || urls.length === 0) {
    console.log('[saveFromLinks] No URLs provided.');
    return { savedCount: 0, failedCount: 0 };
  }

  console.log(`[saveFromLinks] Processing ${urls.length} URLs...`);

  let savedCount = 0;
  let failedCount = 0;

  for (let i = 0; i < urls.length; i++) {
    const url = urls[i];
    try {
      await chrome.action.setBadgeText({ text: `${i + 1}/${urls.length}` });
      await chrome.action.setBadgeBackgroundColor({ color: '#1a73e8' });
    } catch (_) { /* badge may fail if no action button */ }

    let tabId = null;
    try {
      console.log(`[saveFromLinks] [${i + 1}/${urls.length}] Opening: ${url}`);
      const tab = await chrome.tabs.create({ url, active: false });
      tabId = tab.id;

      // Wait for the tab to fully load
      const loadedTab = await waitForTabLoad(tabId, 30000);
      console.log(`[saveFromLinks] [${i + 1}/${urls.length}] Loaded: "${loadedTab.title}"`);

      // Process: activate, scroll, capture, download, close
      const success = await processOneTab(tabId, url, loadedTab.title || '');

      if (success) {
        savedCount++;
      } else {
        failedCount++;
        // processOneTab closes the tab on success; clean up on failure
        chrome.tabs.remove(tabId, () => void chrome.runtime.lastError);
      }
    } catch (e) {
      console.error(`[saveFromLinks] [${i + 1}/${urls.length}] Failed:`, e.message);
      failedCount++;
      if (tabId) {
        chrome.tabs.remove(tabId, () => void chrome.runtime.lastError);
      }
    }

    // Delay between items
    if (i < urls.length - 1) {
      await new Promise(r => setTimeout(r, 500));
    }
  }

  try { await chrome.action.setBadgeText({ text: '' }); } catch (_) { /* ok */ }
  console.log(`[saveFromLinks] Done! Saved: ${savedCount}, Failed: ${failedCount}`);
  return { savedCount, failedCount };
}
