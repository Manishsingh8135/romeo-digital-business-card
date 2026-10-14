// Always share the configured public URL, never a preview URL or tracking query.
export function shareData(config) {
  return {
    title: config.brand,
    text: 'Meet Romeo. A little closer to nature.',
    url: config.cardUrl,
  };
}

export function channelLinks(config) {
  const text = `Meet ${config.founder} · ${config.brand}\n${config.cardUrl}`;
  return {
    whatsapp: `https://wa.me/?text=${encodeURIComponent(text)}`,
    email: `mailto:?subject=${encodeURIComponent(config.brand)}&body=${encodeURIComponent(text)}`,
  };
}

export async function nativeShare(browserNavigator, config) {
  if (typeof browserNavigator.share !== 'function') return 'unsupported';
  try {
    // This must run directly from the click: no fetch/await before share().
    await browserNavigator.share(shareData(config));
    return 'completed';
  } catch (error) {
    // Cancelling the system sheet is a normal action, not a failure.
    return error?.name === 'AbortError' ? 'cancelled' : 'failed';
  }
}

export async function copyCard(browserNavigator, config) {
  try {
    if (!browserNavigator.clipboard?.writeText) return false;
    await browserNavigator.clipboard.writeText(config.cardUrl);
    return true;
  } catch {
    return false;
  }
}

// iPhone and iPad (including iPadOS's desktop-class Safari), where “Save Image” lives in the share sheet.
export function isAppleTouch(browserNavigator) {
  const agent = browserNavigator.userAgent || '';
  return /iPhone|iPad|iPod/.test(agent) || (/Macintosh/.test(agent) && browserNavigator.maxTouchPoints > 1);
}

// Apple touch devices save shared images straight to Photos; everywhere else one PDF download
// avoids the browser's “multiple downloads” prompt and opens on any device.
export function keepRoute(browserNavigator, FileType = globalThis.File) {
  if (!isAppleTouch(browserNavigator) || typeof browserNavigator.share !== 'function' || typeof FileType !== 'function') return 'download';
  try {
    const probe = new FileType([''], 'probe.png', { type: 'image/png' });
    return browserNavigator.canShare?.({ files: [probe] }) ? 'share-images' : 'download';
  } catch {
    return 'download';
  }
}

export async function loadKeepFiles(fetcher, config, FileType = globalThis.File) {
  return Promise.all(['front', 'back'].map(async side => {
    const response = await fetcher(config.keep[side]);
    if (!response.ok) throw new Error(`Card ${side} unavailable`);
    const name = config.keep[side].split('/').pop();
    return new FileType([await response.blob()], name, { type: 'image/png' });
  }));
}

export async function shareImages(browserNavigator, files) {
  // Files only: adding text or a URL hides “Save Image” on iOS.
  if (!browserNavigator.canShare?.({ files })) return 'unsupported';
  try {
    await browserNavigator.share({ files });
    return 'completed';
  } catch (error) {
    return error?.name === 'AbortError' ? 'cancelled' : 'failed';
  }
}
