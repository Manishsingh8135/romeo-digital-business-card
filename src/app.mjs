import config from './config.mjs';
import { nativeShare, copyCard } from './sharing.mjs';

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
    save: 'Confirm the new contact in your contacts app.',
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
