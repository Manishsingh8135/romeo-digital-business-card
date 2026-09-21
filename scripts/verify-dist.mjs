import { readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';

const root = fileURLToPath(new URL('../',import.meta.url));
const info = JSON.parse(await readFile(path.join(root,'dist/build-info.json'),'utf8'));
async function files(directory) {
  const entries = await readdir(directory,{withFileTypes:true});
  const result = await Promise.all(entries.map(entry => entry.isDirectory() ? files(path.join(directory,entry.name)) : [path.join(directory,entry.name)]));
  return result.flat();
}
async function hashes(paths,base) {
  const pairs = await Promise.all(paths.map(async file => [path.relative(base,file).split(path.sep).join('/'),createHash('sha256').update(await readFile(file)).digest('hex')]));
  return Object.fromEntries(pairs.sort(([a],[b]) => a<b?-1:a>b?1:0));
}
try {
  const inputs = ['site.config.json','requirements.txt','scripts/build.py'].map(file => path.join(root,file));
  inputs.push(...await files(path.join(root,'src')),...await files(path.join(root,'assets')));
  assert.deepEqual(await hashes(inputs,root),info.sourceHashes,'Sources changed: rebuild before deploying.');
  const dist = path.join(root,'dist');
  const outputs = (await files(dist)).filter(file => path.basename(file)!=='build-info.json');
  assert.deepEqual(await hashes(outputs,dist),info.outputHashes,'Generated files changed: rebuild before deploying.');
  const config = JSON.parse(await readFile(path.join(root,'site.config.json'),'utf8'));
  assert.equal(info.cardUrl,config.cardUrl);
  const vercel = JSON.parse(await readFile(path.join(root,'vercel.json'),'utf8'));
  const headers = JSON.parse(await readFile(path.join(dist,'headers.json'),'utf8'));
  assert.deepEqual(Object.fromEntries(vercel.headers[0].headers.map(({key,value})=>[key,value])),headers,'Rebuild to refresh Vercel headers.');
  console.log('Static output matches source and configuration. Ready to deploy dist/.');
} catch(error) {
  console.error(error.message);
  console.error('Run: python3 scripts/build.py, then commit dist/ and vercel.json with the source changes.');
  process.exitCode=1;
}
