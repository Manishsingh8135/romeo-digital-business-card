import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { shareData, channelLinks, nativeShare, copyCard } from '../src/sharing.mjs';

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
