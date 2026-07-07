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
