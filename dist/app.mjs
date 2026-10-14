import config from './config.mjs';
import { nativeShare, copyCard, isAppleTouch, keepRoute, loadKeepFiles, shareImages } from './sharing.mjs';

const root = document.getElementById('romeo-ivory');
const stage = root.querySelector('.rv-stage');
const front = root.querySelector('.rv-front');
const back = root.querySelector('.rv-back');
const status = root.querySelector('.rv-status');
const hint = root.querySelector('.rv-hint');
const state = { flipped: false, mode: 'rest' };
let returnFocus = null;
let wakeLock = null;
let wakePending = false;
let sharePending = false;
const keep = { route: keepRoute(navigator), files: null, loading: null, pending: false };
let installPrompt = null;

function fitStage() {
  if (state.mode === 'rest') {
    stage.style.removeProperty('height');
    return;
  }
  const drawer = root.querySelector(`[data-drawer="${state.mode}"]`);
  stage.style.height = `${drawer.offsetTop + drawer.offsetHeight + 34}px`;
}

async function syncWakeLock() {
  const wanted = state.mode === 'share' && document.visibilityState === 'visible';
  if (!wanted && wakeLock) {
    const previous = wakeLock;
    wakeLock = null;
    await previous.release().catch(() => {});
  }
  if (!wanted || wakeLock || wakePending || !navigator.wakeLock) return;
  wakePending = true;
  try {
    const acquired = await navigator.wakeLock.request('screen');
    if (state.mode !== 'share' || document.visibilityState !== 'visible') {
      await acquired.release();
      return;
    }
    wakeLock = acquired;
    acquired.addEventListener('release', () => {
      if (wakeLock === acquired) wakeLock = null;
    });
  } catch {
    // Battery policy / browser support must never block a QR code.
  } finally {
    wakePending = false;
  }
}

function render() {
  root.dataset.mode = state.mode;
  root.style.setProperty('--rv-flip', state.flipped ? '180deg' : '0deg');
  front.inert = state.flipped || state.mode !== 'rest';
  back.inert = !state.flipped || state.mode !== 'rest';
  front.setAttribute('aria-hidden', String(front.inert));
  back.setAttribute('aria-hidden', String(back.inert));
  root.querySelector('.rv-ribbon').inert = state.mode !== 'rest';
  root.querySelectorAll('[data-drawer]').forEach(drawer => {
    const open = drawer.dataset.drawer === state.mode;
    drawer.classList.toggle('is-open', open);
    drawer.inert = !open;
    drawer.setAttribute('aria-hidden', String(!open));
  });
  root.querySelectorAll('.rv-dock [aria-expanded]').forEach(button => {
    button.setAttribute('aria-expanded', String(button.dataset.do === state.mode));
  });
  const flip = root.querySelector('.rv-dock [data-do="flip"]');
  flip.setAttribute('aria-label', state.flipped ? 'Show the front of the card' : 'Turn the card over');
  hint.textContent = {
    rest: state.flipped ? 'A little connection goes a long way.' : 'Press the seal to meet Romeo.',
    share: 'A clear QR, ready for the person beside you.',
    save: 'Front and back, to keep on any device.',
    taste: 'A few things we make, with a little care.',
  }[state.mode];
  fitStage();
  void syncWakeLock();
}

function close() {
  state.mode = 'rest';
  status.textContent = '';
  render();
  if (returnFocus?.isConnected && !returnFocus.closest('[inert]')) {
    returnFocus.focus({ preventScroll: true });
  } else {
    root.querySelector('.rv-dock [data-do="share"]').focus({ preventScroll: true });
  }
}

function open(mode, trigger) {
  if (state.mode === mode) return close();
  returnFocus = trigger;
  state.mode = mode;
  state.flipped = false;
  status.textContent = '';
  render();
  // Visibility is immediate; only the pull-out transform animates.
  root.querySelector(`[data-drawer="${mode}"] .rv-close`).focus({ preventScroll: true });
}

// Fetch ahead of the tap: Safari only opens the share sheet if share() follows the click directly.
function prepareKeepFiles() {
  if (keep.route !== 'share-images' || keep.files || keep.loading) return keep.loading;
  keep.loading = loadKeepFiles(url => fetch(url), config)
    .then(files => { keep.files = files; return files; })
    .catch(() => { keep.route = 'download'; showKeepRoute(); return null; })
    .finally(() => { keep.loading = null; });
  return keep.loading;
}

function showKeepRoute() {
  const photos = keep.route === 'share-images';
  root.querySelector('.rv-keep-label').textContent = photos ? 'Save to Photos' : 'Save front & back';
  root.querySelector('.rv-keep-help').textContent = photos
    ? 'Choose “Save 2 Images” to keep both sides in Photos.'
    : 'Both sides in one PDF that opens on any device.';
}

function downloadPdf() {
  root.querySelector('.rv-keep-files a[href$=".pdf"]').click();
  status.textContent = 'Downloading both sides as a PDF. You’ll find it in Downloads.';
}

