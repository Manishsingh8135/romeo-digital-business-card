import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { shareData, channelLinks, nativeShare, copyCard, isAppleTouch, keepRoute, loadKeepFiles, shareImages } from '../src/sharing.mjs';

const config = JSON.parse(await readFile(new URL('../site.config.json',import.meta.url)));
test('native and fallback channels use one canonical URL without preview / tracking parameters', () => {
  assert.equal(shareData(config).url,config.cardUrl);
  const links = channelLinks(config);
  assert.ok(new URL(links.whatsapp).searchParams.get('text').endsWith(config.cardUrl));
  assert.ok(new URL(links.email).searchParams.get('body').endsWith(config.cardUrl));
});
test('share is called synchronously from the gesture with the correct payload', async () => {
  let called = false;
  const result = nativeShare({share(data){called=true;assert.deepEqual(data,shareData(config));return Promise.resolve();}},config);
  assert.equal(called,true);
  assert.equal(await result,'completed');
});
test('share distinguishes cancellation, lack of support, and failures', async () => {
  assert.equal(await nativeShare({},config),'unsupported');
  assert.equal(await nativeShare({share(){throw {name:'AbortError'};}},config),'cancelled');
  assert.equal(await nativeShare({share(){throw {name:'NotAllowedError'};}},config),'failed');
});
test('copy never reports success when denied or unsupported', async () => {
  assert.equal(await copyCard({},config),false);
  assert.equal(await copyCard({clipboard:{writeText:async()=>{throw new Error('Denied');}}},config),false);
  let copied;
  assert.equal(await copyCard({clipboard:{writeText:async text=>{copied=text;}}},config),true);
  assert.equal(copied,config.cardUrl);
});

const iphone = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';
const ipad = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15';
const sharer = { share: async () => {}, canShare: data => data.files?.length > 0 };
test('only iPhone and iPad save the card through the share sheet; everything else downloads one PDF', () => {
  assert.equal(isAppleTouch({ userAgent: iphone }), true);
  assert.equal(isAppleTouch({ userAgent: ipad, maxTouchPoints: 5 }), true);
  assert.equal(isAppleTouch({ userAgent: ipad, maxTouchPoints: 0 }), false);
  assert.equal(keepRoute({ ...sharer, userAgent: iphone }), 'share-images');
  assert.equal(keepRoute({ ...sharer, userAgent: 'Mozilla/5.0 (Linux; Android 15) Chrome/130 Mobile' }), 'download');
  assert.equal(keepRoute({ userAgent: iphone }), 'download');
  assert.equal(keepRoute({ ...sharer, canShare: () => false, userAgent: iphone }), 'download');
});
test('both sides load as named PNG files, and a missing side is an error rather than half a card', async () => {
  const keep = { front: '/assets/keep/front.png', back: '/assets/keep/back.png', pdf: '/assets/keep/card.pdf' };
  const files = await loadKeepFiles(async () => new Response(new Blob(['png'])), { keep });
  assert.deepEqual(files.map(file => [file.name, file.type]), [['front.png', 'image/png'], ['back.png', 'image/png']]);
  await assert.rejects(loadKeepFiles(async url => new Response('', { status: url.includes('back') ? 404 : 200 }), { keep }));
});
test('image sharing sends files only and reports cancellation separately from failure', async () => {
  const files = [new File(['a'], 'front.png', { type: 'image/png' })];
  let sent;
  assert.equal(await shareImages({ ...sharer, share: async data => { sent = data; } }, files), 'completed');
  assert.deepEqual(Object.keys(sent), ['files']);
  assert.equal(await shareImages({}, files), 'unsupported');
  assert.equal(await shareImages({ ...sharer, share: async () => { throw { name: 'AbortError' }; } }, files), 'cancelled');
  assert.equal(await shareImages({ ...sharer, share: async () => { throw { name: 'NotAllowedError' }; } }, files), 'failed');
});
