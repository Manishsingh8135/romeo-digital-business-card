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