async function keepCard() {
  if (keep.pending) return;
  if (keep.route !== 'share-images') return downloadPdf();
  if (!keep.files) {
    // The first tap came before the images arrived; the next tap opens the share sheet.
    keep.pending = true;
    status.textContent = 'Getting both sides ready…';
    await prepareKeepFiles();
    keep.pending = false;
    if (keep.route !== 'share-images') return downloadPdf();
    status.textContent = 'Ready. Tap Save to Photos again.';
    return;
  }
  keep.pending = true;
  const result = await shareImages(navigator, keep.files);
  keep.pending = false;
  if (result === 'unsupported' || result === 'failed') {
    keep.route = 'download';
    showKeepRoute();
    downloadPdf();
  } else {
    status.textContent = '';
  }
}

function isInstalled() {
  return matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
}

function showInstall() {
  const button = root.querySelector('[data-do="install"]');
  const hadFocus = document.activeElement === button;
  button.hidden = isInstalled() || !(installPrompt || isAppleTouch(navigator));
  if (!button.hidden) return;
  root.querySelector('.rv-install-help').hidden = true;
  // Hiding a focused button would drop focus to the page, out of reach of Escape.
  if (hadFocus) root.querySelector('.rv-keep-more [data-do="contact"]').focus({ preventScroll: true });
}

async function install() {
  const help = root.querySelector('.rv-install-help');
  if (installPrompt) {
    const prompt = installPrompt;
    installPrompt = null;
    await prompt.prompt();
    const { outcome } = await prompt.userChoice;
    status.textContent = outcome === 'accepted' ? 'Added. Romeo’s card now has its own icon.' : '';
    showInstall();
    return;
  }
  help.textContent = 'In Safari, tap Share, then “Add to Home Screen”. The card gets its own icon and opens even offline.';
  help.hidden = false;
  fitStage();
}

function showCopyFallback() {
  const fallback = root.querySelector('.rv-copy-fallback');
  fallback.hidden = false;
  const input = fallback.querySelector('input');
  input.focus({ preventScroll: true });
  input.select();
  status.textContent = 'Select the address and use your device’s Copy command.';
  fitStage();
}

root.addEventListener('click', async event => {
  const actionElement = event.target.closest('[data-do]');
  if (!actionElement || !root.contains(actionElement)) return;
  const action = actionElement.dataset.do;
  if (action === 'flip') {
    state.mode = 'rest';
    state.flipped = !state.flipped;
    status.textContent = '';
    render();
    root.querySelector('.rv-dock [data-do="flip"]').focus({ preventScroll: true });
  } else if (['share', 'save', 'taste'].includes(action)) {
    open(action, actionElement);
    if (state.mode === 'save') void prepareKeepFiles();
  } else if (action === 'close') {
    close();
  } else if (action === 'copy') {
    if (await copyCard(navigator, config)) {
      root.querySelector('.rv-copy-label').textContent = 'Copied';
      root.querySelector('.rv-copy-fallback').hidden = true;
      status.textContent = 'Link copied. Ready to pass on.';
      fitStage();
    } else {
      showCopyFallback();
    }
  } else if (action === 'send') {
    if (sharePending) return;
    sharePending = true;
    const result = await nativeShare(navigator, config);
    sharePending = false;
    if (result === 'unsupported' || result === 'failed') {
      status.textContent = 'Choose WhatsApp or email below, or copy the link.';
      root.querySelector('[data-channel="whatsapp"]').focus({ preventScroll: true });
    } else {
      // Resolution doesn't prove delivery to another person.
      status.textContent = '';
    }
  } else if (action === 'keep') {
    await keepCard();
  } else if (action === 'install') {
    await install();
  } else if (action === 'contact') {
    status.textContent = 'Your device will ask you to open or save the contact file.';
  }
});

root.addEventListener('keydown', event => {
  if (event.key === 'Escape' && state.mode !== 'rest') close();
});
document.addEventListener('visibilitychange', () => void syncWakeLock());
window.addEventListener('pagehide', () => {
  if (wakeLock) void wakeLock.release().catch(() => {});
});
const resizeObserver = new ResizeObserver(fitStage);
root.querySelectorAll('[data-drawer]').forEach(drawer => resizeObserver.observe(drawer));
document.fonts?.ready.then(fitStage);

if (typeof navigator.share !== 'function') {
  root.querySelector('.rv-send-label').textContent = 'Share options';
}
showKeepRoute();
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  installPrompt = event;
  showInstall();
});
window.addEventListener('appinstalled', () => {
  installPrompt = null;
  showInstall();
});
showInstall();
if (new URLSearchParams(location.search).get('view') === 'share') state.mode = 'share';
render();

const offline = root.querySelector('.rv-offline');
function showConnection() { offline.hidden = navigator.onLine; }
window.addEventListener('online', showConnection);
window.addEventListener('offline', showConnection);
showConnection();

// Local previews don't install a worker; production uses a small offline shell.
if ('serviceWorker' in navigator && location.protocol === 'https:' && location.origin === new URL(config.cardUrl).origin) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
