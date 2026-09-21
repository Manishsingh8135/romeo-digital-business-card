import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source=await readFile(new URL('../dist/sw.js',import.meta.url),'utf8');
function worker({offline=false,oldCache=false}={}) {
  const events={}; const stored=new Map(); const deleted=[]; let networkRequests=0;
  const cache={addAll:async keys=>{keys.forEach(key=>stored.set(key,new Response('saved '+key)));},match:async key=>stored.get(key)?.clone(),put:async(key,value)=>stored.set(key,value)};
  const context={URL,Set,Response,self:{location:{origin:'https://hello.romeoshealthheaven.com'},clients:{claim:async()=>{}},addEventListener:(name,callback)=>events[name]=callback},caches:{open:async()=>cache,keys:async()=>oldCache?['romeo-card-old','unrelated-app']:[],delete:async key=>deleted.push(key)},fetch:async()=>{networkRequests++;if(offline)throw new Error('offline');return new Response('fresh');}};
  vm.runInNewContext(source,context);
  async function event(name){let pending;events[name]({waitUntil(value){pending=value;}});await pending;}
  async function request(path,{mode='cors',method='GET',origin=context.self.location.origin}={}){let result;events.fetch({request:{url:origin+path,mode,method},respondWith(value){result=value;}});return result?await result:null;}
  return {event,request,stored,deleted,get networkRequests(){return networkRequests;}};
}
test('offline navigation with share query returns saved root; contact and QR remain available',async()=>{
  const w=worker({offline:true});await w.event('install');
  assert.equal(await(await w.request('/?view=share',{mode:'navigate'})).text(),'saved /');
  assert.equal(await(await w.request('/romeo-health-heaven.vcf')).text(),'saved /romeo-health-heaven.vcf');
  assert.equal(await(await w.request('/assets/qr-card.svg')).text(),'saved /assets/qr-card.svg');
});
test('online HTML, contact and scripts revalidate rather than returning stale content',async()=>{
  const w=worker();await w.event('install');
  for(const file of ['/', '/romeo-health-heaven.vcf','/app.mjs']) {
    const response=await w.request(file,{mode:file==='/'?'navigate':'cors'});
    assert.equal(await response.text(),'fresh');
  }
  assert.equal(w.networkRequests,3);
});
test('worker ignores external links, mutations, and unknown navigation paths',async()=>{
  const w=worker();
  assert.equal(await w.request('/shop/',{origin:'https://romeoshealthheaven.com'}),null);
  assert.equal(await w.request('/',{method:'POST'}),null);
  assert.equal(await w.request('/missing',{mode:'navigate'}),null);
});
test('activation removes only this card’s obsolete caches',async()=>{
  const w=worker({oldCache:true});await w.event('activate');
  assert.deepEqual(w.deleted,['romeo-card-old']);
});
